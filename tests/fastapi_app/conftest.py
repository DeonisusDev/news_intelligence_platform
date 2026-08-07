"""Fakes for the FastAPI test suite - no real ClickHouse/Postgres connection is ever made.
Dependencies are overridden via FastAPI's app.dependency_overrides, matched by the exact
function object each router imports via `from db.xxx import get_xxx` (identity-based, so
importing the same names here is what makes the override actually apply).
"""

import os

# Settings() requires NEWSDATA_PG_DSN/JWT_SECRET and main.py now reads settings at import time
# (for the CORS middleware's allowed-origins list) - no real Postgres connection is ever made in
# these tests (get_postgres_connection is overridden below), so placeholders are fine.
os.environ.setdefault("NEWSDATA_PG_DSN", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

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

    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.fixture
def make_client():
    """Returns a factory: make_client(ch_responses=[...]) -> TestClient with a fake ClickHouse
    client wired in, one canned result list per expected .query() call. Postgres is also wired
    to a harmless empty fake by default (list_summary_cards declares it as a dependency but only
    touches it for logged-in requests, which none of these tests send)."""

    def _make(ch_responses=None):
        fake = FakeClickHouseClient(ch_responses or [])
        app.dependency_overrides[get_clickhouse_client] = lambda: fake
        app.dependency_overrides[get_postgres_connection] = lambda: FakePostgresConnection([])
        return TestClient(app), fake

    yield _make
    app.dependency_overrides.pop(get_clickhouse_client, None)
    app.dependency_overrides.pop(get_postgres_connection, None)


class FakeUsersCursor:
    """Understands exactly the two queries routers/auth.py issues, backed by an in-memory dict
    keyed by email - enough to exercise register/login's real branching (duplicate email,
    wrong password) without a real Postgres."""

    def __init__(self, store):
        self._store = store
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        sql_l = sql.lower()
        if "insert into users" in sql_l:
            email = params["email"]
            if email in self._store:
                import psycopg2.errors

                raise psycopg2.errors.UniqueViolation("duplicate email")
            row = {
                "id": len(self._store) + 1,
                "email": email,
                "password_hash": params["password_hash"],
                "created_at": "2026-08-04T00:00:00+00:00",
            }
            self._store[email] = row
            self._result = row
        elif "select" in sql_l and "from users" in sql_l:
            self._result = self._store.get(params["email"])
        else:
            raise AssertionError(f"FakeUsersCursor doesn't understand: {sql!r}")

    def fetchone(self):
        return self._result


class FakeUsersConnection:
    def __init__(self, store):
        self._store = store

    def cursor(self):
        return FakeUsersCursor(self._store)

    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.fixture
def make_auth_client():
    """Returns a factory: make_auth_client() -> (TestClient, users_store dict), with an
    in-memory fake Postgres users table wired in via dependency override."""

    def _make(seed_users=None):
        store = dict(seed_users or {})
        app.dependency_overrides[get_postgres_connection] = lambda: FakeUsersConnection(store)
        return TestClient(app), store

    yield _make
    app.dependency_overrides.pop(get_postgres_connection, None)


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


class FakeFeedbackCursor:
    """Understands exactly the cluster_feedback queries routers/discover.py issues (Phase 7),
    backed by an in-memory {(user_id, cluster_id): vote} dict - real upsert/delete/select
    branching without a real Postgres."""

    def __init__(self, store):
        self._store = store
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        sql_l = sql.lower()
        if "insert into cluster_feedback" in sql_l:
            self._store[(params["user_id"], params["cluster_id"])] = params["vote"]
        elif "delete from cluster_feedback" in sql_l:
            self._store.pop((params["user_id"], params["cluster_id"]), None)
        elif "select cluster_id, vote from cluster_feedback" in sql_l:
            self._result = [
                {"cluster_id": cluster_id, "vote": vote}
                for (user_id, cluster_id), vote in self._store.items()
                if user_id == params["user_id"]
            ]
        elif "select cluster_id from cluster_feedback" in sql_l:
            # Phase 7.1 "liked" query - dict insertion order stands in for `created_at desc`
            # (most recently liked last-in), so tests seed feedback_store in like order.
            liked = [
                cluster_id
                for (user_id, cluster_id), vote in reversed(list(self._store.items()))
                if user_id == params["user_id"] and vote == 1
            ]
            offset = params["offset"]
            self._result = [{"cluster_id": cid} for cid in liked[offset : offset + params["limit"]]]
        else:
            raise AssertionError(f"FakeFeedbackCursor doesn't understand: {sql!r}")

    def fetchall(self):
        return self._result or []


class FakeFeedbackConnection:
    def __init__(self, store):
        self._store = store

    def cursor(self):
        return FakeFeedbackCursor(self._store)

    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.fixture
def make_feedback_client():
    """Returns a factory: make_feedback_client(ch_responses=[...], feedback_store={...}) ->
    (TestClient, fake_clickhouse, feedback_store) - wires both ClickHouse and an in-memory
    cluster_feedback table (Phase 7) so ranking/feedback endpoint tests can run without a real
    database. Use login_as() below to attach a valid session cookie."""

    def _make(ch_responses=None, feedback_store=None):
        ch_fake = FakeClickHouseClient(ch_responses or [])
        store = feedback_store if feedback_store is not None else {}
        app.dependency_overrides[get_clickhouse_client] = lambda: ch_fake
        app.dependency_overrides[get_postgres_connection] = lambda: FakeFeedbackConnection(store)
        return TestClient(app), ch_fake, store

    yield _make
    app.dependency_overrides.pop(get_clickhouse_client, None)
    app.dependency_overrides.pop(get_postgres_connection, None)


def login_as(client, user_id=1, email="user@example.com"):
    """Mints a real, valid session cookie (via the real JWT code path in auth.py) and attaches
    it to `client` - lets feedback/list-ranking tests exercise a "logged in" request without
    going through /auth/login."""
    from auth import create_access_token

    token = create_access_token(user_id=user_id, email=email, secret=os.environ["JWT_SECRET"])
    client.cookies.set("access_token", token)
