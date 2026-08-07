"""Phase 7 content-based re-ranking: blends topic/keyword overlap with a logged-in user's
previously-liked clusters into the discover feed's ordering - not collaborative filtering or
embeddings (deliberately deferred, see docs/adr/0010-recommendations.md). A pure function, no
ClickHouse/Postgres imports, so it's unit-testable in isolation (see
tests/fastapi_app/test_ranking.py), matching this project's established testing pattern (see
auth.py, llm_client.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from schemas import SummaryCard

_TOPIC_MATCH_WEIGHT = 2


@dataclass
class AffinityCard:
    """Just enough of a liked cluster to build a profile from - the profile query only ever
    selects cluster_id/topic/keywords, not a full SummaryCard."""

    cluster_id: str
    topic: str
    keywords: list[str]


@dataclass
class AffinityProfile:
    topic_weights: dict[str, int]
    keyword_weights: dict[str, int]
    liked_cluster_ids: frozenset[str]

    @property
    def is_empty(self) -> bool:
        return not self.topic_weights and not self.keyword_weights


def build_affinity_profile(liked: list[AffinityCard]) -> AffinityProfile:
    topic_weights: dict[str, int] = {}
    keyword_weights: dict[str, int] = {}
    for item in liked:
        topic_weights[item.topic] = topic_weights.get(item.topic, 0) + 1
        for kw in item.keywords:
            keyword_weights[kw] = keyword_weights.get(kw, 0) + 1
    return AffinityProfile(
        topic_weights, keyword_weights, frozenset(item.cluster_id for item in liked)
    )


def _affinity_score(card: SummaryCard, profile: AffinityProfile) -> int:
    # A liked cluster necessarily matches itself on every topic/keyword it contributed to the
    # profile. Without subtracting that self-contribution back out, a liked card would always
    # score highest of all and permanently pin itself at the top of the feed, instead of just
    # boosting other, genuinely similar stories.
    is_self = card.cluster_id in profile.liked_cluster_ids
    topic_count = profile.topic_weights.get(card.topic, 0) - (1 if is_self else 0)
    score = max(topic_count, 0) * _TOPIC_MATCH_WEIGHT
    for kw in card.keywords:
        keyword_count = profile.keyword_weights.get(kw, 0) - (1 if is_self else 0)
        score += max(keyword_count, 0)
    return score


def rank_by_affinity(cards: list[SummaryCard], profile: AffinityProfile) -> list[SummaryCard]:
    """Stable re-sort: affinity score descending, ties broken by the incoming order. `cards`
    must already be recency-sorted (desc) on input - Python's sort is stable, so recency is the
    tiebreak/blend signal rather than something scored explicitly."""
    if profile.is_empty:
        return cards
    return sorted(cards, key=lambda c: _affinity_score(c, profile), reverse=True)
