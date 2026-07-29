# ADR 0008: Rich event detail as one bigger enrichment call, not several

## Status
Accepted

## Context
Phase 6.1 extends the cluster detail view with the Perplexity-Discover-inspired sections
sketched in product-vision discussions: Key Facts (organizations/locations/people), an AI
Analysis ("why it matters" + an optional before/after comparison), a Consensus/Disagreement
breakdown across sources, and per-source "what this outlet focused on" mini-summaries. The
"Impact" (star ratings per audience) idea from the same discussion was explicitly dropped before
implementation - too subjective/unverifiable for an LLM to produce meaningfully, see the
product-vision memory.

The plan (`serene-drifting-clover.md` §8, Phase 6.1) floated two implementation shapes: "a larger
single prompt, or additional per-cluster calls."

## Decision
**One larger prompt, still one LLM call per cluster** - not one call per new section. All new
fields (`key_facts`, `why_it_matters`, `before_state`/`after_state`, `consensus_points`,
`disagreement_points`, `source_perspectives`) are requested in the same JSON response as the
existing `summary`/`keywords`/`topic`/`sentiment` fields (see `prompts/enrichment_prompt.txt`
and `llm_client.ClusterEnrichment`). Splitting into multiple calls would multiply the already
free-tier-constrained enrichment step's request volume for no benefit here - the model can
produce the whole analysis from the same article context it already has.

**`source_perspectives` is keyed by url_hash, not source_name or a bare index.** The model
returns `{"index": N, "focus": "..."}` where N matches the 1-based numbering it's shown in
`_format_articles_block` - `enrichment_io.py` then zips that index back onto its own
locally-known `url_hash` list (added to `_SELECT_PENDING_SQL`'s `groupArray` tuple) before
storing `Array(Tuple(url_hash, focus))`. Rejected alternatives: matching by `source_name` risks
the model paraphrasing/typo-ing it; a bare index with no reconciliation would silently desync if
`_SOURCES_SQL`'s `order by published_at` and the enrichment query's (unordered) `groupArray`
ever disagreed. url_hash is this codebase's existing "one key reused at every layer" convention
(see ADR 0004) - reusing it here instead of inventing a new join strategy.

**`before_state`/`after_state` are both nullable, not required.** Most stories (lifestyle,
entertainment, opinion) have no natural "before → after" - the prompt explicitly tells the model
to return `null` for both rather than inventing a comparison. Confirmed working as intended in
a real test batch (a celebrity-adventure story correctly got `null, null`; a product-launch-
shaped story got a real before/after pair).

**Client timeout raised 30s → 60s** (`llm_client.enrich_cluster`). A real test against
`gpt-oss-20b:free` (see [[llm-model-choice]] memory for the same-day model-comparison context)
hit ~85s wall-clock on one cluster at the old 30s timeout - i.e. it was already silently retrying
once internally before succeeding. The bigger response schema (roughly 2-3x the old one) takes
longer to generate; the timeout needed real headroom, not just a bump for its own sake.

**New `summary_clusters` columns, not a companion table.** `key_facts_*`, `why_it_matters`,
`before_state`/`after_state`, `consensus_points`, `disagreement_points`, `source_perspectives`
all live directly on `mart.summary_clusters` (see `sql/clickhouse/004_create_summary_clusters.sql`
and the `migrations/006_...` migration for existing deployments) - one enrichment call still
produces one row, so there's no new grain that would justify a separate table.

**FastAPI: these fields are detail-only, never on `GET /discover`'s list response.** `SummaryCard`
is unchanged; only `SummaryDetail` (and `SourceArticle.source_summary`) gained fields. The list
endpoint's cost profile (one query, `limit` rows) shouldn't grow just because the detail view got
richer.

## Consequences
- Existing `summary_clusters` rows written before this migration have empty/null values for all
  new columns (ClickHouse `Array(String)` columns default to `[]`, `why_it_matters` defaults to
  `''`) - not re-enriched automatically. The frontend hides each new section entirely when its
  data is empty (`AnalysisSection`/`KeyFactsSection`/`ConsensusSection` all return `null` in that
  case) rather than showing an empty/placeholder block, so old and newly-enriched clusters render
  correctly side by side in the same feed.
- A real backfill batch (45 clusters: all multi-source clusters that existed at the time, plus a
  random sample of single-source ones) was deleted and re-enriched against the live stack to
  verify this end-to-end against real data rather than fixtures alone - following the same
  "delete stale row → rerun" recovery pattern as the earlier `FINAL`-bug fix.
- Enrichment's per-cluster LLM cost is unchanged (still exactly one call per cluster); wall-clock
  time per cluster increased due to the larger response, which is why the client timeout needed
  to move too.
