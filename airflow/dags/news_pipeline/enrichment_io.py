"""Enriches article clusters (see clustering_io.py), not individual articles: one LLM call
produces one summary/topic/sentiment for the underlying story, regardless of how many outlets
reported it. Selects cluster_ids from article_clusters with no successful summary_clusters row
yet (anti-join), gathers each cluster's member articles, calls the LLM once per cluster, and
inserts one outcome row per cluster. Per-cluster failures don't stop the run -
enrich_pending_clusters always returns counts rather than raising, so the caller can record them
in pipeline_run_log *before* deciding whether the overall failure rate warrants failing the task
(see llm_enrichment in the DAG).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from .clickhouse_hook import ClickHouseHook
from .llm_client import ClusterArticle, enrich_cluster

log = logging.getLogger(__name__)

_SELECT_PENDING_SQL = """
select
    c.cluster_id,
    -- groupArray on a Nullable(String) column silently drops NULL entries, which desyncs
    -- separate title/description/source groupArrays whenever any member has a NULL field
    -- (e.g. no description) - grouping as one tuple per row keeps them aligned.
    groupArray((a.title, a.description, a.source_name)) as members
from mart.article_clusters c
inner join mart.mart_articles a on a.url_hash = c.url_hash
where c.cluster_id not in (
    select cluster_id from mart.summary_clusters final where enrichment_status = 'success'
)
group by c.cluster_id
"""

_INSERT_COLUMNS = [
    "cluster_id", "summary", "keywords", "topic", "sentiment", "sentiment_score",
    "llm_model", "enrichment_status", "raw_llm_response", "article_count", "enriched_at",
]


def enrich_pending_clusters(*, api_key: str, base_url: str, model: str) -> tuple[int, int, int]:
    """Returns (attempted, succeeded, failed). Never raises for per-cluster failures - the
    caller decides whether the failure rate is acceptable."""
    client = ClickHouseHook().get_client()
    pending = client.query(_SELECT_PENDING_SQL).result_rows
    if not pending:
        return 0, 0, 0

    log.info("llm_enrichment: %d pending clusters to process", len(pending))

    succeeded = 0
    failed = 0
    for i, (cluster_id, members) in enumerate(pending, start=1):
        articles = [
            ClusterArticle(title=t, description=d, source_name=s)
            for t, d, s in members
        ]
        enriched_at = datetime.now(timezone.utc)
        try:
            enrichment = enrich_cluster(
                api_key=api_key, base_url=base_url, model=model, articles=articles,
            )
            row = (
                cluster_id, enrichment.summary, enrichment.keywords, enrichment.topic,
                enrichment.sentiment, enrichment.sentiment_score, model, "success", None,
                len(articles), enriched_at,
            )
            succeeded += 1
        except Exception as exc:
            raw_response = getattr(exc, "raw_response", "") or str(exc)[:2000]
            row = (cluster_id, "", [], "", "", None, model, "failed", raw_response, len(articles), enriched_at)
            failed += 1

        # Inserted one row at a time, not batched at the end: if the task later fails or times
        # out mid-batch, clusters already enriched stay recorded and won't be re-billed on rerun.
        client.insert("mart.summary_clusters", [row], column_names=_INSERT_COLUMNS)
        log.info(
            "llm_enrichment: %d/%d done (cluster_id=%s, articles=%d, status=%s)",
            i, len(pending), cluster_id, len(articles), row[7],
        )

    return succeeded + failed, succeeded, failed
