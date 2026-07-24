"""Daily ingestion DAG: NewsAPI.org -> MinIO (raw JSON) -> Postgres (raw_articles).

max_active_runs=1 keeps free-tier NewsAPI/LLM quota bookkeeping trivial to reason about;
there's no benefit to concurrent runs for a single daily batch job (see docs/adr/0001).
"""
from __future__ import annotations

from datetime import datetime, timezone

from airflow.decorators import dag, task

from news_pipeline import audit, config, minio_io, newsapi_client, postgres_io

MINIO_RAW_PREFIX = "raw/newsapi"


@dag(
    dag_id="news_ingestion_pipeline",
    description="NewsAPI -> MinIO -> Postgres raw -> (later phases: ClickHouse, LLM enrichment)",
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

    load_raw_to_postgres(fetch_newsapi_articles())


news_ingestion_pipeline()
