"""Thin client for NewsAPI.org's /v2/top-headlines endpoint.

Pulls top/main headlines across a fixed set of categories (business, technology, ...) rather
than keyword search - this is meant to feed a general-interest Discovery-style feed, not a
tech-news filter. See docs/adr/0006-top-headlines-multi-source.md.

Free Developer tier constraints this is designed around (not silently ignored):
100 requests/day total (shared with manual testing), ~24h publication delay, and the
`content` field truncated to ~260 characters. See README "Known limitations".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

NEWSAPI_BASE_URL = "https://newsapi.org/v2/top-headlines"
PAGE_SIZE = 100


@dataclass
class FetchResult:
    category: str
    articles: list[dict]
    requests_used: int


def fetch_articles_for_category(api_key: str, category: str, max_requests: int) -> FetchResult:
    """Fetch up to `max_requests` pages of top headlines for a single category."""
    articles: list[dict] = []
    requests_used = 0

    for page in range(1, max_requests + 1):
        response = requests.get(
            NEWSAPI_BASE_URL,
            params={
                "category": category,
                "language": "en",
                "pageSize": PAGE_SIZE,
                "page": page,
            },
            headers={"X-Api-Key": api_key},
            timeout=15,
        )
        requests_used += 1

        if response.status_code != 200:
            logger.warning(
                "NewsAPI request failed category=%s page=%s status=%s body=%s",
                category, page, response.status_code, response.text[:500],
            )
            break

        payload = response.json()
        page_articles = payload.get("articles", [])
        articles.extend(page_articles)

        total_results = payload.get("totalResults", 0)
        if len(page_articles) < PAGE_SIZE or page * PAGE_SIZE >= total_results:
            break

    return FetchResult(category=category, articles=articles, requests_used=requests_used)


def fetch_articles(api_key: str, categories: list[str], max_requests_per_run: int) -> list[tuple[str, dict]]:
    """Fetch top headlines across all configured categories, respecting a total request budget
    for the whole run (not per category). Returns a list of (category, article) pairs.
    """
    results: list[tuple[str, dict]] = []
    requests_remaining = max_requests_per_run

    for category in categories:
        if requests_remaining <= 0:
            logger.info("Request budget exhausted, skipping remaining categories")
            break

        result = fetch_articles_for_category(api_key, category, max_requests=requests_remaining)
        requests_remaining -= result.requests_used
        for article in result.articles:
            results.append((category, article))

    return results
