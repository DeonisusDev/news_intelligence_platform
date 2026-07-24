"""Central place to read pipeline configuration.

Values are sourced through Airflow's Variable API rather than raw os.environ: Airflow
transparently backs Variable.get("some_key") with an AIRFLOW_VAR_SOME_KEY env var when present
(see docker-compose.yml), so this works the same whether a value later moves into the metadata
DB, the Airflow UI, or a secrets backend - no code change required.
"""
from __future__ import annotations

from dataclasses import dataclass

from airflow.models import Variable


@dataclass(frozen=True)
class Settings:
    newsapi_api_key: str
    newsapi_queries: list[str]
    newsapi_max_requests_per_run: int
    minio_bucket: str
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    clickhouse_host: str
    clickhouse_port: int
    clickhouse_user: str
    clickhouse_password: str
    clickhouse_database: str


def get_settings() -> Settings:
    return Settings(
        newsapi_api_key=Variable.get("newsapi_api_key"),
        newsapi_queries=[
            q.strip()
            for q in Variable.get("newsapi_queries", default_var="technology,business").split(",")
            if q.strip()
        ],
        newsapi_max_requests_per_run=int(Variable.get("newsapi_max_requests_per_run", default_var="20")),
        minio_bucket=Variable.get("minio_bucket"),
        openrouter_api_key=Variable.get("openrouter_api_key"),
        openrouter_base_url=Variable.get("openrouter_base_url"),
        openrouter_model=Variable.get("openrouter_model"),
        clickhouse_host=Variable.get("clickhouse_host"),
        clickhouse_port=int(Variable.get("clickhouse_port")),
        clickhouse_user=Variable.get("clickhouse_user"),
        clickhouse_password=Variable.get("clickhouse_password"),
        clickhouse_database=Variable.get("clickhouse_database"),
    )
