select
    toDate(published_at) as published_date,
    source_name,
    count() as article_count
from {{ ref('mart_articles') }}
where published_at is not null
group by published_date, source_name
