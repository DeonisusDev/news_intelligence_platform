"""Unit tests for the per-cluster enrichment control flow: attempted/succeeded/failed counting,
and that a per-cluster failure doesn't stop the run - against a fake ClickHouse client and a
patched enrich_cluster (no real API/database or Airflow needed - see the `client` param
docstring in enrichment_io.py).
"""

from unittest.mock import patch

import news_pipeline.enrichment_io as enrichment_io
from news_pipeline.enrichment_io import enrich_pending_clusters
from news_pipeline.llm_client import ClusterEnrichment, EnrichmentError, SourcePerspective


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClickHouseClient:
    def __init__(self, pending_rows):
        self._pending_rows = pending_rows
        self.inserted_rows = []

    def query(self, sql, parameters=None):
        return FakeResult(self._pending_rows)

    def insert(self, table, rows, column_names=None):
        self.inserted_rows.extend(rows)


_ENRICHMENT = ClusterEnrichment(
    summary="s", keywords=["k"], topic="Tech", sentiment="neutral", sentiment_score=0.0
)


def test_returns_zero_counts_when_nothing_pending():
    client = FakeClickHouseClient([])
    attempted, succeeded, failed = enrich_pending_clusters(
        api_key="k", base_url="u", model="m", client=client
    )
    assert (attempted, succeeded, failed) == (0, 0, 0)
    assert client.inserted_rows == []


def test_all_clusters_succeed():
    pending = [
        ("cluster1", [("hash1", "T1", "D1", "Forbes")]),
        ("cluster2", [("hash2", "T2", "D2", "Biztoc.com")]),
    ]
    client = FakeClickHouseClient(pending)

    with patch.object(enrichment_io, "enrich_cluster", return_value=_ENRICHMENT):
        attempted, succeeded, failed = enrich_pending_clusters(
            api_key="k", base_url="u", model="m", client=client
        )

    assert (attempted, succeeded, failed) == (2, 2, 0)
    assert len(client.inserted_rows) == 2
    statuses = {row[7] for row in client.inserted_rows}
    assert statuses == {"success"}


def test_per_cluster_failure_does_not_stop_the_run():
    pending = [
        ("cluster1", [("hash1", "T1", "D1", "Forbes")]),
        ("cluster2", [("hash2", "T2", "D2", "Biztoc.com")]),
    ]
    client = FakeClickHouseClient(pending)

    def side_effect(**kwargs):
        if kwargs["articles"][0].title == "T1":
            raise EnrichmentError("boom", raw_response="raw response text")
        return _ENRICHMENT

    with patch.object(enrichment_io, "enrich_cluster", side_effect=side_effect):
        attempted, succeeded, failed = enrich_pending_clusters(
            api_key="k", base_url="u", model="m", client=client
        )

    assert (attempted, succeeded, failed) == (2, 1, 1)
    rows_by_cluster = {row[0]: row for row in client.inserted_rows}
    assert rows_by_cluster["cluster1"][7] == "failed"
    assert rows_by_cluster["cluster1"][8] == "raw response text"  # raw_llm_response preserved
    assert rows_by_cluster["cluster2"][7] == "success"


def test_multi_article_cluster_builds_one_clusterarticle_per_member():
    pending = [
        ("cluster1", [("hash1", "T1", "D1", "Forbes"), ("hash2", "T1b", "D1b", "Biztoc.com")])
    ]
    client = FakeClickHouseClient(pending)
    captured = {}

    def side_effect(**kwargs):
        captured["articles"] = kwargs["articles"]
        return _ENRICHMENT

    with patch.object(enrichment_io, "enrich_cluster", side_effect=side_effect):
        enrich_pending_clusters(api_key="k", base_url="u", model="m", client=client)

    assert len(captured["articles"]) == 2
    assert captured["articles"][0].source_name == "Forbes"
    assert captured["articles"][1].source_name == "Biztoc.com"
    assert client.inserted_rows[0][9] == 2  # article_count


def test_source_perspectives_are_keyed_by_url_hash_via_index():
    pending = [
        ("cluster1", [("hash1", "T1", "D1", "Forbes"), ("hash2", "T1b", "D1b", "Biztoc.com")])
    ]
    client = FakeClickHouseClient(pending)
    enrichment = ClusterEnrichment(
        summary="s",
        topic="Tech",
        sentiment="neutral",
        source_perspectives=[
            SourcePerspective(index=2, focus="Biztoc's angle"),
            SourcePerspective(index=1, focus="Forbes' angle"),
        ],
    )

    with patch.object(enrichment_io, "enrich_cluster", return_value=enrichment):
        enrich_pending_clusters(api_key="k", base_url="u", model="m", client=client)

    source_perspectives = client.inserted_rows[0][19]
    assert ("hash2", "Biztoc's angle") in source_perspectives
    assert ("hash1", "Forbes' angle") in source_perspectives


def test_out_of_range_source_perspective_index_is_dropped():
    pending = [("cluster1", [("hash1", "T1", "D1", "Forbes")])]
    client = FakeClickHouseClient(pending)
    enrichment = ClusterEnrichment(
        summary="s",
        topic="Tech",
        sentiment="neutral",
        source_perspectives=[SourcePerspective(index=5, focus="hallucinated index")],
    )

    with patch.object(enrichment_io, "enrich_cluster", return_value=enrichment):
        enrich_pending_clusters(api_key="k", base_url="u", model="m", client=client)

    assert client.inserted_rows[0][19] == []


def test_failed_cluster_gets_empty_defaults_for_rich_detail_fields():
    pending = [("cluster1", [("hash1", "T1", "D1", "Forbes")])]
    client = FakeClickHouseClient(pending)

    with patch.object(
        enrichment_io, "enrich_cluster", side_effect=EnrichmentError("boom", raw_response="raw")
    ):
        enrich_pending_clusters(api_key="k", base_url="u", model="m", client=client)

    row = client.inserted_rows[0]
    assert row[11:14] == ([], [], [])  # key_facts_organizations/locations/people
    assert row[14] == ""  # why_it_matters
    assert row[15] is None and row[16] is None  # before_state, after_state
    assert row[17:20] == ([], [], [])  # consensus_points, disagreement_points, source_perspectives
