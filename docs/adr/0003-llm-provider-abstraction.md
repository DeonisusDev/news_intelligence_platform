# ADR 0003: LLM provider abstraction via OpenAI-SDK base_url swap

## Status
Accepted

## Context
The enrichment step (summary, keywords, topic, sentiment) should not be hard-wired to one vendor.
Building a bespoke plugin/strategy-pattern abstraction was considered, but adds indirection with
no real payoff: every serious LLM provider (OpenAI, OpenRouter, Ollama, vLLM, LM Studio, Groq,
together.ai, ...) now exposes an OpenAI-compatible `/chat/completions` endpoint.

## Decision
Use the official `openai` Python SDK as the one client, configured entirely via env vars
(`OPENROUTER_BASE_URL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`). Swapping providers — e.g. to a
local Ollama instance — is a `.env` change, not a code change.

## Consequences
- No custom abstraction layer to maintain or test.
- Free OpenRouter models do not reliably honor `response_format: json_schema`; the enrichment
  client must treat structured output as best-effort and fall back to prompt-engineered JSON +
  pydantic validation + retry (see `airflow/plugins/news_pipeline/llm_client.py`).
- If a future provider needs a genuinely different calling convention (e.g. a non-OpenAI-shaped
  API), this ADR should be revisited.
