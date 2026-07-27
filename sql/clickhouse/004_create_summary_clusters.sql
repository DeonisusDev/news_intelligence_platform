-- Populated directly by the llm_enrichment Airflow task (not a dbt model): one row per
-- (cluster_id, enrichment attempt) - one summary per underlying story, regardless of how many
-- articles/outlets cover it. enrichment_status='failed' rows keep raw_llm_response for
-- debugging bad/unparseable model output; a rerun only retries cluster_id values that don't
-- already have a 'success' row (see enrichment_io.py), so it never re-bills a successful call.
CREATE TABLE IF NOT EXISTS mart.summary_clusters
(
    cluster_id        String,
    summary           String,
    keywords          Array(String),
    topic             String,
    sentiment         String,
    sentiment_score   Nullable(Float32),
    llm_model         String,
    enrichment_status String,             -- success | failed
    raw_llm_response  Nullable(String),
    article_count     UInt32,             -- how many articles fed into this cluster's summary
    enriched_at       DateTime,
    created_at        DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(enriched_at)
ORDER BY cluster_id;
