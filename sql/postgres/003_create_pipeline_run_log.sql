-- Runs against the "newsdata" application database (see 001_create_newsdata_db.sql).
\c newsdata

-- Queryable pipeline run history, independent of Airflow's own UI/metadata DB.
-- Each task writes explicitly at start (status='running') and end (counts + final status),
-- since row/duplicate/failure counts are business metrics Airflow itself has no visibility into.
CREATE TABLE IF NOT EXISTS pipeline_run_log (
    id              BIGSERIAL PRIMARY KEY,
    run_id          TEXT NOT NULL,          -- Airflow dag_run.run_id, shared across all tasks in a run
    dag_id          TEXT NOT NULL,
    task_id         TEXT NOT NULL,
    try_number      INT NOT NULL,
    execution_date  TIMESTAMPTZ NOT NULL,   -- Airflow logical/data-interval date
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL,          -- running | success | failed
    rows_fetched    INT DEFAULT 0,
    rows_new        INT DEFAULT 0,
    rows_duplicate  INT DEFAULT 0,
    rows_failed     INT DEFAULT 0,
    error_message   TEXT,
    extra_metadata  JSONB,                  -- e.g. {"api_calls_used": 12, "llm_model": "...", "pages_fetched": 3}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, task_id, try_number)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_log_run_id ON pipeline_run_log (run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_run_log_dag_task ON pipeline_run_log (dag_id, task_id);
