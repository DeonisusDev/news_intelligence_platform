"""Endpoint tests for the Discovery-feed routes (see routers/discover.py) - list, detail, 404,
and topic filtering, all against a fake ClickHouse client so no database is needed.
"""

CARD_ROW = (
    "cluster1",
    "A summary",
    "Technology",
    "neutral",
    0.0,
    ["ai", "chips"],
    2,
    "2026-07-28T10:00:00",
    "2026-07-26T12:00:00",
    "https://forbes.com/img.jpg",
)

# CARD_ROW plus the Phase 6.1 detail-only columns (see _DETAIL_EXTRA_COLUMNS in discover.py).
DETAIL_ROW = CARD_ROW + (
    ["Acme Corp"],
    ["Antarctica"],
    [],
    "it matters because of X",
    "before state",
    "after state",
    ["everyone agrees on X"],
    ["outlets differ on Y"],
    [("hash1", "Forbes' angle")],
)

SOURCE_ROWS = [
    (
        "hash1",
        "Forbes",
        "newsapi",
        "T1",
        "https://forbes.com/a",
        "https://forbes.com/img.jpg",
        "2026-07-26T12:00:00",
        "technology",
    ),
    (
        "hash2",
        "Biztoc.com",
        "newsapi",
        "T1",
        "https://biztoc.com/a",
        "https://biztoc.com/img.jpg",
        "2026-07-26T12:12:00",
        "technology",
    ),
]


def test_list_returns_cards(make_client):
    client, fake = make_client(ch_responses=[[CARD_ROW]])

    response = client.get("/discover")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["cluster_id"] == "cluster1"
    assert body[0]["article_count"] == 2
    assert body[0]["keywords"] == ["ai", "chips"]


def test_list_applies_default_pagination_params(make_client):
    client, fake = make_client(ch_responses=[[]])

    client.get("/discover")

    _, params = fake.queries[0]
    assert params["limit"] == 20
    assert params["offset"] == 0
    assert "topic" not in params


def test_list_passes_topic_filter_through(make_client):
    client, fake = make_client(ch_responses=[[]])

    client.get("/discover", params={"topic": "Technology"})

    sql, params = fake.queries[0]
    assert "topic = {topic:String}" in sql
    assert params["topic"] == "Technology"


def test_list_rejects_limit_above_max(make_client):
    client, _ = make_client(ch_responses=[[]])
    response = client.get("/discover", params={"limit": 1000})
    assert response.status_code == 422


def test_detail_returns_card_and_sources(make_client):
    client, fake = make_client(ch_responses=[[DETAIL_ROW], SOURCE_ROWS])

    response = client.get("/discover/cluster1")

    assert response.status_code == 200
    body = response.json()
    assert body["cluster_id"] == "cluster1"
    assert len(body["sources"]) == 2
    assert body["sources"][0]["source_name"] == "Forbes"
    assert body["sources"][1]["source_name"] == "Biztoc.com"


def test_detail_includes_rich_event_detail_fields(make_client):
    client, fake = make_client(ch_responses=[[DETAIL_ROW], SOURCE_ROWS])

    response = client.get("/discover/cluster1")

    body = response.json()
    assert body["key_facts"] == {
        "organizations": ["Acme Corp"],
        "locations": ["Antarctica"],
        "people": [],
    }
    assert body["why_it_matters"] == "it matters because of X"
    assert body["before_state"] == "before state"
    assert body["after_state"] == "after state"
    assert body["consensus_points"] == ["everyone agrees on X"]
    assert body["disagreement_points"] == ["outlets differ on Y"]


def test_detail_matches_source_perspective_by_url_hash(make_client):
    client, fake = make_client(ch_responses=[[DETAIL_ROW], SOURCE_ROWS])

    response = client.get("/discover/cluster1")

    sources = response.json()["sources"]
    assert sources[0]["source_summary"] == "Forbes' angle"  # hash1
    assert sources[1]["source_summary"] is None  # hash2 has no perspective entry


def test_detail_404s_for_unknown_cluster(make_client):
    client, fake = make_client(ch_responses=[[]])  # card query returns no rows

    response = client.get("/discover/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Cluster not found"
