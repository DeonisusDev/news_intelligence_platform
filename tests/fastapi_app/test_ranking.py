"""Pure unit tests for Phase 7's content-based re-ranking (see ranking.py) - no ClickHouse,
Postgres, or HTTP involved, matching the project's "business logic testable without a real
database" convention (see auth.py, llm_client.py).
"""

from ranking import AffinityCard, build_affinity_profile, rank_by_affinity
from schemas import SummaryCard

_NOW = "2026-08-05T10:00:00"


def _card(cluster_id, topic, keywords, enriched_at=_NOW):
    return SummaryCard(
        cluster_id=cluster_id,
        summary="s",
        topic=topic,
        sentiment="neutral",
        sentiment_score=0.0,
        keywords=keywords,
        article_count=1,
        enriched_at=enriched_at,
        first_published_at=enriched_at,
        image_url=None,
    )


def test_build_affinity_profile_counts_topics_and_keywords():
    liked = [
        AffinityCard(cluster_id="l1", topic="Technology", keywords=["ai", "chips"]),
        AffinityCard(cluster_id="l2", topic="Technology", keywords=["ai"]),
        AffinityCard(cluster_id="l3", topic="Sports", keywords=["olympics"]),
    ]

    profile = build_affinity_profile(liked)

    assert profile.topic_weights == {"Technology": 2, "Sports": 1}
    assert profile.keyword_weights == {"ai": 2, "chips": 1, "olympics": 1}


def test_empty_profile_is_empty():
    assert build_affinity_profile([]).is_empty is True


def test_rank_by_affinity_leaves_order_unchanged_for_an_empty_profile():
    cards = [_card("c1", "Technology", ["ai"]), _card("c2", "Sports", ["olympics"])]
    profile = build_affinity_profile([])

    ranked = rank_by_affinity(cards, profile)

    assert [c.cluster_id for c in ranked] == ["c1", "c2"]


def test_rank_by_affinity_does_not_let_a_liked_card_dominate_via_self_match():
    # c1 IS the liked cluster - its own topic/keywords trivially match themselves, so without
    # excluding that self-contribution it would always outscore every other card and pin itself
    # at the top of the feed forever, regardless of genuine similarity to anything else.
    cards = [_card("c2", "Technology", ["ai"]), _card("c1", "Technology", ["ai"])]
    profile = build_affinity_profile(
        [AffinityCard(cluster_id="c1", topic="Technology", keywords=["ai"])]
    )

    ranked = rank_by_affinity(cards, profile)

    # c2 is a genuinely similar *other* card and should score at least as well as c1 now that
    # c1 no longer gets credit for matching itself - the stable sort keeps c2 first (its
    # incoming position), not forced to the back behind the liked card.
    assert [c.cluster_id for c in ranked] == ["c2", "c1"]


def test_rank_by_affinity_still_boosts_other_cards_similar_to_a_liked_one():
    cards = [_card("unrelated", "Sports", []), _card("similar", "Technology", ["ai"])]
    profile = build_affinity_profile(
        [AffinityCard(cluster_id="liked", topic="Technology", keywords=["ai"])]
    )

    ranked = rank_by_affinity(cards, profile)

    assert [c.cluster_id for c in ranked] == ["similar", "unrelated"]


def test_rank_by_affinity_promotes_matching_topic_above_recency_order():
    # c1 is more recent (earlier in the input list) but c2 matches the user's liked topic.
    cards = [_card("c1", "Sports", []), _card("c2", "Technology", [])]
    profile = build_affinity_profile(
        [AffinityCard(cluster_id="liked", topic="Technology", keywords=[])]
    )

    ranked = rank_by_affinity(cards, profile)

    assert [c.cluster_id for c in ranked] == ["c2", "c1"]


def test_rank_by_affinity_scores_keyword_overlap_too():
    cards = [
        _card("no-overlap", "Sports", ["olympics"]),
        _card("one-keyword", "Sports", ["ai"]),
        _card("two-keywords", "Sports", ["ai", "chips"]),
    ]
    profile = build_affinity_profile(
        [AffinityCard(cluster_id="liked", topic="Technology", keywords=["ai", "chips"])]
    )

    ranked = rank_by_affinity(cards, profile)

    assert [c.cluster_id for c in ranked] == ["two-keywords", "one-keyword", "no-overlap"]


def test_rank_by_affinity_weights_topic_match_above_a_single_keyword_match():
    cards = [
        _card("topic-match", "Technology", []),
        _card("keyword-match", "Sports", ["ai"]),
    ]
    profile = build_affinity_profile(
        [AffinityCard(cluster_id="liked", topic="Technology", keywords=["ai"])]
    )

    ranked = rank_by_affinity(cards, profile)

    assert [c.cluster_id for c in ranked] == ["topic-match", "keyword-match"]


def test_rank_by_affinity_is_stable_for_tied_scores():
    cards = [_card("first", "Sports", []), _card("second", "Sports", [])]
    profile = build_affinity_profile(
        [AffinityCard(cluster_id="liked", topic="Technology", keywords=[])]
    )

    ranked = rank_by_affinity(cards, profile)

    assert [c.cluster_id for c in ranked] == ["first", "second"]
