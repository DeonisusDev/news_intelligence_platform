"""Applies the fresh-install ClickHouse DDL (sql/clickhouse/001-004) to a clean instance, e.g.
the `services:` container CI spins up for the `dbt build` job. Migration scripts (005+) are
deliberately excluded - they assume an existing pre-rename schema that a fresh CI instance never
has (see docs/troubleshooting.md's "dbt incremental models don't auto-migrate" entry for why
002-004 already reflect the current column names).

ClickHouse's HTTP interface rejects multi-statement bodies, so each file's statements are split
on `;` and sent one at a time - the same reason clustering_io.py/postgres_io.py never need to
worry about this (they only ever send single statements).
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

DDL_FILES = [
    "sql/clickhouse/001_create_databases.sql",
    "sql/clickhouse/002_create_raw_articles.sql",
    "sql/clickhouse/003_create_article_clusters.sql",
    "sql/clickhouse/004_create_summary_clusters.sql",
]


def _strip_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))


def main() -> None:
    host = os.environ.get("CLICKHOUSE_HOST", "localhost")
    port = os.environ.get("CLICKHOUSE_PORT", "8123")
    user = os.environ.get("CLICKHOUSE_USER", "default")
    password = os.environ.get("CLICKHOUSE_PASSWORD", "")
    url = f"http://{host}:{port}/?user={user}&password={password}"

    for path in DDL_FILES:
        with open(path) as f:
            content = _strip_comments(f.read())
        statements = [s.strip() for s in content.split(";") if s.strip()]
        for statement in statements:
            request = urllib.request.Request(url, data=statement.encode(), method="POST")
            try:
                urllib.request.urlopen(request)
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"Failed applying {path}: {exc.read().decode()}") from exc
        print(f"Applied {path} ({len(statements)} statements)")


if __name__ == "__main__":
    main()
