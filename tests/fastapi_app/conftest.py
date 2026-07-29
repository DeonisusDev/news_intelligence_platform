"""Fakes for the FastAPI test suite - no real ClickHouse/Postgres connection is ever made.
Dependencies are overridden via FastAPI's app.dependency_overrides, matched by the exact
function object each router imports via `from db.xxx import get_xxx` (identity-based, so
importing the same names here is what makes the override actually apply).
"""

import os

# Settings() requires NEWSDATA_PG_DSN and main.py now reads settings at import time (for the
# CORS middleware's allowed-origins list) - no real Postgres connection is ever made in these
# tests (get_postgres_connection is overridden below), so any well-formed DSN placeholder works.
os.environ.setdefault("NEWSDATA_PG_DSN", "postgresql://test:test@localhost:5432/test")

import pytest  # noqa: E402
from db.clickhouse_client import get_clickhouse_client  # noqa: E402
from db.postgres_client import get_postgres_connection  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


class FakeQueryResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClickHouseClient:
    """Each call to .query() pops the next canned response, in call order - matches how the
    discover detail endpoint issues two queries (card, then sources) per request."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.queries = []

    def query(self, sql, parameters=None):
        self.queries.append((sql, parameters))
        return FakeQueryResult(self._responses.pop(0))


class FakePipelineCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed_with = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        self.executed_with = params

    def fetchall(self):
        return self._rows


class FakePostgresConnection:
    def __init__(self, rows):
        self._cursor = FakePipelineCursor(rows)

    def cursor(self):
        return self._cursor


@pytest.fixture
def make_client():
    """Returns a factory: make_client(ch_responses=[...]) -> TestClient with a fake ClickHouse
    client wired in, one canned result list per expected .query() call."""

    def _make(ch_responses=None):
        fake = FakeClickHouseClient(ch_responses or [])
        app.dependency_overrides[get_clickhouse_client] = lambda: fake
        return TestClient(app), fake

    yield _make
    app.dependency_overrides.pop(get_clickhouse_client, None)


@pytest.fixture
def make_pg_client():
    """Returns a factory: make_pg_client(rows) -> TestClient with a fake Postgres connection
    wired in, returning `rows` (a list of dicts) from cur.fetchall()."""

    def _make(rows):
        fake_conn = FakePostgresConnection(rows)
        app.dependency_overrides[get_postgres_connection] = lambda: fake_conn
        return TestClient(app), fake_conn

    yield _make
    app.dependency_overrides.pop(get_postgres_connection, None)
