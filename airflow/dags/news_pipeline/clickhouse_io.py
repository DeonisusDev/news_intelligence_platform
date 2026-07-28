"""Copies this run's newly-inserted raw_articles rows from Postgres into ClickHouse via
ClickHouse's built-in postgresql() table function - a pure SQL pull, no Python row-shuttling.

Rows in Postgres only carry the current ingestion_run_id if they were actually inserted this
run; duplicates caught by ON CONFLICT DO NOTHING keep whatever ingestion_run_id they already
had (see postgres_io.py). Scoping this copy by ingestion_run_id therefore both selects "new
since last run" and reuses the same idempotency guarantee: rerunning an already-processed day
finds zero matching Postgres rows and copies nothing into ClickHouse.
"""
from __future__ import annotations

from airflow.hooks.base import BaseHook

from .clickhouse_hook import ClickHouseHook

NEWSDATA_CONN_ID = "newsdata_pg"

_TABLE_FUNCTION = (
    "postgresql({conn:String}, {db:String}, 'raw_articles', {user:String}, {password:String})"
)

_COLUMNS = """
    url_hash, source_id, source_name, author, title, description, content,
    url, url_to_image, published_at, category, source_provider, fetched_at, raw_payload,
    ingestion_run_id, created_at
"""

_COUNT_SQL = f"SELECT count() FROM {_TABLE_FUNCTION} WHERE ingestion_run_id = {{run_id:String}}"

_INSERT_SQL = f"""
INSERT INTO raw.newsapi_articles ({_COLUMNS})
SELECT {_COLUMNS}
FROM {_TABLE_FUNCTION}
WHERE ingestion_run_id = {{run_id:String}}
"""


def _postgres_conn_params() -> dict:
    conn = BaseHook.get_connection(NEWSDATA_CONN_ID)
    return {
        "conn": f"{conn.host}:{conn.port}",
        "db": conn.schema,
        "user": conn.login,
        "password": conn.password,
    }


def load_new_rows(run_id: str) -> int:
    """Inserts this run's new raw_articles rows into ClickHouse. Returns the row count."""
    params = {**_postgres_conn_params(), "run_id": run_id}
    client = ClickHouseHook().get_client()

    count = client.query(_COUNT_SQL, parameters=params).result_rows[0][0]
    if count == 0:
        return 0

    client.command(_INSERT_SQL, parameters=params)
    return count
