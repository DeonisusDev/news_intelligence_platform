"""OpenAI-SDK-compatible client for cluster enrichment: one LLM call summarizes an entire
cluster of articles covering the same underlying story (see clustering_io.py), not one call
per article - this is both the point (one summary per story, not one per outlet) and a
practical necessity given free-tier LLM quotas.

Free OpenRouter models don't reliably honor `response_format=json_schema`, so this prompts for
JSON directly and validates/retries rather than depending on structured-output support. Swapping
LLM providers (e.g. to a local Ollama server, or a paid OpenAI model) only requires changing
base_url/model in config - no code change.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Bind-mounted (see docker-compose.yml) so the prompt is tunable without rebuilding the image;
# read at call time, not import time, so edits take effect on the very next task run.
PROMPT_PATH = Path("/opt/airflow/prompts/enrichment_prompt.txt")

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class ClusterArticle:
    title: str | None
    description: str | None
    source_name: str | None


class ClusterEnrichment(BaseModel):
    summary: str
    keywords: list[str] = Field(default_factory=list)
    topic: str
    sentiment: str
    sentiment_score: float | None = None


class EnrichmentError(Exception):
    """Raised when the LLM response can't be parsed/validated. Carries the raw response text
    so the caller can persist it for debugging even on failure."""

    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


def _extract_enrichment(raw_text: str) -> ClusterEnrichment:
    match = _JSON_BLOCK_RE.search(raw_text)
    if not match:
        raise EnrichmentError(f"No JSON object found in LLM response: {raw_text[:500]!r}", raw_response=raw_text)
    try:
        data = json.loads(match.group(0))
        return ClusterEnrichment.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise EnrichmentError(f"Invalid LLM response: {exc}", raw_response=raw_text) from exc


def _format_articles_block(articles: list[ClusterArticle]) -> str:
    lines = []
    for i, article in enumerate(articles, start=1):
        source = article.source_name or "unknown source"
        lines.append(f"{i}. [{source}] {article.title or ''}\n   {article.description or ''}")
    return "\n".join(lines)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(EnrichmentError),
)
def enrich_cluster(
    *,
    api_key: str,
    base_url: str,
    model: str,
    articles: list[ClusterArticle],
) -> ClusterEnrichment:
    # Explicit timeout/max_retries: the default httpx timeout is 600s, and a stalled free-tier
    # connection can sit there silently - a large batch of clusters must fail fast per cluster,
    # not potentially hang for hours. Rate-limit/timeout errors propagate to the caller uncaught
    # (see enrichment_io.py's per-cluster try/except) rather than being retried here - only
    # response-parsing failures (EnrichmentError) get our own retry.
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0, max_retries=1)
    prompt = PROMPT_PATH.read_text().format(articles_block=_format_articles_block(articles))

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    raw_text = response.choices[0].message.content or ""
    return _extract_enrichment(raw_text)
