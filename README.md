# News Intelligence Platform

[![CI](https://github.com/DeonisusDev/news_intelligence_platform/actions/workflows/ci.yml/badge.svg)](https://github.com/DeonisusDev/news_intelligence_platform/actions/workflows/ci.yml)

A daily ETL/ELT pipeline that ingests news articles, lands them immutably, transforms them through
a layered warehouse, enriches them with an LLM, and serves the result through an API. Built as a
Data Engineering portfolio project — the LLM step is one stage in the pipeline, not the point of it.

```
NewsAPI.org + GNews.io (top headlines, all categories) → Airflow (daily DAG)
   → MinIO (raw JSON) → Postgres (raw, idempotent)
   → dbt-clickhouse (stage → ods → mart) → ClickHouse
   → article clustering (same story, many outlets, either provider) → LLM enrichment
   → summary_clusters (ClickHouse) → FastAPI
```

See `docs/architecture.md` for a diagram and `docs/adr/` for the reasoning behind the key
architectural decisions (why LocalExecutor, why ClickHouse, the LLM provider abstraction, the
dedup/idempotency key, why enrichment runs per story-cluster rather than per article, why
ingestion pulls top-headlines across categories from two providers).

## Status

Under active build-out. Current phase: **Phase 5 — CI, docs polish**.

- [x] Phase 0 — docker-compose skeleton, all services healthy (verified: Postgres with `airflow`+`newsdata` DBs, MinIO bucket, ClickHouse `/ping`, Airflow `/api/v2/monitor/health`, FastAPI `/health`)
- [x] Phase 1 — ingestion DAG (NewsAPI → MinIO → Postgres raw). Verified end-to-end against the real NewsAPI: 153 articles fetched, 136 new rows landed, dedup + idempotency confirmed by rerunning the DAG (second run: 153/153 correctly detected as duplicates, row count unchanged).
- [x] Ingestion pivot — switched NewsAPI to `/v2/top-headlines` across all categories (was keyword search) and added GNews.io as a second top-headlines provider; `raw_articles` gained `category`/`source_provider` columns. See `docs/adr/0006-top-headlines-multi-source.md`. Verified end-to-end: both providers fetched successfully (NewsAPI across 7 categories, GNews across 9, gracefully absorbing free-tier 429s on individual categories), `dbt build` green (17/17) after migrating the `ods`/`mart` layers to the new columns, clustering + LLM enrichment ran clean over the resulting 380 clusters (605 total after two runs, 0 failures). Also fixed a real bug surfaced by the larger, more varied article volume: `groupArray` silently dropping NULL `description`s desynced per-cluster article arrays for ~4% of clusters (see `docs/troubleshooting.md`).
- [x] Phase 2 — dbt-clickhouse (stage → ods → mart), Postgres → ClickHouse raw via the `postgresql()` table function. Verified end-to-end: `dbt build` green (17/17, incl. `unique`/`not_null` on `url_hash`), full DAG run populates `raw`/`ods`/`mart` consistently (56/56/56 rows), idempotency confirmed by rerunning the DAG (0 new rows copied into ClickHouse, all layer counts unchanged).
- [x] Phase 3 — article clustering (title-token similarity, no LLM) → LLM enrichment → `summary_clusters`. Verified end-to-end against the real OpenRouter API: 159 clusters summarized (0 failures), confirmed clustering correctly groups the same story across outlets (e.g. Forbes + its Biztoc.com syndication landed in one cluster). Idempotency confirmed by rerunning the DAG after new articles arrived: only the 66 genuinely new clusters were processed, all 159 previously-summarized clusters were skipped and their `cluster_id`s stayed stable.
- [x] Phase 4 — FastAPI serving layer. Discovery-feed shaped: `GET /discover` (paginated summary cards, optional `topic` filter), `GET /discover/{cluster_id}` (card + full source-article list, 404 on unknown id), `GET /stats/daily`, `GET /stats/topics`, `GET /pipeline/runs` (Postgres `pipeline_run_log`, independent of the Airflow UI). Verified against the live stack: all endpoints return real joined data, `/docs` Swagger UI works, 404 path confirmed, detail endpoint spot-checked against the corrected Forbes/Biztoc.com cluster (`article_count: 2`, both sources listed correctly).
- [ ] Phase 5 — CI, docs polish. `.github/workflows/ci.yml` added: `lint` (`ruff check` + `black --check`, both clean locally), `dbt-build` (spins up a real ClickHouse service container, applies the fresh-install DDL, runs a genuine `dbt build` - verified locally: 17/17 green against an empty instance), `compose-smoke` (`docker compose config -q` + `docker compose up --wait` against every documented health endpoint). Architecture diagram and sample API calls added to this README. Not yet confirmed green on GitHub Actions itself (no `gh` CLI / API access from this environment) - check the badge/Actions tab after this pushes.

## Prerequisites

- Docker + Docker Compose
- **≥8GB RAM available to Docker.** Airflow 3.x runs 4 separate components (api-server,
  scheduler, dag-processor, triggerer) alongside Postgres, ClickHouse, MinIO, and FastAPI. On a
  constrained machine, close other memory-heavy applications before `docker compose up`.
- A free [NewsAPI.org](https://newsapi.org) API key
- A free [GNews.io](https://gnews.io) API key (optional - ingestion runs fine without it, just
  skips that provider)
- A free [OpenRouter](https://openrouter.ai) API key (for LLM enrichment)

## Setup

```bash
cp .env.example .env
# fill in NEWSAPI_API_KEY, OPENROUTER_API_KEY (GNEWS_API_KEY is optional)
# generate a Fernet key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

make up      # docker compose up -d --build
make ps      # check all services are healthy
```

- Airflow UI: http://localhost:8080 (SimpleAuthManager, all-admins mode — no login required; dev-only setting, see `docker-compose.yml`)
- MinIO console: http://localhost:9001 (credentials from `.env`)
- Airflow health check: http://localhost:8080/api/v2/monitor/health
- ClickHouse HTTP: http://localhost:8123/ping
- FastAPI: http://localhost:8000/docs — `GET /discover`, `GET /discover/{cluster_id}`,
  `GET /stats/daily`, `GET /stats/topics`, `GET /pipeline/runs`

## Sample API calls

```bash
# Discovery feed - one card per story-cluster, newest first
curl "http://localhost:8000/discover?limit=5"

# Same feed, filtered to one topic
curl "http://localhost:8000/discover?topic=Technology&limit=5"

# Expand a card into its individual source articles
curl "http://localhost:8000/discover/<cluster_id>"

# Article volume by day/source, and cluster counts by topic
curl "http://localhost:8000/stats/daily?limit=10"
curl "http://localhost:8000/stats/topics"

# Ingestion run history (independent of the Airflow UI)
curl "http://localhost:8000/pipeline/runs?limit=10"
```

## Known limitations

- **NewsAPI free tier**: 100 requests/day (shared across dev + testing), articles delayed ~24h,
  `content` field truncated to ~260 characters, ToS restricts use to dev/test — not a production
  data source, and the ingestion DAG budgets its request count accordingly.
- **GNews free tier**: 100 requests/day, max 10 articles per request, and pagination is a
  paid-only feature — `gnews_client.py` makes exactly one request per category, no page loop.
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
