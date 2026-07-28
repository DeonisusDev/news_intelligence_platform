"""Fakes for the FastAPI test suite - no real ClickHouse/Postgres connection is ever made.
Dependencies are overridden via FastAPI's app.dependency_overrides, matched by the exact
function object each router imports via `from db.xxx import get_xxx` (identity-based, so
importing the same names here is what makes the override actually apply).
"""

import pytest
from db.clickhouse_client import get_clickhouse_client
from db.postgres_client import get_postgres_connection
from fastapi.testclient import TestClient
from main import app


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
