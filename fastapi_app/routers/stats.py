"""Aggregate stats over the mart layer - article volume by day/source, cluster counts by topic."""

from __future__ import annotations

from clickhouse_connect.driver.client import Client
from db.clickhouse_client import get_clickhouse_client
from fastapi import APIRouter, Depends, Query
from schemas import DailyStat, TopicStat

router = APIRouter(prefix="/stats", tags=["stats"])

_DAILY_SQL = """
select published_date, source_name, article_count
from mart.mart_daily_stats
order by published_date desc, article_count desc
limit {limit:UInt32}
"""

_TOPICS_SQL = """
select topic, count() as cluster_count
from mart.summary_clusters final
where enrichment_status = 'success'
group by topic
order by cluster_count desc
"""


@router.get("/daily", response_model=list[DailyStat])
def daily_stats(
    limit: int = Query(100, ge=1, le=1000),
    client: Client = Depends(get_clickhouse_client),
) -> list[DailyStat]:
    rows = client.query(_DAILY_SQL, parameters={"limit": limit}).result_rows
    return [DailyStat(published_date=r[0], source_name=r[1], article_count=r[2]) for r in rows]


@router.get("/topics", response_model=list[TopicStat])
def topic_stats(client: Client = Depends(get_clickhouse_client)) -> list[TopicStat]:
    rows = client.query(_TOPICS_SQL).result_rows
    return [TopicStat(topic=r[0], cluster_count=r[1]) for r in rows]
