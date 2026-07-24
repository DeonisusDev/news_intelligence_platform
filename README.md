# News Intelligence Platform

A daily ETL/ELT pipeline that ingests news articles, lands them immutably, transforms them through
a layered warehouse, enriches them with an LLM, and serves the result through an API. Built as a
Data Engineering portfolio project — the LLM step is one stage in the pipeline, not the point of it.

```
NewsAPI.org → Airflow (daily DAG) → MinIO (raw JSON) → Postgres (raw, idempotent)
   → dbt-clickhouse (stage → ods → mart) → ClickHouse
   → LLM enrichment → summary_articles (ClickHouse) → FastAPI
```

See `docs/architecture.md` for a diagram and `docs/adr/` for the reasoning behind the key
architectural decisions (why LocalExecutor, why ClickHouse, the LLM provider abstraction, the
dedup/idempotency key).

## Status

Under active build-out. Current phase: **Phase 2 — dbt-clickhouse**.

- [x] Phase 0 — docker-compose skeleton, all services healthy (verified: Postgres with `airflow`+`newsdata` DBs, MinIO bucket, ClickHouse `/ping`, Airflow `/api/v2/monitor/health`, FastAPI `/health`)
- [x] Phase 1 — ingestion DAG (NewsAPI → MinIO → Postgres raw). Verified end-to-end against the real NewsAPI: 153 articles fetched, 136 new rows landed, dedup + idempotency confirmed by rerunning the DAG (second run: 153/153 correctly detected as duplicates, row count unchanged).
- [ ] Phase 2 — dbt-clickhouse (stage/ods/mart)
- [ ] Phase 3 — LLM enrichment → `summary_articles`
- [ ] Phase 4 — FastAPI serving layer
- [ ] Phase 5 — CI, docs polish

## Prerequisites

- Docker + Docker Compose
- **≥8GB RAM available to Docker.** Airflow 3.x runs 4 separate components (api-server,
  scheduler, dag-processor, triggerer) alongside Postgres, ClickHouse, MinIO, and FastAPI. On a
  constrained machine, close other memory-heavy applications before `docker compose up`.
- A free [NewsAPI.org](https://newsapi.org) API key
- A free [OpenRouter](https://openrouter.ai) API key (for LLM enrichment)

## Setup

```bash
cp .env.example .env
# fill in NEWSAPI_API_KEY, OPENROUTER_API_KEY
# generate a Fernet key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

make up      # docker compose up -d --build
make ps      # check all services are healthy
```

- Airflow UI: http://localhost:8080 (SimpleAuthManager, all-admins mode — no login required; dev-only setting, see `docker-compose.yml`)
- MinIO console: http://localhost:9001 (credentials from `.env`)
- Airflow health check: http://localhost:8080/api/v2/monitor/health
- ClickHouse HTTP: http://localhost:8123/ping
- FastAPI: http://localhost:8000/docs (available from Phase 4 onward)

## Known limitations

- **NewsAPI free tier**: 100 requests/day (shared across dev + testing), articles delayed ~24h,
  `content` field truncated to ~260 characters, ToS restricts use to dev/test — not a production
  data source, and the ingestion DAG budgets its request count accordingly.
- **Free OpenRouter models**: response quality and structured-output support are inconsistent;
  the enrichment client validates and retries rather than trusting the model unconditionally.
- **ClickHouse at this data volume** (hundreds of articles/day) is a deliberate choice to
  demonstrate OLAP modeling, not a scale requirement — see `docs/adr/0002-clickhouse-for-olap.md`.

## Repository layout

```
airflow/     Airflow image, DAGs, plugins (NewsAPI client, dedup, MinIO/Postgres/ClickHouse I/O, LLM client, audit log)
dbt/         dbt-clickhouse project: stage → ods → mart
fastapi_app/ Serving API over ClickHouse (articles, stats) and Postgres (pipeline run history)
sql/         Hand-written DDL for Postgres and ClickHouse init tables
docs/        Architecture diagram + ADRs
```
