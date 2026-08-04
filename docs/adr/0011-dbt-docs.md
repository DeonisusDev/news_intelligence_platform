# ADR 0011: dbt docs as a CI artifact, not a public deploy

## Status
Accepted

## Context
Phase 8 is the data-catalog phase: real column-level descriptions across `stage`/`ods`/`mart`
(previously mostly table-level docs, plus columns that happened to have a test attached), and a
way to actually generate and browse `dbt docs`. The plan explicitly left "optionally a CI
artifact upload" as the only deploy option on the table - not a public hosted site.

## Decision
**Every column on every model gets a real `description:`**, not just the ones with a `unique`/
`not_null` test - `_stage__models.yml`, `_ods__models.yml`, `_mart__models.yml`, and (for a
complete lineage root) `_stage__sources.yml`'s `raw.newsapi_articles`. Descriptions explain the
column's *provenance and caveats* (e.g. "NewsAPI only populates source_id for a small set of
top sources - most articles have a null id"), not just restate the column name, since that's the
information someone unfamiliar with this pipeline would actually need before querying it.

**`make dbt-docs` runs `dbt docs generate` inside the `airflow-scheduler` container and copies
the artifacts out to `dbt/target/` (gitignored) for local serving**, rather than trying to run
`dbt docs serve` inside the container itself. `dbt/` is bind-mounted from the host (host-owned),
but the container runs as `AIRFLOW_UID` (50000) and can't write under a host-owned directory -
the same constraint the DAG's own `dbt_run` task already works around with `--target-path
/tmp/dbt_target` (see `dbt_project.yml`'s comment). `dbt docs serve` also has no port exposed
from that container, and generated docs are just static files (`index.html` + `manifest.json` +
`catalog.json`) - any static file server works, so `python3 -m http.server` on the host is
simpler than adding a permanent port mapping for an on-demand dev tool.

**CI (`dbt-build` job) runs `dbt docs generate` right after `dbt build`, against the same
already-populated ClickHouse service container, and uploads the result as a GitHub Actions
artifact** (`actions/upload-artifact`, 14-day retention) - not a public GitHub Pages deploy.
Running it against the real (if CI-ephemeral) ClickHouse means `catalog.json` reflects genuine
column types from the warehouse, not just what the manifest's config says - a stronger check
than `dbt docs generate` alone would be if it only compiled without querying anything. A public
deploy is unnecessary for a portfolio project's CI and adds hosting/access-control surface for
no real benefit here.

## Consequences
- Verified against the live stack, not just `dbt parse`: `make dbt-docs` generated real docs
  (`dbt docs generate` output: "Found 5 models, 12 data tests, 1 source, 522 macros" /
  "Catalog written to /tmp/dbt_target/catalog.json"), served locally, and inspected in a real
  (headless) browser - `mart_articles`'s page shows every column with its real ClickHouse type
  (from the live catalog) and its new description, `Referenced By`/`Depends On` correctly list
  `mart_daily_stats` and `dim_source`/`ods_articles`, and the lineage graph panel correctly draws
  `ods_articles -> dim_source -> mart_articles -> mart_daily_stats`. A full `dbt build` was also
  re-run afterward to confirm the `.yml` changes didn't disturb any of the 12 existing data tests
  (17/17 still green).
