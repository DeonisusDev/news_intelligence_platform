"""Endpoint tests for the Discovery-feed routes (see routers/discover.py) - list, detail, 404,
topic filtering, and (Phase 7) feedback voting + affinity re-ranking, all against fake
ClickHouse/Postgres clients so no database is needed.
"""

from conftest import login_as

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


# --- Phase 7: feedback (thumbs up/down) ---------------------------------------------------


def test_feedback_requires_login(make_client):
    client, _ = make_client(ch_responses=[])

    response = client.post("/discover/cluster1/feedback", json={"vote": 1})

    assert response.status_code == 401


def test_feedback_rejects_an_invalid_vote_value(make_feedback_client):
    client, _, _ = make_feedback_client()
    login_as(client)

    response = client.post("/discover/cluster1/feedback", json={"vote": 0})

    assert response.status_code == 422


def test_feedback_upsert_stores_the_vote(make_feedback_client):
    client, _, store = make_feedback_client()
    login_as(client, user_id=7)

    response = client.post("/discover/cluster1/feedback", json={"vote": 1})

    assert response.status_code == 204
    assert store[(7, "cluster1")] == 1


def test_feedback_upsert_overwrites_a_previous_vote(make_feedback_client):
    client, _, store = make_feedback_client(feedback_store={(7, "cluster1"): 1})
    login_as(client, user_id=7)

    client.post("/discover/cluster1/feedback", json={"vote": -1})

    assert store[(7, "cluster1")] == -1


def test_feedback_delete_removes_the_vote(make_feedback_client):
    client, _, store = make_feedback_client(feedback_store={(7, "cluster1"): 1})
    login_as(client, user_id=7)

    response = client.delete("/discover/cluster1/feedback")

    assert response.status_code == 204
    assert (7, "cluster1") not in store


# --- Phase 7: affinity re-ranking for logged-in users -------------------------------------

CARD_ROW_SPORTS = (
    "cluster2",
    "A sports summary",
    "Sports",
    "neutral",
    0.0,
    ["olympics"],
    1,
    "2026-07-28T09:00:00",
    "2026-07-27T12:00:00",
    None,
)


def test_list_is_unweighted_and_untouched_for_a_logged_in_user_with_no_votes(make_feedback_client):
    client, fake, _ = make_feedback_client(ch_responses=[[CARD_ROW, CARD_ROW_SPORTS]])
    login_as(client)

    response = client.get("/discover")

    assert response.status_code == 200
    body = response.json()
    assert [c["cluster_id"] for c in body] == ["cluster1", "cluster2"]
    assert all(c["my_vote"] is None for c in body)


def test_list_reranks_by_affinity_to_previously_liked_clusters(make_feedback_client):
    # Candidate window comes back recency-sorted: cluster1 (Technology) before cluster2 (Sports).
    # The user has previously upvoted a Sports cluster, so cluster2 should be promoted above it.
    client, fake, _ = make_feedback_client(
        ch_responses=[
            [CARD_ROW, CARD_ROW_SPORTS],  # candidate window
            [("liked-cluster", "Sports", ["olympics"])],  # affinity-profile lookup
        ],
        feedback_store={(1, "liked-cluster"): 1},
    )
    login_as(client, user_id=1)

    response = client.get("/discover")

    assert response.status_code == 200
    body = response.json()
    assert [c["cluster_id"] for c in body] == ["cluster2", "cluster1"]


def test_list_reports_the_users_own_vote_per_card(make_feedback_client):
    # cluster1 has an up-vote, so the affinity-profile lookup fires too (fed back its own topic).
    client, fake, _ = make_feedback_client(
        ch_responses=[
            [CARD_ROW, CARD_ROW_SPORTS],  # candidate window
            [("cluster1", "Technology", ["ai", "chips"])],  # affinity-profile lookup
        ],
        feedback_store={(1, "cluster1"): 1, (1, "cluster2"): -1},
    )
    login_as(client, user_id=1)

    response = client.get("/discover")

    body = {c["cluster_id"]: c["my_vote"] for c in response.json()}
    assert body == {"cluster1": 1, "cluster2": -1}
