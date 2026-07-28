-- FINAL is defense-in-depth, not a correctness requirement here: Postgres's UNIQUE(url_hash)
-- already guarantees the raw copy task never inserts a given url_hash into ClickHouse twice.
select
    url_hash,
    source_id,
    source_name,
    author,
    trim(title) as title,
    trim(description) as description,
    content,
    length(content) >= 260 as is_content_truncated,
    url,
    domain(url) as url_domain,
    url_to_image,
    published_at,
    category,
    source_provider,
    fetched_at,
    ingestion_run_id
from {{ source('raw', 'newsapi_articles') }} final
