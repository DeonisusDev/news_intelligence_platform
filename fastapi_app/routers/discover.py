"""Discovery-style feed: one card per story-cluster (summary_clusters), expandable into its
individual source articles (article_clusters -> mart_articles). See product-vision discussion:
this mirrors a Perplexity-Discovery-like feed rather than a flat article list.
"""

from __future__ import annotations

from clickhouse_connect.driver.client import Client
from db.clickhouse_client import get_clickhouse_client
from db.postgres_client import get_postgres_connection
from dependencies import CurrentUser, get_current_user, get_optional_current_user
from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg2.extensions import connection as PGConnection
from ranking import AffinityCard, build_affinity_profile, rank_by_affinity
from schemas import FeedbackRequest, KeyFacts, SourceArticle, SummaryCard, SummaryDetail

router = APIRouter(prefix="/discover", tags=["discover"])

# Phase 7: how many recency-ordered rows a logged-in re-rank considers. Bounded so re-ranking
# stays a single cheap ClickHouse query rather than scanning the whole table; infinite scroll
# for a logged-in user stops once it runs past this window (see docs/adr/0010-recommendations.md).
_CANDIDATE_WINDOW = 200

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

# Detail-view-only fields (Phase 6.1) - never selected by the list endpoint above.
_DETAIL_EXTRA_COLUMNS = (
    "c.key_facts_organizations, c.key_facts_locations, c.key_facts_people, c.why_it_matters, "
    "c.before_state, c.after_state, c.consensus_points, c.disagreement_points, "
    "c.source_perspectives"
)

_DETAIL_SQL = f"""
{_CLUSTER_MEDIA_CTE}
select {_CARD_COLUMNS}, {_DETAIL_EXTRA_COLUMNS}
from mart.summary_clusters c final
inner join cluster_media m on m.cluster_id = c.cluster_id
where c.enrichment_status = 'success' and c.cluster_id = {{cluster_id:String}}
"""

_SOURCES_SQL = """
select a.url_hash, a.source_name, a.source_provider, a.title, a.url, a.url_to_image,
       a.published_at, a.category
from mart.article_clusters c final
inner join mart.mart_articles a on a.url_hash = c.url_hash
where c.cluster_id = {cluster_id:String}
order by a.published_at
"""

# Phase 7: just enough per cluster to build/score an affinity profile from.
_TOPIC_KEYWORDS_FOR_CLUSTERS_SQL = """
select cluster_id, topic, keywords from mart.summary_clusters final
where cluster_id in {cluster_ids:Array(String)}
"""

_USER_VOTES_SQL = """
select cluster_id, vote from cluster_feedback where user_id = %(user_id)s
"""

# Phase 7.1: "Liked" page - just the cluster_ids the user upvoted, most recently liked first, so
# a fresh Postgres upsert (see _UPSERT_FEEDBACK_SQL) reorders this list without a re-vote.
_LIKED_CLUSTER_IDS_SQL = """
select cluster_id from cluster_feedback
where user_id = %(user_id)s and vote = 1
order by created_at desc
limit %(limit)s offset %(offset)s
"""

_CARDS_BY_IDS_SQL = f"""
{_CLUSTER_MEDIA_CTE}
select {_CARD_COLUMNS}
from mart.summary_clusters c final
inner join cluster_media m on m.cluster_id = c.cluster_id
where c.enrichment_status = 'success' and c.cluster_id in {{cluster_ids:Array(String)}}
"""

_UPSERT_FEEDBACK_SQL = """
insert into cluster_feedback (user_id, cluster_id, vote)
values (%(user_id)s, %(cluster_id)s, %(vote)s)
on conflict (user_id, cluster_id) do update set vote = excluded.vote, created_at = now()
"""

