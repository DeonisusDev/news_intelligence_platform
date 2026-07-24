"""Writes to pipeline_run_log: a queryable pipeline run history independent of Airflow's
own UI/metadata DB (row/duplicate/failure counts are business metrics Airflow has no
visibility into, so each task records them explicitly).
"""
from __future__ import annotations

import json
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

from airflow.providers.postgres.hooks.postgres import PostgresHook

from .postgres_io import NEWSDATA_CONN_ID

_INSERT_SQL = """
INSERT INTO pipeline_run_log
    (run_id, dag_id, task_id, try_number, execution_date, started_at, status)
VALUES (%s, %s, %s, %s, %s, %s, 'running')
ON CONFLICT (run_id, task_id, try_number) DO NOTHING
"""

_UPDATE_SQL = """
UPDATE pipeline_run_log
SET finished_at = %s, status = %s, rows_fetched = %s, rows_new = %s,
    rows_duplicate = %s, rows_failed = %s, error_message = %s, extra_metadata = %s
WHERE run_id = %s AND task_id = %s AND try_number = %s
"""


@dataclass
class RunMetrics:
    rows_fetched: int = 0
    rows_new: int = 0
    rows_duplicate: int = 0
    rows_failed: int = 0
    extra_metadata: dict = field(default_factory=dict)


def _hook() -> PostgresHook:
    return PostgresHook(postgres_conn_id=NEWSDATA_CONN_ID)


@contextmanager
def track(context: dict):
    ti = context["ti"]
    run_id = context["run_id"]
    dag_id = ti.dag_id
    task_id = ti.task_id
    try_number = ti.try_number
    # logical_date is None for manual triggers not tied to a schedule (Airflow 3); fall back
    # to "now" so the NOT NULL execution_date column always gets a real timestamp.
    execution_date = context.get("logical_date") or datetime.now(timezone.utc)
    started_at = datetime.now(timezone.utc)

    _hook().run(_INSERT_SQL, parameters=(run_id, dag_id, task_id, try_number, execution_date, started_at))

    metrics = RunMetrics()
    status = "success"
    error_message = None
    try:
        yield metrics
    except Exception:
        status = "failed"
        error_message = traceback.format_exc()[:4000]
        raise
    finally:
        _hook().run(
            _UPDATE_SQL,
            parameters=(
                datetime.now(timezone.utc),
                status,
                metrics.rows_fetched,
                metrics.rows_new,
                metrics.rows_duplicate,
                metrics.rows_failed,
                error_message,
                json.dumps(metrics.extra_metadata),
                run_id,
                task_id,
                try_number,
            ),
        )
