"""Unit tests for the raw_articles upsert logic - field normalization across the two providers
(NewsAPI, GNews) and the insert/dedup control flow, against a fake Postgres connection (no real
database or Airflow needed - see the `conn` param docstring in postgres_io.py).

psycopg2's execute_values does real byte-string templating via cur.mogrify(), so a plain
MagicMock cursor can't stand in for it directly - it's patched at the source instead, and only
its return value (the "fetch" result driving rows_new) is asserted on.
"""

from unittest.mock import MagicMock, patch

import news_pipeline.postgres_io as postgres_io
from news_pipeline.postgres_io import _extract_common_fields, upsert_articles

NEWSAPI_ARTICLE = {
    "source": {"id": "forbes", "name": "Forbes"},
    "author": "Jane Doe",
    "title": "T",
    "description": "D",
    "content": "C",
    "url": "https://forbes.com/a",
    "urlToImage": "https://forbes.com/img.jpg",
    "publishedAt": "2026-07-26T12:00:00Z",
}

GNEWS_ARTICLE = {
    "source": {"name": "Biztoc.com"},
    "title": "T2",
    "description": "D2",
    "content": "C2",
    "url": "https://biztoc.com/a",
    "image": "https://biztoc.com/img.jpg",
    "publishedAt": "2026-07-26T12:12:00Z",
}


def _fake_conn():
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def test_extract_common_fields_newsapi_maps_source_id_and_author():
    fields = _extract_common_fields("newsapi", NEWSAPI_ARTICLE)
    assert fields["source_id"] == "forbes"
    assert fields["source_name"] == "Forbes"
    assert fields["author"] == "Jane Doe"
    assert fields["url_to_image"] == "https://forbes.com/img.jpg"


def test_extract_common_fields_gnews_has_no_source_id_or_author():
    fields = _extract_common_fields("gnews", GNEWS_ARTICLE)
    assert fields["source_id"] is None
    assert fields["author"] is None
    assert fields["source_name"] == "Biztoc.com"


def test_extract_common_fields_gnews_maps_image_field_not_urltoimage():
    fields = _extract_common_fields("gnews", GNEWS_ARTICLE)
    assert fields["url_to_image"] == "https://biztoc.com/img.jpg"


def test_extract_common_fields_handles_missing_source_gracefully():
    fields = _extract_common_fields("newsapi", {"url": "https://example.com/a"})
    assert fields["source_id"] is None
    assert fields["source_name"] is None


def test_upsert_articles_returns_zero_for_empty_input():
    conn = _fake_conn()
    rows_new, rows_duplicate = upsert_articles([], ingestion_run_id="run1", conn=conn)
    assert (rows_new, rows_duplicate) == (0, 0)
    conn.cursor.assert_not_called()


def test_upsert_articles_skips_items_with_no_url():
    conn = _fake_conn()
    items = [("newsapi", "technology", {"title": "no url here"})]
    with patch.object(postgres_io, "execute_values", return_value=[]) as mock_execute_values:
        upsert_articles(items, ingestion_run_id="run1", conn=conn)
    # Called with an empty rows list - nothing had a url to build a row from.
    _, args, _ = mock_execute_values.mock_calls[0]
    assert args[2] == []


def test_upsert_articles_counts_new_vs_duplicate():
    conn = _fake_conn()
    items = [
        ("newsapi", "technology", NEWSAPI_ARTICLE),
        ("gnews", "technology", GNEWS_ARTICLE),
    ]
    # Only one of the two rows reported as newly inserted (the other hit ON CONFLICT DO NOTHING).
    with patch.object(postgres_io, "execute_values", return_value=[("some_hash",)]):
        rows_new, rows_duplicate = upsert_articles(items, ingestion_run_id="run1", conn=conn)

    assert rows_new == 1
    assert rows_duplicate == 1
    conn.commit.assert_called_once()


def test_upsert_articles_does_not_close_an_injected_connection():
    conn = _fake_conn()
    items = [("newsapi", "technology", NEWSAPI_ARTICLE)]
    with patch.object(postgres_io, "execute_values", return_value=[("h",)]):
        upsert_articles(items, ingestion_run_id="run1", conn=conn)
    conn.close.assert_not_called()