_DELETE_FEEDBACK_SQL = """
delete from cluster_feedback where user_id = %(user_id)s and cluster_id = %(cluster_id)s
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
    q: str | None = Query(
        None, description="Case-insensitive substring match on the summary or keywords"
    ),
    client: Client = Depends(get_clickhouse_client),
    current_user: CurrentUser | None = Depends(get_optional_current_user),
    conn: PGConnection = Depends(get_postgres_connection),
) -> list[SummaryCard]:
    where_extra = ""
    params: dict = {}
    if topic:
        where_extra += " and c.topic = {topic:String}"
        params["topic"] = topic
    if q:
        # arrayExists over keywords since ClickHouse's ILIKE only works on strings, not arrays.
        where_extra += (
            " and (c.summary ILIKE {q_pattern:String} "
            "or arrayExists(k -> k ILIKE {q_pattern:String}, c.keywords))"
        )
        params["q_pattern"] = f"%{q}%"

    if current_user is None:
        # Anonymous/logged-out - plain unweighted feed, unchanged from pre-Phase-7 behavior.
        sql = _LIST_SQL_BASE + where_extra
        sql += " order by c.enriched_at desc limit {limit:UInt32} offset {offset:UInt32}"
        params.update({"limit": limit, "offset": offset})
        rows = client.query(sql, parameters=params).result_rows
        return [_row_to_card(row) for row in rows]

    # Logged in - pull a bounded recency-ordered candidate window, re-rank by affinity to the
    # user's liked clusters, then paginate the *ranked* list (see ranking.py / ADR 0010).
    window_sql = _LIST_SQL_BASE + where_extra
    window_sql += " order by c.enriched_at desc limit {window:UInt32}"
    params["window"] = _CANDIDATE_WINDOW
    candidates = [
        _row_to_card(row) for row in client.query(window_sql, parameters=params).result_rows
    ]

    with conn.cursor() as cur:
        cur.execute(_USER_VOTES_SQL, {"user_id": current_user.id})
        votes = {row["cluster_id"]: row["vote"] for row in cur.fetchall()}

    liked_cluster_ids = [cluster_id for cluster_id, vote in votes.items() if vote == 1]
    if liked_cluster_ids:
        profile_rows = client.query(
            _TOPIC_KEYWORDS_FOR_CLUSTERS_SQL, parameters={"cluster_ids": liked_cluster_ids}
        ).result_rows
        profile = build_affinity_profile(
            [AffinityCard(cluster_id=row[0], topic=row[1], keywords=row[2]) for row in profile_rows]
        )
        candidates = rank_by_affinity(candidates, profile)

    page = candidates[offset : offset + limit]
    return [card.model_copy(update={"my_vote": votes.get(card.cluster_id)}) for card in page]


@router.get("/liked", response_model=list[SummaryCard])
def list_liked_cards(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    client: Client = Depends(get_clickhouse_client),
    current_user: CurrentUser = Depends(get_current_user),
    conn: PGConnection = Depends(get_postgres_connection),
) -> list[SummaryCard]:
    # Registered ahead of GET /{cluster_id} below - otherwise FastAPI would match "liked" as a
    # cluster_id there instead of routing here.
    with conn.cursor() as cur:
        cur.execute(
            _LIKED_CLUSTER_IDS_SQL, {"user_id": current_user.id, "limit": limit, "offset": offset}
        )
        ordered_ids = [row["cluster_id"] for row in cur.fetchall()]

    if not ordered_ids:
        return []

    rows = client.query(_CARDS_BY_IDS_SQL, parameters={"cluster_ids": ordered_ids}).result_rows
    cards_by_id = {row[0]: _row_to_card(row) for row in rows}
    # Preserve the Postgres vote-recency order - ClickHouse's `in {array}` doesn't guarantee it.
    return [
        cards_by_id[cluster_id].model_copy(update={"my_vote": 1})
        for cluster_id in ordered_ids
        if cluster_id in cards_by_id
    ]


@router.get("/{cluster_id}", response_model=SummaryDetail)
def get_summary_detail(
    cluster_id: str,
    client: Client = Depends(get_clickhouse_client),
) -> SummaryDetail:
    rows = client.query(_DETAIL_SQL, parameters={"cluster_id": cluster_id}).result_rows
    if not rows:
        raise HTTPException(status_code=404, detail="Cluster not found")

    row = rows[0]
    card = _row_to_card(row)
    # Keyed by url_hash (see llm_client.SourcePerspective / enrichment_io.py) so it can't be
    # thrown off by a source_name the model paraphrased slightly differently from our data.
    perspective_by_hash = dict(row[18])

    source_rows = client.query(_SOURCES_SQL, parameters={"cluster_id": cluster_id}).result_rows
    sources = [
        SourceArticle(
            source_name=r[1],
            source_provider=r[2],
            title=r[3],
            url=r[4],
            url_to_image=r[5],
            published_at=r[6],
            category=r[7],
            source_summary=perspective_by_hash.get(r[0]),
        )
        for r in source_rows
    ]
    return SummaryDetail(
        **card.model_dump(),
        sources=sources,
        key_facts=KeyFacts(organizations=row[10], locations=row[11], people=row[12]),
        why_it_matters=row[13],
        before_state=row[14],
        after_state=row[15],
        consensus_points=row[16],
        disagreement_points=row[17],
    )


@router.post("/{cluster_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def submit_feedback(
    cluster_id: str,
    payload: FeedbackRequest,
    current_user: CurrentUser = Depends(get_current_user),
    conn: PGConnection = Depends(get_postgres_connection),
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            _UPSERT_FEEDBACK_SQL,
            {"user_id": current_user.id, "cluster_id": cluster_id, "vote": payload.vote},
        )
        conn.commit()


@router.delete("/{cluster_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def remove_feedback(
    cluster_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    conn: PGConnection = Depends(get_postgres_connection),
) -> None:
    with conn.cursor() as cur:
        cur.execute(_DELETE_FEEDBACK_SQL, {"user_id": current_user.id, "cluster_id": cluster_id})
        conn.commit()
