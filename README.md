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
   → summary_clusters (ClickHouse) → FastAPI → React SPA (frontend/)
```

See `docs/architecture.md` for a diagram and `docs/adr/` for the reasoning behind the key
architectural decisions (why LocalExecutor, why ClickHouse, the LLM provider abstraction, the
dedup/idempotency key, why enrichment runs per story-cluster rather than per article, why
ingestion pulls top-headlines across categories from two providers).

## Status

Phases 0-5 complete, plus a post-Phase-5 unit test suite, Phase 6 (web frontend), Phase 6.1
(rich event detail), Phase 6.5 (user accounts), Phase 7 (recommendations), and Phase 8 (data
catalog). See `docs/adr/` and `docs/troubleshooting.md` for the reasoning and real bugs hit along
the way. Remaining phases (9-13) are sketched in the plan's future-phases section - operational
maturity, embeddings, and beyond.

- [x] Phase 0 — docker-compose skeleton, all services healthy (verified: Postgres with `airflow`+`newsdata` DBs, MinIO bucket, ClickHouse `/ping`, Airflow `/api/v2/monitor/health`, FastAPI `/health`)
- [x] Phase 1 — ingestion DAG (NewsAPI → MinIO → Postgres raw). Verified end-to-end against the real NewsAPI: 153 articles fetched, 136 new rows landed, dedup + idempotency confirmed by rerunning the DAG (second run: 153/153 correctly detected as duplicates, row count unchanged).
- [x] Ingestion pivot — switched NewsAPI to `/v2/top-headlines` across all categories (was keyword search) and added GNews.io as a second top-headlines provider; `raw_articles` gained `category`/`source_provider` columns. See `docs/adr/0006-top-headlines-multi-source.md`. Verified end-to-end: both providers fetched successfully (NewsAPI across 7 categories, GNews across 9, gracefully absorbing free-tier 429s on individual categories), `dbt build` green (17/17) after migrating the `ods`/`mart` layers to the new columns, clustering + LLM enrichment ran clean over the resulting 380 clusters (605 total after two runs, 0 failures). Also fixed a real bug surfaced by the larger, more varied article volume: `groupArray` silently dropping NULL `description`s desynced per-cluster article arrays for ~4% of clusters (see `docs/troubleshooting.md`).
- [x] Phase 2 — dbt-clickhouse (stage → ods → mart), Postgres → ClickHouse raw via the `postgresql()` table function. Verified end-to-end: `dbt build` green (17/17, incl. `unique`/`not_null` on `url_hash`), full DAG run populates `raw`/`ods`/`mart` consistently (56/56/56 rows), idempotency confirmed by rerunning the DAG (0 new rows copied into ClickHouse, all layer counts unchanged).
- [x] Phase 3 — article clustering (title-token similarity, no LLM) → LLM enrichment → `summary_clusters`. Verified end-to-end against the real OpenRouter API: 159 clusters summarized (0 failures), confirmed clustering correctly groups the same story across outlets (e.g. Forbes + its Biztoc.com syndication landed in one cluster). Idempotency confirmed by rerunning the DAG after new articles arrived: only the 66 genuinely new clusters were processed, all 159 previously-summarized clusters were skipped and their `cluster_id`s stayed stable.
- [x] Phase 4 — FastAPI serving layer. Discovery-feed shaped: `GET /discover` (paginated summary cards, optional `topic` filter), `GET /discover/{cluster_id}` (card + full source-article list, 404 on unknown id), `GET /stats/daily`, `GET /stats/topics`, `GET /pipeline/runs` (Postgres `pipeline_run_log`, independent of the Airflow UI). Verified against the live stack: all endpoints return real joined data, `/docs` Swagger UI works, 404 path confirmed, detail endpoint spot-checked against the corrected Forbes/Biztoc.com cluster (`article_count: 2`, both sources listed correctly).
- [x] Phase 5 — CI, docs polish. `.github/workflows/ci.yml`: `lint` (`ruff check` + `black --check`), `test` (66 unit tests over `news_pipeline` + `fastapi_app`, no Airflow/real DB needed), `dbt-build` (real ClickHouse service container, fresh-install DDL, genuine `dbt build`, not just compile), `compose-smoke` (`docker compose config -q` + `up -d` + a health-endpoint poll loop). All four green on GitHub Actions. Getting there caught two real, previously-unnoticed bugs: migration scripts living directly under `sql/postgres|clickhouse/` were auto-executed by `docker-entrypoint-initdb.d` on a *fresh* install too (breaking `docker compose up` from a clean volume for anyone who'd never run the pipeline before - fixed by moving them into `migrations/` subdirectories, which both engines' init entrypoints don't scan), and `docker compose up --wait` failing on `minio-createbuckets`, a legitimate one-shot job (see `docs/troubleshooting.md` for both). Architecture diagram and sample API calls added to this README.
- [x] Post-Phase-5 — unit test suite. `tests/`: `news_pipeline` (dedup, clustering, LLM response parsing, Postgres upsert/field-normalization) and `fastapi_app` (every endpoint via `TestClient` + dependency overrides). Required a small, behavior-preserving refactor - `compute_clusters`/`enrich_pending_clusters`/`upsert_articles` each gained an injectable `client`/`conn` parameter so their Airflow-hook imports could move inside the function body, making the modules importable (and their logic testable) without `apache-airflow` installed.
- [x] Phase 6 — web frontend. `frontend/`: Vite + React + TypeScript + Tailwind + shadcn/ui SPA served by nginx. One card per story-cluster (hero image, TL;DR, topic + heuristic consensus badges), infinite-scroll feed (TanStack Query), click-to-expand source list (Dialog), topic filter tucked behind a dropdown (styled after Perplexity Discover's own layout), dark mode. FastAPI gained CORS middleware and `GET /discover` gained `first_published_at`/`image_url` per card. See `docs/adr/0007-frontend-spa.md`. Verified against the live stack in a real (headless) browser: real data end-to-end, dialog expand, dark mode + persistence, mobile-width layout, infinite scroll (20→100 cards over repeated scrolls), topic filter, zero console errors.
- [x] Phase 6.1 — rich event detail. Same enrichment LLM call (not a second round-trip) now also returns Key Facts (organizations/locations/people), an AI Analysis ("why it matters" + an optional before/after comparison), a Consensus/Disagreement breakdown across sources, and per-source "what this outlet focused on" mini-summaries (matched by `url_hash`, not source name, so it stays correct even when several sources share a name). New `summary_clusters` columns (see `sql/clickhouse/migrations/006_...`); `GET /discover/{cluster_id}` and the detail dialog both extended; the "Impact" star-ratings idea from the same product discussion was explicitly dropped as unverifiable. See `docs/adr/0008-rich-event-detail.md`. Verified against a real 45-cluster backfill (all existing multi-source clusters + a random sample of single-source ones, re-enriched via the same delete-and-rerun pattern as the earlier `FINAL` bug fix): spot-checked in a real browser, including a case where 3 sources share the exact same name (url_hash-keyed matching confirmed correct) and a case with genuine cross-outlet disagreement.
- [x] Phase 6.5 — user accounts. New Postgres `users` table (`sql/postgres/004_create_users.sql`); `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` (bcrypt-hashed passwords, a 24h JWT set as an httpOnly cookie - the frontend never touches the token directly). Deliberately out of scope: email verification, password reset, OAuth - see `docs/adr/0009-user-accounts.md`. `AuthDialog` in the frontend header toggles between login/register; the header shows the logged-in email + a logout button once authenticated. Verified against the live stack: register/duplicate-email 409/wrong-password 401/`/auth/me` 401-then-200/logout all confirmed via real `curl` calls, then the same flow end-to-end through the real UI in a headless browser (including dark mode and the inline error state), zero console errors.
- [x] Phase 7 — recommendations (thumbs up/down). New Postgres `cluster_feedback` table (`sql/postgres/005_create_cluster_feedback.sql`); `POST`/`DELETE /discover/{cluster_id}/feedback` (upsert/un-vote, requires login). `GET /discover` re-ranks a bounded recency-ordered candidate window by content-based affinity (topic/keyword overlap with the user's previously-liked clusters, blended with recency via a stable sort) for logged-in users only - anonymous requests take the exact pre-Phase-7 code path. Ranking itself is a pure, DB-free function (`fastapi_app/ranking.py`) - not collaborative filtering or embeddings, deliberately - see `docs/adr/0010-recommendations.md`. Thumbs up/down buttons on each `SummaryCard`, visible only when logged in. Verified against the live stack: a real scripted vote measurably reordered the logged-in feed (a Business-topic cluster jumped from position 9 to position 1, pulling every other Business cluster in the window up with it) while the anonymous feed stayed untouched; confirmed again through the real UI in a headless browser (toggle up→down→un-vote, dark mode, zero console errors) - which caught and fixed a real bug along the way (a pre-Phase-7 fetch call was missing `credentials: "include"`, silently dropping the session cookie).
- [x] Phase 8 — data catalog. Real column-level `description:` for every column across `stage`/`ods`/`mart` (and the `raw` source), not just the ones with a test attached. `make dbt-docs` generates the catalog inside the `airflow-scheduler` container and copies it to `dbt/target/` (gitignored) for local serving (`dbt/` is host-owned, the container can't write there directly - same constraint as the DAG's own `dbt_run` task). CI's `dbt-build` job also runs `dbt docs generate` against the same live ClickHouse service container and uploads the result as a 14-day GitHub Actions artifact, not a public deploy - see `docs/adr/0011-dbt-docs.md`. Verified against the live stack in a real (headless) browser: `mart_articles`'s page shows every column's real ClickHouse type (from the live catalog) and its new description, and the lineage graph panel correctly draws `ods_articles → dim_source → mart_articles → mart_daily_stats`. A full `dbt build` re-run afterward confirmed all 12 existing data tests still pass (17/17 green).

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

- Frontend: http://localhost:3000 — the Discovery-style feed
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
frontend/    Vite + React + TypeScript SPA (Discovery-style feed) served by nginx
sql/         Hand-written DDL for Postgres and ClickHouse init tables
docs/        Architecture diagram + ADRs
tests/       Unit tests for news_pipeline (dedup, clustering, LLM parsing, Postgres upsert) and
             fastapi_app (endpoint tests via TestClient + dependency overrides) - `pytest -v`,
             no Airflow/real DB required (see requirements-dev.txt)
```
