# ADR 0005: Cluster articles into stories before LLM enrichment

## Status
Accepted

## Context
The same real-world event is routinely reported by several outlets under different URLs (and
therefore different `url_hash` values, per ADR 0004) - e.g. Forbes publishes a story and
Biztoc.com syndicates it verbatim. Enriching every article independently means paying for (and
displaying) the same summary N times, which is both wasteful against free-tier LLM quotas and
not what a reader wants from a "news intelligence" product - they want one summary per story,
with the covering outlets attached, not N near-identical summaries.

## Decision
A new `cluster_articles` DAG task runs between `dbt_run` and `llm_enrichment`
(`clustering_io.py`). It groups `mart_articles` into clusters using **title-token Jaccard
similarity** (lowercased, stopword-stripped tokens; threshold 0.5; only articles published
within a day of each other are compared) and a union-find over the resulting similarity graph -
no LLM call involved in this step, keeping it fast, free, and deterministic. Assignments are
written to `mart.article_clusters` (`url_hash -> cluster_id`).

A cluster's `cluster_id` is the `url_hash` of its **earliest-published member**, not a hash of
the full membership set. `llm_enrichment` then runs once per `cluster_id` (not per article),
gathering every member's title/description/source into one prompt, and writes one row per
cluster to `mart.summary_clusters`.

## Consequences
- LLM calls scale with distinct stories, not distinct articles/outlets - directly mitigates the
  free-tier daily quota this project already ran into during development.
- The whole `mart_articles` table is re-clustered from scratch every run (same
  recompute-the-whole-table pattern as `mart_articles`/`mart_daily_stats`; see ADR 0002). The
  resulting O(n²) title comparison is trivial at this project's data volume (hundreds of
  articles/day) but would need real dedup infrastructure (e.g. an embedding index, incremental
  clustering) at production scale.
- Because the cluster ID is pinned to its earliest member, it stays stable as further outlets
  join later - an already-summarized cluster is never treated as "new" just because one more
  article joins it. The trade-off: that cluster's summary also won't automatically pick up the
  newcomer's information. Refreshing it requires manually deleting its `summary_clusters` row
  and rerunning - acceptable for this project's scale, called out here rather than silently
  glossed over.
- Title-only similarity is a coarse heuristic - it won't catch stories with very differently
  worded headlines, and could over-cluster generic/templated titles (rare in practice for real
  news headlines). Embedding-based similarity would be more accurate but costs an API call per
  article; rejected for now to keep the clustering step LLM-free.
