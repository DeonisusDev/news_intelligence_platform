"""Daily ingestion DAG: NewsAPI.org -> MinIO (raw JSON) -> Postgres (raw_articles)
-> ClickHouse raw -> dbt build (stage -> ods -> mart).

max_active_runs=1 keeps free-tier NewsAPI/LLM quota bookkeeping trivial to reason about;
there's no benefit to concurrent runs for a single daily batch job (see docs/adr/0001).
"""
from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task
from airflow.providers.standard.operators.bash import BashOperator

from news_pipeline import audit, clickhouse_io, config, minio_io, newsapi_client, postgres_io

MINIO_RAW_PREFIX = "raw/newsapi"
DBT_PROJECT_DIR = "/opt/airflow/dbt"
DBT_BIN = "/opt/airflow/dbt_venv/bin/dbt"


@dag(
    dag_id="news_ingestion_pipeline",
    description="NewsAPI -> MinIO -> Postgres raw -> ClickHouse -> dbt (later phase: LLM enrichment)",
    schedule="@daily",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,
    tags=["news-intelligence"],
)
def news_ingestion_pipeline():
    @task
    def fetch_newsapi_articles(**context) -> dict:
        settings = config.get_settings()
        run_id = context["run_id"]
        # "ds" isn't in context for manual triggers not tied to a schedule (Airflow 3
        # leaves logical_date/data_interval as None in that case).
        logical_date = context.get("logical_date") or datetime.now(timezone.utc)
        ds = logical_date.strftime("%Y-%m-%d")
        key = f"{MINIO_RAW_PREFIX}/dt={ds}/run_id={run_id}/articles.json"

        with audit.track(context) as metrics:
            query_article_pairs = newsapi_client.fetch_articles(
                api_key=settings.newsapi_api_key,
                queries=settings.newsapi_queries,
                max_requests_per_run=settings.newsapi_max_requests_per_run,
            )
            metrics.rows_fetched = len(query_article_pairs)

            payload = [{"query": q, "article": a} for q, a in query_article_pairs]
            minio_io.put_json(settings.minio_bucket, key, payload)
            metrics.extra_metadata = {"minio_key": key, "queries": settings.newsapi_queries}

        return {"minio_key": key, "ingestion_run_id": run_id}

    @task
    def load_raw_to_postgres(fetch_result: dict, **context) -> None:
        settings = config.get_settings()

        with audit.track(context) as metrics:
            payload = minio_io.get_json(settings.minio_bucket, fetch_result["minio_key"])
            query_article_pairs = [(item["query"], item["article"]) for item in payload]
            metrics.rows_fetched = len(query_article_pairs)

            rows_new, rows_duplicate = postgres_io.upsert_articles(
                query_article_pairs,
                ingestion_run_id=fetch_result["ingestion_run_id"],
            )
            metrics.rows_new = rows_new
            metrics.rows_duplicate = rows_duplicate

    @task
    def load_postgres_to_clickhouse_raw(fetch_result: dict, **context) -> None:
        with audit.track(context) as metrics:
            rows_copied = clickhouse_io.load_new_rows(run_id=fetch_result["ingestion_run_id"])
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

    fetch_result = fetch_newsapi_articles()
    load_raw_to_postgres(fetch_result) >> load_postgres_to_clickhouse_raw(fetch_result) >> dbt_run


news_ingestion_pipeline()
