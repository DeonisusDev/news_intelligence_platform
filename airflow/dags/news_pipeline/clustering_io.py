"""Groups articles covering the same underlying story (e.g. 10 outlets reporting "new Claude
version released") into clusters, using title-token Jaccard similarity - no LLM call needed for
this step, which also keeps it cheap and deterministic. Recomputed over the full mart_articles
table each run (same "small enough to just rebuild" pattern as mart_articles/mart_daily_stats -
O(n^2) title comparisons are trivial at this project's data volume; see docs/adr/0005).

A cluster's cluster_id is the url_hash of its earliest-published member, not a hash of the
whole membership set: this keeps the ID stable as long as that first article doesn't change,
so a cluster already enriched with a summary isn't treated as "new" just because one more
outlet picks up the story later. The trade-off - documented in docs/adr/0005 - is that the
summary then won't automatically reflect newcomers; refreshing it would need a manual
delete-and-rerun against summary_clusters for that cluster_id.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .clickhouse_hook import ClickHouseHook

# clickhouse-connect returns ClickHouse's DateTime columns as naive datetimes (ClickHouse's
# DateTime type carries no tz info) - keep comparisons naive too, only using timezone.utc for
# the (unrelated) computed_at write-timestamp below.

_SELECT_ARTICLES_SQL = "select url_hash, title, published_at from mart.mart_articles"

_STOPWORDS = {
    "the",
    "a",
    "an",
    "to",
    "of",
    "in",
    "on",
    "for",
    "and",
    "is",
    "are",
    "at",
    "by",
    "with",
    "as",
    "it",
    "its",
    "from",
    "after",
    "over",
    "into",
    "amid",
    "how",
    "why",
    "what",
    "will",
    "says",
    "said",
    "new",
    "more",
    "than",
    "this",
    "that",
    "be",
    "has",
    "have",
    "had",
    "not",
    "but",
    "or",
    "was",
    "were",
    "been",
    "being",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")

SIMILARITY_THRESHOLD = 0.5
_CLUSTER_WINDOW_SECONDS = 24 * 60 * 60  # only compare articles published within a day of each other


def _tokenize(title: str | None) -> set[str]:
    if not title:
        return set()
    tokens = _TOKEN_RE.findall(title.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return len(a & b) / union if union else 0.0


class _UnionFind:
    def __init__(self, items):
        self.parent = {item: item for item in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def compute_clusters() -> int:
    """Recomputes clusters over all mart_articles and writes assignments into
    mart.article_clusters. Returns the number of (article, cluster) rows written."""
    client = ClickHouseHook().get_client()
    rows = client.query(_SELECT_ARTICLES_SQL).result_rows
    if not rows:
        return 0

    articles = [
        (url_hash, _tokenize(title), published_at) for url_hash, title, published_at in rows
    ]
    uf = _UnionFind(url_hash for url_hash, _, _ in articles)

    for i in range(len(articles)):
        url_i, tokens_i, pub_i = articles[i]
        for j in range(i + 1, len(articles)):
            url_j, tokens_j, pub_j = articles[j]
            if pub_i and pub_j and abs((pub_j - pub_i).total_seconds()) > _CLUSTER_WINDOW_SECONDS:
                continue
            if _jaccard(tokens_i, tokens_j) >= SIMILARITY_THRESHOLD:
                uf.union(url_i, url_j)

    groups: dict[str, list[tuple[str, datetime | None]]] = {}
    for url_hash, _, published_at in articles:
        root = uf.find(url_hash)
        groups.setdefault(root, []).append((url_hash, published_at))

    epoch = datetime.min
    computed_at = datetime.now(timezone.utc)
    output_rows = []
    for members in groups.values():
        members_sorted = sorted(members, key=lambda m: (m[1] or epoch, m[0]))
        cluster_id = members_sorted[0][0]
        for url_hash, _ in members:
            output_rows.append((url_hash, cluster_id, computed_at))

    client.insert(
        "mart.article_clusters",
        output_rows,
        column_names=["url_hash", "cluster_id", "computed_at"],
    )
    return len(output_rows)
