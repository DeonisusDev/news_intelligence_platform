"""Settings sourced from environment variables (see docker-compose.yml's `fastapi` service) -
no hardcoded credentials, no Airflow dependency (this app runs standalone).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    clickhouse_host: str = "clickhouse"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "default"

    newsdata_pg_dsn: str

    # Comma-separated list of allowed browser origins for the frontend (see docker-compose.yml's
    # `frontend` service) - no wildcard, since cookies will carry auth once Phase 6.5 lands.
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
