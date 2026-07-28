"""Thin client for GNews.io's /v4/top-headlines endpoint - a second, independent source of
top/main headlines across categories, so the same real-world story is more likely to be
covered by an outlet NewsAPI's index doesn't carry (both feed the same clustering step, see
docs/adr/0005-article-clustering.md).

Free tier constraints this is designed around: 100 requests/day, and pagination (`page` param)
is a paid-only feature - a single request per category (max 10 articles/request) is all the
free tier allows, so there's no page-loop here unlike newsapi_client.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

GNEWS_BASE_URL = "https://gnews.io/api/v4/top-headlines"
MAX_ARTICLES_PER_REQUEST = 10


@dataclass
class FetchResult:
    category: str
    articles: list[dict]
    requests_used: int


def fetch_articles_for_category(api_key: str, category: str) -> FetchResult:
    """Fetch the single page of top headlines GNews's free tier allows for one category."""
    response = requests.get(
        GNEWS_BASE_URL,
        params={
            "category": category,
            "lang": "en",
            "max": MAX_ARTICLES_PER_REQUEST,
            "apikey": api_key,
        },
        timeout=15,
    )

    if response.status_code != 200:
        logger.warning(
            "GNews request failed category=%s status=%s body=%s",
            category, response.status_code, response.text[:500],
        )
        return FetchResult(category=category, articles=[], requests_used=1)

    payload = response.json()
    return FetchResult(category=category, articles=payload.get("articles", []), requests_used=1)


def fetch_articles(api_key: str, categories: list[str], max_requests_per_run: int) -> list[tuple[str, dict]]:
    """Fetch top headlines across all configured categories, respecting a total request budget
    for the whole run (one request per category). Returns a list of (category, article) pairs.
    """
    results: list[tuple[str, dict]] = []
    requests_remaining = max_requests_per_run

    for category in categories:
        if requests_remaining <= 0:
            logger.info("Request budget exhausted, skipping remaining categories")
            break

        result = fetch_articles_for_category(api_key, category)
        requests_remaining -= result.requests_used
        for article in result.articles:
            results.append((category, article))

    return results
