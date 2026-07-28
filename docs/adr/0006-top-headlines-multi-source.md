# ADR 0006: Top-headlines ingestion across all categories, from two providers

## Status
Accepted

## Context
Phases 1-3 fetched articles via NewsAPI's `/v2/everything` with a fixed list of keyword queries
(`technology,business,science,artificial intelligence`) - a tech-news filter, not a general news
feed. The target product (see product-vision memory: a Perplexity-Discovery-style feed) needs
top/main headlines across *all* areas of interest, not just technology. A single provider is
also a single point of coverage failure: NewsAPI and GNews each index a different set of outlets,
so the same real-world story is more likely to be caught by at least one of them, which matters
directly to the clustering step (ADR 0005) - more source diversity per cluster, richer summaries.

## Decision
Two independent fetch tasks run each day, both pulling **top headlines by category** rather than
keyword search:
- `fetch_newsapi_articles`: NewsAPI.org `/v2/top-headlines`, looping over its 7 categories
  (business, entertainment, general, health, science, sports, technology).
- `fetch_gnews_articles`: GNews.io `/v4/top-headlines`, looping over its 9 categories (adds
  world, nation). Free tier gives no pagination, so this is one request per category.

Both write their own MinIO JSON blob (tagged `provider`/`category` per item), and
`load_raw_to_postgres` merges both into the same `raw_articles` table, which gained two columns:
`category` (renamed from `query_keyword` - now a top-headlines category, not a free-text keyword)
and `source_provider` (`'newsapi'` | `'gnews'`). `_extract_common_fields()` in `postgres_io.py`
normalizes each provider's article shape (GNews has no `source.id`/`author`, and calls the image
field `image` not `urlToImage`) before insert; `raw_payload` still stores the untouched
provider-native JSON.

`dedup.py`'s `url_hash` is unaffected - it's still the single cross-provider identity key, and
article clustering (ADR 0005) is what catches the same story appearing under two different URLs
from two different providers.

## Consequences
- `raw_articles`/`raw.newsapi_articles` schema change: existing deployments need the migration
  scripts (`sql/postgres/004_migrate_category_provider.sql`,
  `sql/clickhouse/005_migrate_category_provider.sql`) since `docker-entrypoint-initdb.d` scripts
  only run once against an empty volume; fresh installs get the new shape directly from
  `002_create_raw_articles.sql`.
- GNews is optional at the config level - `gnews_api_key` defaults to empty, and
  `fetch_gnews_articles` skips cleanly (0 rows, no failure) if unset, so the pipeline still runs
  end-to-end for anyone who hasn't signed up for a GNews key yet.
- Both providers' free tiers are ~100 requests/day; looping 7-9 categories/day per provider is a
  small fraction of that budget, leaving headroom the keyword-query design didn't need to think
  about as carefully.
- `mart_articles.category` and `.source_provider` are now available for FastAPI/UI filtering
  (e.g. "Technology" or "Sports" tabs on the Discovery feed) - not built yet, but the schema
  supports it starting now rather than needing another migration later.
