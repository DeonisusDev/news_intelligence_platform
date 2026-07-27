"""Thin custom BaseHook wrapping clickhouse-connect (official HTTP client).

No first-party stable Airflow provider targets ClickHouse yet, and community options are
built on the less-maintained native-protocol clickhouse-driver with uncertain Airflow 3
compatibility - a hand-rolled hook over clickhouse-connect's HTTP client is small, transparent,
and reuses Airflow's own Variable-backed config plumbing (see config.py).
"""
from __future__ import annotations

import clickhouse_connect
from airflow.hooks.base import BaseHook

from .config import get_settings


class ClickHouseHook(BaseHook):
    def get_client(self) -> clickhouse_connect.driver.Client:
        settings = get_settings()
        return clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
        )
