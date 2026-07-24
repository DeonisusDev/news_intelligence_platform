"""Thin client for NewsAPI.org's /v2/everything endpoint.

Free Developer tier constraints this is designed around (not silently ignored):
100 requests/day total (shared with manual testing), ~24h publication delay, and the
`content` field truncated to ~260 characters. See README "Known limitations".
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"
PAGE_SIZE = 20


@dataclass
class FetchResult:
    query: str
    articles: list[dict]
    requests_used: int


def fetch_articles_for_query(api_key: str, query: str, max_requests: int) -> FetchResult:
    """Fetch up to `max_requests` pages of articles for a single query term."""
    articles: list[dict] = []
    requests_used = 0

    for page in range(1, max_requests + 1):
        response = requests.get(
            NEWSAPI_BASE_URL,
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": PAGE_SIZE,
                "page": page,
            },
            headers={"X-Api-Key": api_key},
            timeout=15,
        )
        requests_used += 1

        if response.status_code != 200:
            logger.warning(
                "NewsAPI request failed query=%s page=%s status=%s body=%s",
                query, page, response.status_code, response.text[:500],
            )
            break

        payload = response.json()
        page_articles = payload.get("articles", [])
        articles.extend(page_articles)

        total_results = payload.get("totalResults", 0)
        if len(page_articles) < PAGE_SIZE or page * PAGE_SIZE >= total_results:
            break

    return FetchResult(query=query, articles=articles, requests_used=requests_used)


def fetch_articles(api_key: str, queries: list[str], max_requests_per_run: int) -> list[tuple[str, dict]]:
    """Fetch articles across all configured queries, respecting a total request budget
    for the whole run (not per query). Returns a list of (query, article) pairs.
    """
    results: list[tuple[str, dict]] = []
    requests_remaining = max_requests_per_run

    for query in queries:
        if requests_remaining <= 0:
            logger.info("Request budget exhausted, skipping remaining queries")
            break

        result = fetch_articles_for_query(api_key, query, max_requests=requests_remaining)
        requests_remaining -= result.requests_used
        for article in result.articles:
            results.append((query, article))

    return results
