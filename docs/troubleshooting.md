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
