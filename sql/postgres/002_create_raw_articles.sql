-- Runs against the "newsdata" application database (see 001_create_newsdata_db.sql).
\c newsdata

CREATE TABLE IF NOT EXISTS raw_articles (
    id               BIGSERIAL PRIMARY KEY,
    url_hash         CHAR(64) NOT NULL UNIQUE,   -- sha256(normalize_url(url)) -- the dedup/idempotency key
    source_id        TEXT,
    source_name      TEXT,
    author           TEXT,
    title            TEXT,
    description      TEXT,
    content          TEXT,                       -- NewsAPI free tier truncates this to ~260 chars
    url              TEXT NOT NULL,
    url_to_image     TEXT,
    published_at     TIMESTAMPTZ,
    category         TEXT,                       -- top-headlines category this article was fetched under
    source_provider  TEXT NOT NULL DEFAULT 'newsapi',  -- 'newsapi' | 'gnews'
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_payload      JSONB NOT NULL,             -- full original provider article object, for replay/audit
    -- Airflow's own dag_run.run_id (e.g. "scheduled__2026-07-24T00:00:00+00:00"), not a
    -- synthetic UUID - lets this row be traced directly back to the Airflow UI/CLI.
    ingestion_run_id TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_raw_articles_ingestion_run_id ON raw_articles (ingestion_run_id);
