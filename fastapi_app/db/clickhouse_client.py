"""FastAPI dependency yielding a ClickHouse client per request.

clickhouse-connect's client is a thin HTTP wrapper (cheap to construct), so a
fresh one per request keeps this dependency simple and avoids any question of
thread-safety when FastAPI runs sync endpoints across its threadpool.
"""

from __future__ import annotations

from typing import Iterator

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from config import get_settings


def get_clickhouse_client() -> Iterator[Client]:
    settings = get_settings()
    client = clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_database,
    )
    try:
        yield client
    finally:
        client.close()
