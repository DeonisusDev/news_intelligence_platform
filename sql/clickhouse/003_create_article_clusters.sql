-- Maps each article to a cluster of articles covering the same underlying story (e.g. 10
-- outlets all reporting "new Claude version released"), so LLM enrichment summarizes the
-- story once, not once per outlet. Populated by clustering_io.compute_clusters() (title-token
-- similarity, no LLM call), not a dbt model. Recomputed over the full mart_articles table each
-- run (cheap at this project's data volume - see docs/adr/0005).
CREATE TABLE IF NOT EXISTS mart.article_clusters
(
    url_hash    String,
    cluster_id  String,   -- url_hash of the cluster's earliest-published member (stable key)
    computed_at DateTime
)
ENGINE = ReplacingMergeTree(computed_at)
ORDER BY url_hash;
