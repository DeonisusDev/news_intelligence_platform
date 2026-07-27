-- Keyed by source_name, not source_id: NewsAPI only populates source.id for a small set of
-- "top sources" - most articles have a null id but a distinct, reliably-populated name, so
-- grouping by (source_id, source_name) leaves many unrelated sources sharing source_id='unknown'
-- and fans out any join keyed on source_id alone.
-- Group by the raw column, not coalesce(source_name, 'Unknown'): ClickHouse's GROUP BY key
-- matching gets confused when a SELECT-list alias shadows a source column of the same name
-- (works fine with a differently-named alias, or - as here - grouping by the plain column).
select
    coalesce(source_name, 'Unknown') as source_name,
    any(source_id) as source_id,
    any(url_domain) as sample_domain
from {{ ref('ods_articles') }} final
group by source_name
