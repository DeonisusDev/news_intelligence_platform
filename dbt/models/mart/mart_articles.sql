-- Recomputed as a full table each run (data volume here is hundreds of articles/day -
-- not enough to justify incremental mart logic; see docs/adr/0002 for the scale caveat).
select
    a.url_hash,
    a.title,
    a.description,
    a.content,
    a.is_content_truncated,
    a.url,
    a.url_domain,
    a.url_to_image,
    a.published_at,
    a.query_keyword,
    d.source_id,
    a.source_name,
    a.fetched_at
-- ClickHouse requires the alias before FINAL, not after (`table alias FINAL`, not `table FINAL alias`).
from {{ ref('ods_articles') }} a final
left join {{ ref('dim_source') }} d
    on coalesce(a.source_name, 'Unknown') = d.source_name
