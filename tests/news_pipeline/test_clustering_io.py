"""Unit tests for the pure clustering logic (see docs/adr/0005-article-clustering.md) - title
tokenization, Jaccard similarity, union-find, and the compute_clusters orchestration against a
fake ClickHouse client (no real database or Airflow needed - see the `client` param docstring
in clustering_io.py).
"""

from datetime import datetime

from news_pipeline.clustering_io import (
    SIMILARITY_THRESHOLD,
    _jaccard,
    _tokenize,
    _UnionFind,
    compute_clusters,
)


class FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class FakeClickHouseClient:
    def __init__(self, articles_rows):
        self._articles_rows = articles_rows
        self.inserted = None
        self.insert_table = None
        self.insert_columns = None

    def query(self, sql, parameters=None):
        return FakeResult(self._articles_rows)

    def insert(self, table, rows, column_names=None):
        self.insert_table = table
        self.inserted = rows
        self.insert_columns = column_names


# --- _tokenize ---


def test_tokenize_lowercases_and_splits_on_non_alnum():
    assert _tokenize("Claude Code, Released!") == {"claude", "code", "released"}


def test_tokenize_drops_stopwords():
    assert "the" not in _tokenize("the new release")
    assert "new" not in _tokenize("the new release")


def test_tokenize_drops_short_tokens():
    # length <= 2 tokens are dropped even if not stopwords
    assert _tokenize("AI is ok") == set()


def test_tokenize_none_or_empty_returns_empty_set():
    assert _tokenize(None) == set()
    assert _tokenize("") == set()


# --- _jaccard ---


def test_jaccard_identical_sets_is_one():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_sets_is_zero():
    assert _jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_partial_overlap():
    assert _jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_jaccard_empty_set_is_zero():
    assert _jaccard(set(), {"a"}) == 0.0
    assert _jaccard(set(), set()) == 0.0


# --- _UnionFind ---


def test_union_find_starts_disjoint():
    uf = _UnionFind(["a", "b", "c"])
    assert uf.find("a") != uf.find("b")


def test_union_find_merges_two_items():
    uf = _UnionFind(["a", "b", "c"])
    uf.union("a", "b")
    assert uf.find("a") == uf.find("b")
    assert uf.find("a") != uf.find("c")


def test_union_find_transitively_merges_via_chain():
    uf = _UnionFind(["a", "b", "c", "d"])
    uf.union("a", "b")
    uf.union("b", "c")
    assert uf.find("a") == uf.find("c")
    assert uf.find("a") != uf.find("d")


def test_union_find_union_is_idempotent():
    uf = _UnionFind(["a", "b"])
    uf.union("a", "b")
    uf.union("a", "b")
    assert uf.find("a") == uf.find("b")


# --- compute_clusters ---


def test_compute_clusters_groups_similar_titles_into_one_cluster_id():
    rows = [
        (
            "hash_forbes",
            "Nine Out Of 10 Leaders Say Life Skills More Important",
            datetime(2026, 7, 26, 12, 0, 0),
        ),
        (
            "hash_biztoc",
            "Nine Out Of 10 Leaders Say Life Skills More Important Than AI",
            datetime(2026, 7, 26, 12, 12, 0),
        ),
    ]
    client = FakeClickHouseClient(rows)

    written = compute_clusters(client=client)

    assert written == 2
    assert client.insert_table == "mart.article_clusters"
    cluster_ids = {row[1] for row in client.inserted}
    # Earliest-published member (hash_forbes) becomes the stable cluster_id (see ADR 0005).
    assert cluster_ids == {"hash_forbes"}


def test_compute_clusters_keeps_dissimilar_titles_in_separate_clusters():
    rows = [
        ("hash_a", "Sony discontinues PlayStation physical discs", datetime(2026, 7, 26)),
        ("hash_b", "Matt Damon lost 167 pounds for Nolan film", datetime(2026, 7, 26)),
    ]
    client = FakeClickHouseClient(rows)

    compute_clusters(client=client)

    cluster_ids = {row[0]: row[1] for row in client.inserted}
    assert cluster_ids["hash_a"] != cluster_ids["hash_b"]


def test_compute_clusters_respects_time_window_even_with_similar_titles():
    rows = [
        ("hash_old", "Company announces major layoffs today", datetime(2026, 7, 1, 0, 0, 0)),
        ("hash_new", "Company announces major layoffs today", datetime(2026, 7, 26, 0, 0, 0)),
    ]
    client = FakeClickHouseClient(rows)

    compute_clusters(client=client)

    cluster_ids = {row[0]: row[1] for row in client.inserted}
    # More than 24h apart - even with an identical title, these shouldn't merge.
    assert cluster_ids["hash_old"] != cluster_ids["hash_new"]


def test_compute_clusters_returns_zero_for_no_articles():
    client = FakeClickHouseClient([])
    assert compute_clusters(client=client) == 0
    assert client.inserted is None


def test_similarity_threshold_is_the_documented_value():
    assert SIMILARITY_THRESHOLD == 0.5
