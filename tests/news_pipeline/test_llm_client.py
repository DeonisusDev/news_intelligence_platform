"""Unit tests for the LLM response parsing/validation logic - the part that has to be robust
against free-tier models not reliably honoring structured output (see llm_client.py's module
docstring). No network calls: enrich_cluster itself (which does the actual API call) isn't
exercised here.
"""

import pytest
from news_pipeline.llm_client import (
    ClusterArticle,
    EnrichmentError,
    _extract_enrichment,
    _format_articles_block,
)


def test_extract_enrichment_parses_clean_json():
    raw = '{"summary": "s", "keywords": ["a", "b"], "topic": "Tech", "sentiment": "neutral"}'
    result = _extract_enrichment(raw)
    assert result.summary == "s"
    assert result.keywords == ["a", "b"]
    assert result.topic == "Tech"
    assert result.sentiment == "neutral"
    assert result.sentiment_score is None


def test_extract_enrichment_finds_json_embedded_in_prose():
    raw = (
        "Sure, here's the analysis:\n"
        '{"summary": "s", "topic": "Business", "sentiment": "positive", "sentiment_score": 0.8}'
        "\nLet me know if you need anything else!"
    )
    result = _extract_enrichment(raw)
    assert result.summary == "s"
    assert result.sentiment_score == 0.8


def test_extract_enrichment_defaults_keywords_to_empty_list():
    raw = '{"summary": "s", "topic": "Tech", "sentiment": "neutral"}'
    result = _extract_enrichment(raw)
    assert result.keywords == []


def test_extract_enrichment_raises_when_no_json_object_present():
    with pytest.raises(EnrichmentError) as exc_info:
        _extract_enrichment("I refuse to answer in JSON today.")
    assert exc_info.value.raw_response == "I refuse to answer in JSON today."


def test_extract_enrichment_raises_on_malformed_json():
    raw = '{"summary": "s", "topic": "Tech", "sentiment": }'
    with pytest.raises(EnrichmentError):
        _extract_enrichment(raw)


def test_extract_enrichment_raises_when_required_field_missing():
    raw = '{"summary": "s"}'  # missing topic/sentiment
    with pytest.raises(EnrichmentError) as exc_info:
        _extract_enrichment(raw)
    assert exc_info.value.raw_response == raw


def test_format_articles_block_numbers_and_includes_source():
    articles = [
        ClusterArticle(title="T1", description="D1", source_name="Forbes"),
        ClusterArticle(title="T2", description="D2", source_name="Biztoc.com"),
    ]
    block = _format_articles_block(articles)
    assert "1. [Forbes] T1" in block
    assert "2. [Biztoc.com] T2" in block


def test_format_articles_block_falls_back_to_unknown_source():
    articles = [ClusterArticle(title="T1", description="D1", source_name=None)]
    block = _format_articles_block(articles)
    assert "[unknown source] T1" in block


def test_format_articles_block_handles_missing_title_and_description():
    articles = [ClusterArticle(title=None, description=None, source_name="Forbes")]
    block = _format_articles_block(articles)
    assert "1. [Forbes] " in block
