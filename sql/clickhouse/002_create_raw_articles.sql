-- Mirrors Postgres raw_articles, loaded incrementally per DAG run by the
-- load_postgres_to_clickhouse_raw task (INSERT ... SELECT FROM postgresql(...),
-- scoped to WHERE ingestion_run_id = '<this run>'). ReplacingMergeTree on url_hash
-- is defense-in-depth: Postgres's UNIQUE(url_hash) already guarantees no duplicate
-- rows are ever eligible to be copied in, so a plain MergeTree would also be
-- correct, but ReplacingMergeTree keeps the two raw layers consistent if that ever
-- changes and lets downstream stage models query `FINAL` for safety.
CREATE TABLE IF NOT EXISTS raw.newsapi_articles
(
    url_hash        String,
    source_id       Nullable(String),
    source_name     Nullable(String),
    author          Nullable(String),
    title           Nullable(String),
    description     Nullable(String),
    content         Nullable(String),
    url             String,
    url_to_image    Nullable(String),
    published_at    Nullable(DateTime),
    query_keyword   Nullable(String),
    fetched_at      DateTime,
    raw_payload     String,
    ingestion_run_id String,
    created_at      DateTime
)
ENGINE = ReplacingMergeTree(fetched_at)
ORDER BY url_hash;
