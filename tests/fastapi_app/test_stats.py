"""Endpoint tests for the aggregate stats routes (see routers/stats.py)."""

DAILY_ROW = ("2026-07-27", "Forbes", 4)
TOPIC_ROW = ("Technology", 116)


def test_daily_stats_returns_rows(make_client):
    client, fake = make_client(ch_responses=[[DAILY_ROW]])

    response = client.get("/stats/daily")

    assert response.status_code == 200
    body = response.json()
    assert body == [{"published_date": "2026-07-27", "source_name": "Forbes", "article_count": 4}]


def test_daily_stats_passes_limit_through(make_client):
    client, fake = make_client(ch_responses=[[]])

    client.get("/stats/daily", params={"limit": 5})

    _, params = fake.queries[0]
    assert params["limit"] == 5


def test_topic_stats_returns_rows(make_client):
    client, fake = make_client(ch_responses=[[TOPIC_ROW]])

    response = client.get("/stats/topics")

    assert response.status_code == 200
    assert response.json() == [{"topic": "Technology", "cluster_count": 116}]
