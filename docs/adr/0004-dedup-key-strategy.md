# ADR 0004: Deduplication and idempotency key

## Status
Accepted

## Context
NewsAPI frequently returns the same article across multiple query terms/categories in a single
run, and the same article again on subsequent days. The pipeline needs one canonical identity for
an article that's stable across re-fetches, and every layer (Postgres raw, ClickHouse raw/ods/mart,
summary_articles) needs to agree on it.

## Decision
`url_hash = sha256(normalize_url(url))` is the single dedup/idempotency key, computed once in
`airflow/dags/news_pipeline/dedup.py` and carried through every table unchanged.

Normalization: lowercase host, strip default port and trailing slash, strip known tracking query
params (`utm_*`, `fbclid`, `gclid`, ...), sort remaining query params, rebuild the URL, then hash.

## Consequences
- Postgres `raw_articles`: `UNIQUE(url_hash)` + `ON CONFLICT DO NOTHING` — first-seen-wins,
  duplicates counted but never merged (preserves "raw data is immutable").
- ClickHouse tables: `ORDER BY url_hash` with `ReplacingMergeTree`, `unique_key='url_hash'` in dbt
  incremental config.
- A URL-based key cannot detect two different URLs describing the same real-world story (e.g.
  syndicated wire copy on two domains) — that's a separate, coarser-grained problem, solved by
  the title-similarity article clustering in `docs/adr/0005-article-clustering.md`, not by
  `url_hash` itself.
- `summary_clusters`: the enrichment task anti-joins on `cluster_id` (not `url_hash`) against
  already-successful rows, so reruns never re-bill an LLM call for a story already summarized -
  see ADR 0005 for why enrichment is keyed by cluster rather than by individual article.
