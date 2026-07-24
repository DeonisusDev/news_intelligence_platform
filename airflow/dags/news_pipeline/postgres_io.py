"""Idempotent upsert of raw articles into Postgres.

Dedup semantics: first-seen-wins. ON CONFLICT (url_hash) DO NOTHING keeps raw_articles
immutable and lets the caller count new-vs-duplicate rows from the returned inserted count.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import execute_values

from .dedup import url_hash

NEWSDATA_CONN_ID = "newsdata_pg"

_INSERT_SQL = """
INSERT INTO raw_articles (
    url_hash, source_id, source_name, author, title, description, content,
    url, url_to_image, published_at, query_keyword, fetched_at, raw_payload, ingestion_run_id
) VALUES %s
ON CONFLICT (url_hash) DO NOTHING
RETURNING url_hash
"""


def upsert_articles(query_article_pairs: list[tuple[str, dict]], ingestion_run_id: str) -> tuple[int, int]:
    """Returns (rows_new, rows_duplicate)."""
    if not query_article_pairs:
        return 0, 0

    fetched_at = datetime.now(timezone.utc)
    rows = []
    for query, article in query_article_pairs:
        url = article.get("url")
        if not url:
            continue
        source = article.get("source") or {}
        rows.append((
            url_hash(url),
            source.get("id"),
            source.get("name"),
            article.get("author"),
            article.get("title"),
            article.get("description"),
            article.get("content"),
            url,
            article.get("urlToImage"),
            article.get("publishedAt"),
            query,
            fetched_at,
            json.dumps(article, ensure_ascii=False),
            ingestion_run_id,
        ))

    hook = PostgresHook(postgres_conn_id=NEWSDATA_CONN_ID)
    conn = hook.get_conn()
    try:
        with conn.cursor() as cur:
            inserted = execute_values(cur, _INSERT_SQL, rows, fetch=True)
            rows_new = len(inserted)
        conn.commit()
    finally:
        conn.close()

    rows_duplicate = len(rows) - rows_new
    return rows_new, rows_duplicate
