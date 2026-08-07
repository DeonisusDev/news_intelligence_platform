"""Daily ingestion DAG: NewsAPI.org + GNews.io (top headlines, all categories) -> MinIO
(raw JSON) -> Postgres (raw_articles) -> ClickHouse raw -> dbt build (stage -> ods -> mart)
-> article clustering -> LLM enrichment (one summary per story cluster, in summary_clusters).

Two independent providers feed the same raw_articles table (tagged by source_provider) so the
same real-world story is more likely to be caught by at least one of them - see
docs/adr/0006-top-headlines-multi-source.md. max_active_runs=1 keeps free-tier NewsAPI/GNews/LLM
quota bookkeeping trivial to reason about; there's no benefit to concurrent runs for a single
daily batch job (see docs/adr/0001).
"""

from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task
from airflow.providers.standard.operators.bash import BashOperator
from news_pipeline import (
    audit,
    clickhouse_io,
    clustering_io,
    config,
    enrichment_io,
    gnews_client,
    minio_io,
    newsapi_client,
    postgres_io,
)

MINIO_RAW_PREFIX = "raw/newsapi"
DBT_PROJECT_DIR = "/opt/airflow/dbt"
DBT_BIN = "/opt/airflow/dbt_venv/bin/dbt"


@dag(
    dag_id="news_ingestion_pipeline",
    description="NewsAPI+GNews top-headlines -> MinIO -> Postgres raw -> ClickHouse -> dbt -> "
    "clustering -> LLM enrichment",
    schedule="@daily",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,
    tags=["news-intelligence"],
)
def news_ingestion_pipeline():
    def _minio_key(context: dict, filename: str) -> str:
        run_id = context["run_id"]
        # "ds" isn't in context for manual triggers not tied to a schedule (Airflow 3
        # leaves logical_date/data_interval as None in that case).
        logical_date = context.get("logical_date") or datetime.now(timezone.utc)
        ds = logical_date.strftime("%Y-%m-%d")
        return f"{MINIO_RAW_PREFIX}/dt={ds}/run_id={run_id}/{filename}"

    @task
    def fetch_newsapi_articles(**context) -> dict:
        settings = config.get_settings()
        run_id = context["run_id"]
        key = _minio_key(context, "newsapi_articles.json")

        with audit.track(context) as metrics:
            category_article_pairs = newsapi_client.fetch_articles(
                api_key=settings.newsapi_api_key,
                categories=settings.newsapi_categories,
                max_requests_per_run=settings.newsapi_max_requests_per_run,
            )
            metrics.rows_fetched = len(category_article_pairs)

            payload = [
                {"provider": "newsapi", "category": c, "article": a}
                for c, a in category_article_pairs
            ]
            minio_io.put_json(settings.minio_bucket, key, payload)
            metrics.extra_metadata = {"minio_key": key, "categories": settings.newsapi_categories}

        return {"minio_key": key, "ingestion_run_id": run_id}

    @task
    def fetch_gnews_articles(**context) -> dict:
        settings = config.get_settings()
        run_id = context["run_id"]
        key = _minio_key(context, "gnews_articles.json")

        with audit.track(context) as metrics:
            if not settings.gnews_api_key:
                metrics.rows_fetched = 0
                metrics.extra_metadata = {"skipped": "gnews_api_key not configured"}
                minio_io.put_json(settings.minio_bucket, key, [])
                return {"minio_key": key, "ingestion_run_id": run_id}

            category_article_pairs = gnews_client.fetch_articles(
                api_key=settings.gnews_api_key,
                categories=settings.gnews_categories,
                max_requests_per_run=settings.gnews_max_requests_per_run,
            )
            metrics.rows_fetched = len(category_article_pairs)

            payload = [
                {"provider": "gnews", "category": c, "article": a}
                for c, a in category_article_pairs
            ]
            minio_io.put_json(settings.minio_bucket, key, payload)
            metrics.extra_metadata = {"minio_key": key, "categories": settings.gnews_categories}

        return {"minio_key": key, "ingestion_run_id": run_id}

    @task
    def load_raw_to_postgres(fetch_results: list[dict], **context) -> None:
        settings = config.get_settings()

        with audit.track(context) as metrics:
            items = []
            for fetch_result in fetch_results:
                payload = minio_io.get_json(settings.minio_bucket, fetch_result["minio_key"])
                items.extend(
                    (item["provider"], item["category"], item["article"]) for item in payload
                )
            metrics.rows_fetched = len(items)

            rows_new, rows_duplicate = postgres_io.upsert_articles(
                items,
                ingestion_run_id=fetch_results[0]["ingestion_run_id"],
            )
            metrics.rows_new = rows_new
            metrics.rows_duplicate = rows_duplicate

    @task
    def load_postgres_to_clickhouse_raw(**context) -> None:
        # run_id comes straight from this task's own context, not from an upstream fetch task's
        # XCom - it's the DAG run's id, identical for every task in the run, and this copy scans
        # Postgres by ingestion_run_id (see clickhouse_io.load_new_rows) so it picks up *both*
        # providers' new rows in one pass regardless of which fetch task "supplied" the id. Taking
        # it from a specific fetch task's return value would draw a misleading provider-specific
        # edge in the Airflow graph view, as if this step only depended on NewsAPI.
        with audit.track(context) as metrics:
            rows_copied = clickhouse_io.load_new_rows(run_id=context["run_id"])
            metrics.rows_fetched = rows_copied
            metrics.rows_new = rows_copied

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"{DBT_BIN} build "
            f"--profiles-dir {DBT_PROJECT_DIR} --project-dir {DBT_PROJECT_DIR} --target prod "
            "--log-path /tmp/dbt_logs --target-path /tmp/dbt_target"
        ),
    )

    @task
    def cluster_articles(**context) -> None:
        with audit.track(context) as metrics:
            rows_written = clustering_io.compute_clusters()
            metrics.rows_fetched = rows_written
            metrics.rows_new = rows_written

    MAX_ENRICHMENT_FAILURE_RATE = 0.2

    @task
    def llm_enrichment(**context) -> None:
        settings = config.get_settings()
        with audit.track(context) as metrics:
            attempted, succeeded, failed = enrichment_io.enrich_pending_clusters(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                model=settings.openrouter_model,
            )
            # Counts are recorded on `metrics` before the failure-rate check below, so
            # pipeline_run_log reflects what actually happened even if this then raises.
            metrics.rows_fetched = attempted
            metrics.rows_new = succeeded
            metrics.rows_failed = failed

            if attempted and failed / attempted > MAX_ENRICHMENT_FAILURE_RATE:
                raise RuntimeError(
                    f"LLM enrichment failure rate too high: {failed}/{attempted} failed "
                    f"(threshold {MAX_ENRICHMENT_FAILURE_RATE:.0%})"
                )

    newsapi_result = fetch_newsapi_articles()
    gnews_result = fetch_gnews_articles()
    (
        load_raw_to_postgres([newsapi_result, gnews_result])
        >> load_postgres_to_clickhouse_raw()
        >> dbt_run
        >> cluster_articles()
        >> llm_enrichment()
    )


news_ingestion_pipeline()
