"""Reads pipeline_run_log (Postgres) - API-level observability into ingestion runs, independent
of the Airflow UI/metadata DB (see sql/postgres/003_create_pipeline_run_log.sql).
"""

from __future__ import annotations

from db.postgres_client import get_postgres_connection
from fastapi import APIRouter, Depends, Query
from psycopg2.extensions import connection as PGConnection
from schemas import PipelineRun

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_RUNS_SQL = """
select run_id, dag_id, task_id, try_number, status, started_at, finished_at,
       rows_fetched, rows_new, rows_duplicate, rows_failed, error_message
from pipeline_run_log
order by started_at desc
limit %(limit)s
"""


@router.get("/runs", response_model=list[PipelineRun])
def list_pipeline_runs(
    limit: int = Query(20, ge=1, le=200),
    conn: PGConnection = Depends(get_postgres_connection),
) -> list[PipelineRun]:
    with conn.cursor() as cur:
        cur.execute(_RUNS_SQL, {"limit": limit})
        rows = cur.fetchall()
    return [PipelineRun(**row) for row in rows]
