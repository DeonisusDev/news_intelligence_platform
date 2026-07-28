# Troubleshooting notes

Non-obvious issues hit while building this project, kept here so they don't have to be
rediscovered. Most are specific to Airflow 3.x's new architecture (separate api-server,
dag-processor, triggerer; tasks talk to the API server over HTTP instead of hitting the
metadata DB directly).

## Shared code belongs in `dags/`, not `plugins/`

Airflow's plugin manager recursively tries to `import` every `.py` file under `plugins/` as a
standalone module (it's meant for `AirflowPlugin` subclasses - custom operators/hooks/macros).
A regular Python package with relative imports (`from .foo import bar`) breaks under that loader
with `ImportError: attempted relative import with no known parent package`, even though the DAG
itself still works (DAG files import the package via `sys.path`, which includes `dags/` too).

Fix: put shared library code in `airflow/dags/news_pipeline/` instead of `airflow/plugins/`. The
dag-processor only looks for top-level `DAG` objects there and ignores everything else - no
auto-import side effects.

## Airflow 3's real health check path is `/api/v2/monitor/health`

`/health` still exists but returns a `404` with a message pointing at the new path. Use
`/api/v2/monitor/health` for the `airflow-apiserver` healthcheck and any manual curl checks.

## LocalExecutor needs an explicit `execution_api_server_url`

Airflow 3 tasks run in a subprocess supervised by the scheduler, but that supervisor talks to
the **api-server** over HTTP (not the DB directly) to report task start/heartbeat/state. The
config key `LocalExecutor` actually reads is `[core] execution_api_server_url`
(`AIRFLOW__CORE__EXECUTION_API_SERVER_URL`) - **not** `[execution_api] execution_api_server_url`,
which is a different, unrelated key. Left unset, it defaults to `http://localhost:8080/execution/`,
which is wrong across containers and fails with `httpcore.ConnectError: Connection refused`.

Set it explicitly to the `airflow-apiserver` service:
```
AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://airflow-apiserver:8080/execution/
```

## `secret_key` / `jwt_secret` must be identical across every Airflow container

The scheduler signs a JWT per task so its supervisor can authenticate to the api-server's
execution API; the api-server verifies that JWT with the same secret. If left unset, Airflow
generates a random value **per process**, so the scheduler and api-server end up with different
secrets and every task fails with `403 Forbidden` on the very first callback
(`PATCH /execution/task-instances/{id}/run`) - after connectivity is otherwise fine.

Fix: set `AIRFLOW__API__SECRET_KEY` and `AIRFLOW__API_AUTH__JWT_SECRET` explicitly via `.env`,
shared by every Airflow service in `docker-compose.yml`.

## `context["ds"]` doesn't exist for manual triggers without a schedule tie-in

In Airflow 3, `airflow dags trigger` (no explicit logical date) produces a run with
`logical_date=None` and no data interval - it isn't tied to the DAG's schedule. Template context
keys derived from `logical_date` (like `ds`) are simply absent in that case, raising `KeyError`.

Fix: derive dates defensively - `context.get("logical_date") or datetime.now(timezone.utc)` -
rather than indexing `context["ds"]`/`context["logical_date"]` directly. This matters for any
code that also has to work under `catchup=False` scheduled runs (where `logical_date` **is**
populated) as well as ad-hoc manual triggers.

## dbt can't write `logs/`/`target/` under a bind-mounted project dir

`./dbt:/opt/airflow/dbt` is a bind mount from the host, owned by the host user (uid 1000 here).
Airflow's containers run as `AIRFLOW_UID` (50000, per the upstream-recommended default) with
group 0 - neither matches the host directory's owner or group, so dbt's default
`mkdir -p dbt/logs` / `dbt/target` fails with `PermissionError: [Errno 13] Permission denied`.
The dbt CLI swallows this particular failure almost silently (`dbt debug` just exits 2 with no
stdout/stderr) - the only way to see the real traceback was invoking `dbtRunner` directly from a
Python shell instead of the `dbt` entrypoint script.

Fix: point dbt's run artifacts at the container's own filesystem instead of the bind mount, via
the `--log-path`/`--target-path` CLI flags (e.g. `/tmp/dbt_logs`, `/tmp/dbt_target`) - `models/`
still comes from the host bind mount, only the ephemeral run output moves. (Setting these as
`log-path`/`target-path` keys in `dbt_project.yml` also works but is deprecated in dbt 1.12+.)

## dbt `incremental` models don't auto-migrate their physical schema

Renaming/adding a column in an upstream model's `select *` doesn't reach a downstream
`materialized='incremental'` model's actual ClickHouse table - dbt's incremental strategies
(`delete+insert` here) `INSERT INTO` the *existing* table, so a column the existing table
doesn't have yet causes `DB::Exception: Unknown expression identifier 'old_column_name'`
(the new SELECT no longer produces it) the next time the model runs. This bit `ods_articles`
after renaming `query_keyword` -> `category` in `stg_articles.sql` - `mart_articles` (materialized
as `table`, a full drop-and-recreate every run) picked up the new column automatically, but
`ods_articles` didn't.

Fix: `ALTER TABLE ... RENAME COLUMN` / `ADD COLUMN` the existing incremental table by hand to
match the new upstream shape (see `sql/clickhouse/migrations/005_migrate_category_provider.sql`)
- or, if the data is fully disposable, drop the table and let dbt do a full rebuild on the next
run.

## Migration scripts under `docker-entrypoint-initdb.d` also run on a *fresh* install

Postgres's and ClickHouse's official images run every `*.sql` file directly inside
`/docker-entrypoint-initdb.d/` on first container start against an empty volume - `docker-compose.yml`
mounts the whole `sql/postgres/`/`sql/clickhouse/` directory there, so a migration script meant
only for *already-running* deployments (e.g. `RENAME COLUMN query_keyword TO category`) ran on
every fresh install too, and failed immediately (`column "query_keyword" does not exist` /
`Cannot find column to rename`) since the fresh-install DDL already creates the new column
directly. This broke `docker compose up` from a clean volume for anyone who'd never run the
pipeline before - caught by the Phase 5 CI `compose-smoke` job, not by hand-testing (which only
ever ran against volumes that already existed from earlier phases).

Fix: both engines' init entrypoints only scan the *top level* of `/docker-entrypoint-initdb.d/`,
not subdirectories (confirmed empirically) - moving migration-only scripts into
`sql/postgres/migrations/` and `sql/clickhouse/migrations/` keeps them out of the auto-run path
while still shipping in the same mounted directory tree for manual application.

## ClickHouse's `groupArray` silently drops NULLs, desyncing parallel arrays

`groupArray(a.title)`, `groupArray(a.description)`, `groupArray(a.source_name)` computed
side-by-side in one `GROUP BY` look like they'd zip back up positionally, but `groupArray` on a
`Nullable(String)` column skips NULL values entirely - so if even one row in the group has a NULL
`description`, that array comes back shorter than `titles`/`sources`, and zipping them in Python
silently truncates to the shortest array (occasionally to *zero* elements, discarding the whole
group). This broke `enrichment_io.py`'s per-cluster article gathering for ~4% of clusters
(any cluster containing an article with a NULL field), producing "successful" LLM summaries
generated from zero actual articles.

Fix: `groupArray((a.title, a.description, a.source_name))` - group the columns as one tuple per
row instead of three separate arrays. `groupArray` never drops a NULL that's *inside* a tuple,
only bare NULL scalars, so tuples keep their 1:1 correspondence to source rows.

## Forgetting `FINAL` on `article_clusters` double-counted articles mid-session

`enrichment_io.py`'s pending-clusters query joined `mart.article_clusters` without `FINAL`, even
though it's a `ReplacingMergeTree` like every other table in this pipeline that needs it
(`raw.newsapi_articles`, `ods_articles`, ...). Re-running `cluster_articles` more than once in a
short window (e.g. while debugging) leaves multiple un-merged versions of the same `url_hash`
physically present until ClickHouse's background merge catches up - querying without `FINAL`
during that window silently doubled some clusters' member arrays, inflating `article_count` and
feeding the LLM the same article twice in one prompt. Found by spot-checking a cluster's actual
member articles in DBeaver and noticing `article_count` didn't match the real row count.

Fix: add `final` after the table alias (`from mart.article_clusters c final`) like everywhere
else. 127 already-affected `summary_clusters` rows (verified via `uniqExact(url_hash)` against
the `FINAL`-deduped join not matching the stored `article_count`) were deleted and re-enriched
rather than patched in place - cheap on a free LLM tier and consistent with ADR 0005's existing
"stale cluster row -> delete and rerun" recovery pattern.
