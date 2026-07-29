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
    created_at        DateTime DEFAULT now(),
    -- Phase 6.1 (see docs/adr/0008-rich-event-detail.md): all populated by the same enrichment
    -- LLM call as the fields above, not a second call - detail-view-only, never selected by the
    -- /discover list endpoint.
    key_facts_organizations Array(String),
    key_facts_locations     Array(String),
    key_facts_people        Array(String),
    why_it_matters          String,
    before_state            Nullable(String),
    after_state             Nullable(String),
    consensus_points        Array(String),
    disagreement_points     Array(String),
    -- (url_hash, focus) pairs - url_hash (not source_name or a positional index) is the join key
    -- back to mart_articles, matching this codebase's existing url_hash-everywhere convention.
    source_perspectives     Array(Tuple(String, String))
)
ENGINE = ReplacingMergeTree(enriched_at)
ORDER BY cluster_id;
