"""Endpoint tests for the pipeline-run-history route (see routers/pipeline.py), against a fake
Postgres connection (no real database needed).
"""

RUN_ROW = {
    "run_id": "manual__2026-07-28T07:49:00+00:00_abc",
    "dag_id": "news_ingestion_pipeline",
    "task_id": "llm_enrichment",
    "try_number": 1,
    "status": "success",
    "started_at": "2026-07-28T07:51:39+00:00",
    "finished_at": "2026-07-28T09:28:00+00:00",
    "rows_fetched": 380,
    "rows_new": 380,
    "rows_duplicate": 0,
    "rows_failed": 0,
    "error_message": None,
}


def test_list_pipeline_runs_returns_rows(make_pg_client):
    client, fake_conn = make_pg_client([RUN_ROW])

    response = client.get("/pipeline/runs")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["run_id"] == RUN_ROW["run_id"]
    assert body[0]["rows_fetched"] == 380


def test_list_pipeline_runs_passes_limit_through(make_pg_client):
    client, fake_conn = make_pg_client([])

    client.get("/pipeline/runs", params={"limit": 7})

    assert fake_conn._cursor.executed_with == {"limit": 7}


def test_list_pipeline_runs_empty_history(make_pg_client):
    client, fake_conn = make_pg_client([])

    response = client.get("/pipeline/runs")

    assert response.status_code == 200
    assert response.json() == []
