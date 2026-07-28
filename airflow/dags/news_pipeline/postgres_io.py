"""Idempotent upsert of raw articles into Postgres.

Dedup semantics: first-seen-wins. ON CONFLICT (url_hash) DO NOTHING keeps raw_articles
immutable and lets the caller count new-vs-duplicate rows from the returned inserted count.

Two providers (NewsAPI, GNews) feed this same table - each has a slightly different article
shape (e.g. GNews has no source.id/author, and calls the image field "image" not "urlToImage"),
so _extract_common_fields() normalizes both into one row shape before insert. raw_payload still
stores the untouched provider-native JSON for replay/audit.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from psycopg2.extras import execute_values

from .dedup import url_hash

NEWSDATA_CONN_ID = "newsdata_pg"

_INSERT_SQL = """
INSERT INTO raw_articles (
    url_hash, source_id, source_name, author, title, description, content,
    url, url_to_image, published_at, category, source_provider, fetched_at,
    raw_payload, ingestion_run_id
) VALUES %s
ON CONFLICT (url_hash) DO NOTHING
RETURNING url_hash
"""


def _extract_common_fields(provider: str, article: dict) -> dict:
    source = article.get("source") or {}
    if provider == "gnews":
        return {
            "source_id": None,
            "source_name": source.get("name"),
            "author": None,
            "title": article.get("title"),
            "description": article.get("description"),
            "content": article.get("content"),
            "url": article.get("url"),
            "url_to_image": article.get("image"),
            "published_at": article.get("publishedAt"),
        }
    return {
        "source_id": source.get("id"),
        "source_name": source.get("name"),
        "author": article.get("author"),
        "title": article.get("title"),
        "description": article.get("description"),
        "content": article.get("content"),
        "url": article.get("url"),
        "url_to_image": article.get("urlToImage"),
        "published_at": article.get("publishedAt"),
    }


def upsert_articles(
    items: list[tuple[str, str, dict]], ingestion_run_id: str, conn=None
) -> tuple[int, int]:
    """`items` is a list of (provider, category, article) tuples.

    Returns (rows_new, rows_duplicate). `conn` is injectable (defaults to a real PostgresHook
    connection) so tests can pass a fake without needing Airflow installed - the import is
    local to keep this module importable on its own for unit-testing _extract_common_fields.
    """
    if not items:
        return 0, 0

    fetched_at = datetime.now(timezone.utc)
    rows = []
    for provider, category, article in items:
        fields = _extract_common_fields(provider, article)
        if not fields["url"]:
            continue
        rows.append(
            (
                url_hash(fields["url"]),
                fields["source_id"],
                fields["source_name"],
                fields["author"],
                fields["title"],
                fields["description"],
                fields["content"],
                fields["url"],
                fields["url_to_image"],
                fields["published_at"],
                category,
                provider,
                fetched_at,
                json.dumps(article, ensure_ascii=False),
                ingestion_run_id,
            )
        )

    owns_conn = conn is None
    if owns_conn:
        from airflow.providers.postgres.hooks.postgres import PostgresHook

        conn = PostgresHook(postgres_conn_id=NEWSDATA_CONN_ID).get_conn()
    try:
        with conn.cursor() as cur:
            inserted = execute_values(cur, _INSERT_SQL, rows, fetch=True)
            rows_new = len(inserted)
        conn.commit()
    finally:
        if owns_conn:
            conn.close()

    rows_duplicate = len(rows) - rows_new
    return rows_new, rows_duplicate
