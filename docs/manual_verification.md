# Manual verification guide (Phase 0 + Phase 1)

Step-by-step checks you can run yourself to confirm everything that's been built so far
actually works. Written to be followed top to bottom on a fresh terminal.

## 0. Prerequisites

- Docker + Docker Compose installed and running.
- `.env` present in the project root (copy from `.env.example` if you don't have one) with
  `NEWSAPI_API_KEY` filled in. Everything else can keep its example defaults for local testing.
- **Free up RAM before starting.** The full stack (Postgres, MinIO, ClickHouse, 4 Airflow
  containers, FastAPI) is tight on machines with less than ~8GB free. If containers restart
  unexpectedly or Airflow's API server becomes unresponsive, check `free -h` first - close
  Chrome tabs / heavy IDEs before retrying rather than assuming something is broken.

## 1. Bring the stack up

```bash
cd /home/deonisus/news_intelligence_platform
docker compose up -d --build
```

First run builds two custom images (Airflow with a baked-in dbt venv, ~2.2GB; FastAPI, ~200MB) -
expect this to take a few minutes. Subsequent runs are fast (cached layers).

**Check:** all containers should show `healthy` (a few, like the Airflow scheduler/dag-processor/
triggerer, don't have healthchecks defined and will just show `Up` - that's expected):

```bash
docker compose ps
```

You should see 8 services: `postgres`, `minio`, `minio-createbuckets` (this one exits after
running once - that's correct, not a crash), `clickhouse`, `airflow-apiserver`,
`airflow-scheduler`, `airflow-dag-processor`, `airflow-triggerer`, `fastapi`.

**Note:** the Airflow API server takes ~25-30 seconds after container start to become healthy
(it boots 4 uvicorn workers sequentially). Don't be alarmed if `docker compose ps` shows
`health: starting` for a little while.

## 2. Check each service directly

```bash
# Postgres - should return "accepting connections"
docker compose exec postgres pg_isready -U airflow

# Both databases should exist: airflow (Airflow's own metadata) and newsdata (our app data)
docker compose exec postgres psql -U airflow -l

# MinIO - should return "OK"
curl -s http://localhost:9000/minio/health/live -o /dev/null -w "%{http_code}\n"

# ClickHouse - should return "Ok."
curl -s http://localhost:8123/ping

# Airflow API server - should return a JSON block with 4 "healthy" components
# (metadatabase, scheduler, triggerer, dag_processor)
curl -s http://localhost:8080/api/v2/monitor/health | python3 -m json.tool

# FastAPI - should return {"status":"ok"}
curl -s http://localhost:8000/health
```

## 3. Browse the UIs

- **Airflow UI**: http://localhost:8080 — no login needed (SimpleAuthManager is configured in
  all-admins mode for local dev, see `docker-compose.yml` comment). You should see the
  `news_ingestion_pipeline` DAG listed.
- **MinIO console**: http://localhost:9001 — log in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`
  from your `.env` (defaults `minioadmin` / `minioadmin123`). You should see a bucket named
  `raw-news-data` (or whatever you set `MINIO_BUCKET` to).
- **FastAPI docs**: http://localhost:8000/docs — just the `/health` endpoint for now; the real
  API endpoints come in Phase 4.

## 4. Confirm the Postgres schema

```bash
docker compose exec postgres psql -U airflow -d newsdata -c "\dt"
```

Expect two tables: `raw_articles` and `pipeline_run_log`. Inspect their columns if curious:

```bash
docker compose exec postgres psql -U airflow -d newsdata -c "\d raw_articles"
docker compose exec postgres psql -U airflow -d newsdata -c "\d pipeline_run_log"
```

## 5. Run the ingestion DAG yourself

The DAG starts **paused** by default (Airflow's standard safety behavior). Unpause and trigger it:

```bash
docker compose exec airflow-scheduler airflow dags unpause news_ingestion_pipeline
docker compose exec airflow-scheduler airflow dags trigger news_ingestion_pipeline
```

Watch it run either in the Airflow UI (http://localhost:8080 → click into the DAG → Grid view),
or from the CLI:

```bash
docker compose exec airflow-scheduler airflow dags list-runs news_ingestion_pipeline
```

Wait until the newest run shows `state = success` (should take well under a minute). If it shows
`failed`, see the troubleshooting note at the bottom of this file for how to pull the real error.

## 6. Verify the data actually landed

**MinIO** — via the console (http://localhost:9001), browse into the `raw-news-data` bucket:
you should see a path like `raw/newsapi/dt=2026-07-24/run_id=.../articles.json` containing the
raw NewsAPI response payloads.

**Postgres** — check the row count and a few sample rows:

```bash
docker compose exec postgres psql -U airflow -d newsdata -c "SELECT count(*) FROM raw_articles;"
docker compose exec postgres psql -U airflow -d newsdata -c \
  "SELECT source_name, title, query_keyword, published_at FROM raw_articles ORDER BY fetched_at DESC LIMIT 5;"
```

**Pipeline run log** — this is the custom observability table, independent of Airflow's own UI:

```bash
docker compose exec postgres psql -U airflow -d newsdata -c \
  "SELECT run_id, task_id, status, rows_fetched, rows_new, rows_duplicate FROM pipeline_run_log ORDER BY id DESC LIMIT 10;"
```

You should see two rows per DAG run (one per task: `fetch_newsapi_articles`,
`load_raw_to_postgres`), each with `status = success`.

## 7. Prove idempotency and deduplication (the important part)

Trigger the DAG a second time:

```bash
docker compose exec airflow-scheduler airflow dags trigger news_ingestion_pipeline
```

Wait for it to finish (same as step 5), then re-run the `pipeline_run_log` query from step 6.
**Expected result:** the new run's `load_raw_to_postgres` row should show `rows_new = 0` and
`rows_duplicate` equal to `rows_fetched` (NewsAPI will very likely return the same top articles
again within a few minutes) - i.e. re-running the pipeline does **not** create duplicate rows.
Confirm the total count is unchanged:

```bash
docker compose exec postgres psql -U airflow -d newsdata -c "SELECT count(*) FROM raw_articles;"
```

This should match the count from step 6, not have grown by another full batch.

> Note: if enough real time passes between runs, NewsAPI may surface a handful of genuinely new
> articles published in between - a small `rows_new > 0` isn't a failure, it's correct behavior.
> The thing to watch for is that already-seen articles are **never** re-inserted or duplicated.

## 8. Tear down (optional)

```bash
docker compose down          # stop and remove containers, keep data volumes
docker compose down -v       # also wipe all data (Postgres/MinIO/ClickHouse volumes) - full reset
```

## If something fails: how to actually debug it

```bash
# Scheduler logs (LocalExecutor runs tasks in-process here, so failures show up in this log)
docker compose logs airflow-scheduler --tail=100

# The actual task log (more useful than scheduler logs for application-level bugs)
docker compose exec airflow-scheduler find /opt/airflow/logs -name "*.log" -newer /opt/airflow/airflow.cfg
# then:
docker compose exec airflow-scheduler cat "<path from above>"

# DAG import errors (if the DAG doesn't show up in the UI at all)
docker compose logs airflow-dag-processor --tail=50
```

See `docs/troubleshooting.md` for the specific Airflow 3 issues already hit and fixed during
development (health endpoint path, execution API auth, plugin loader gotcha, etc.) - if you hit
something that looks like one of those, it's already documented there.
