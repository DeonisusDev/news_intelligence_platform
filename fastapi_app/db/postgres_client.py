"""FastAPI dependency yielding a Postgres connection per request. Only used for
pipeline_run_log (operational history) - all article/summary data lives in ClickHouse.
"""
from __future__ import annotations

from typing import Iterator

import psycopg2
from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import RealDictCursor

from config import get_settings


def get_postgres_connection() -> Iterator[PGConnection]:
    settings = get_settings()
    conn = psycopg2.connect(settings.newsdata_pg_dsn, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()
