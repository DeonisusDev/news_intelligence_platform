"""Discovery-style feed: one card per story-cluster (summary_clusters), expandable into its
individual source articles (article_clusters -> mart_articles). See product-vision discussion:
this mirrors a Perplexity-Discovery-like feed rather than a flat article list.
"""

from __future__ import annotations

from clickhouse_connect.driver.client import Client
from db.clickhouse_client import get_clickhouse_client
from fastapi import APIRouter, Depends, HTTPException, Query
from schemas import SourceArticle, SummaryCard, SummaryDetail

router = APIRouter(prefix="/discover", tags=["discover"])

_CARD_COLUMNS = (
    "c.cluster_id, c.summary, c.topic, c.sentiment, c.sentiment_score, c.keywords, "
    "c.article_count, c.enriched_at, m.first_published_at, m.image_url"
)

# Feed cards need a representative image and the earliest source's published_at (for a
# "published X ago" hero) up front, without a per-card detail round-trip - computed once per
# cluster_id here and joined onto summary_clusters, rather than N+1 detail fetches from the feed.
_CLUSTER_MEDIA_CTE = """
with cluster_media as (
    select
        ac.cluster_id,
        min(a.published_at) as first_published_at,
        any(a.url_to_image) as image_url
    from mart.article_clusters ac final
    inner join mart.mart_articles a on a.url_hash = ac.url_hash
    group by ac.cluster_id
)
"""

_LIST_SQL_BASE = f"""
{_CLUSTER_MEDIA_CTE}
select {_CARD_COLUMNS}
from mart.summary_clusters c final
inner join cluster_media m on m.cluster_id = c.cluster_id
where c.enrichment_status = 'success'
"""

_DETAIL_SQL = f"""
{_CLUSTER_MEDIA_CTE}
select {_CARD_COLUMNS}
from mart.summary_clusters c final
inner join cluster_media m on m.cluster_id = c.cluster_id
where c.enrichment_status = 'success' and c.cluster_id = {{cluster_id:String}}
"""

_SOURCES_SQL = """
select a.source_name, a.source_provider, a.title, a.url, a.url_to_image, a.published_at, a.category
from mart.article_clusters c final
inner join mart.mart_articles a on a.url_hash = c.url_hash
where c.cluster_id = {cluster_id:String}
order by a.published_at
"""


def _row_to_card(row: tuple) -> SummaryCard:
    return SummaryCard(
        cluster_id=row[0],
        summary=row[1],
        topic=row[2],
        sentiment=row[3],
        sentiment_score=row[4],
        keywords=row[5],
        article_count=row[6],
        enriched_at=row[7],
        first_published_at=row[8],
        image_url=row[9],
    )


@router.get("", response_model=list[SummaryCard])
def list_summary_cards(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    topic: str | None = Query(None, description="Filter to a single topic, exact match"),
    client: Client = Depends(get_clickhouse_client),
) -> list[SummaryCard]:
    sql = _LIST_SQL_BASE
    params: dict = {"limit": limit, "offset": offset}
    if topic:
        sql += " and c.topic = {topic:String}"
        params["topic"] = topic
    sql += " order by c.enriched_at desc limit {limit:UInt32} offset {offset:UInt32}"

    rows = client.query(sql, parameters=params).result_rows
    return [_row_to_card(row) for row in rows]


@router.get("/{cluster_id}", response_model=SummaryDetail)
def get_summary_detail(
    cluster_id: str,
    client: Client = Depends(get_clickhouse_client),
) -> SummaryDetail:
    rows = client.query(_DETAIL_SQL, parameters={"cluster_id": cluster_id}).result_rows
    if not rows:
        raise HTTPException(status_code=404, detail="Cluster not found")

    card = _row_to_card(rows[0])
    source_rows = client.query(_SOURCES_SQL, parameters={"cluster_id": cluster_id}).result_rows
    sources = [
        SourceArticle(
            source_name=r[0],
            source_provider=r[1],
            title=r[2],
            url=r[3],
            url_to_image=r[4],
            published_at=r[5],
            category=r[6],
        )
        for r in source_rows
    ]
    return SummaryDetail(**card.model_dump(), sources=sources)
