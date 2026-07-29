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

from .llm_client import ClusterArticle, enrich_cluster

log = logging.getLogger(__name__)

_SELECT_PENDING_SQL = """
select
    c.cluster_id,
    -- groupArray on a Nullable(String) column silently drops NULL entries, which desyncs
    -- separate title/description/source groupArrays whenever any member has a NULL field
    -- (e.g. no description) - grouping as one tuple per row keeps them aligned. url_hash is
    -- included (not just used to join) so source_perspectives can be keyed by it - see
    -- llm_client.SourcePerspective's docstring for why not source_name or a bare index.
    groupArray((a.url_hash, a.title, a.description, a.source_name)) as members
from mart.article_clusters c final
inner join mart.mart_articles a on a.url_hash = c.url_hash
where c.cluster_id not in (
    select cluster_id from mart.summary_clusters final where enrichment_status = 'success'
)
group by c.cluster_id
"""

_INSERT_COLUMNS = [
    "cluster_id",
    "summary",
    "keywords",
    "topic",
    "sentiment",
    "sentiment_score",
    "llm_model",
    "enrichment_status",
    "raw_llm_response",
    "article_count",
    "enriched_at",
    "key_facts_organizations",
    "key_facts_locations",
    "key_facts_people",
    "why_it_matters",
    "before_state",
    "after_state",
    "consensus_points",
    "disagreement_points",
    "source_perspectives",
]


def enrich_pending_clusters(
    *, api_key: str, base_url: str, model: str, client=None
) -> tuple[int, int, int]:
    """Returns (attempted, succeeded, failed). Never raises for per-cluster failures - the
    caller decides whether the failure rate is acceptable.

    `client` is injectable (defaults to a real ClickHouseHook client) so tests can pass a fake
    without needing Airflow installed - see clustering_io.compute_clusters for the same pattern.
    """
    if client is None:
        from .clickhouse_hook import ClickHouseHook

        client = ClickHouseHook().get_client()
    pending = client.query(_SELECT_PENDING_SQL).result_rows
    if not pending:
        return 0, 0, 0

    log.info("llm_enrichment: %d pending clusters to process", len(pending))

    succeeded = 0
    failed = 0
    for i, (cluster_id, members) in enumerate(pending, start=1):
        url_hashes = [m[0] for m in members]
        articles = [ClusterArticle(title=m[1], description=m[2], source_name=m[3]) for m in members]
        enriched_at = datetime.now(timezone.utc)
        try:
            enrichment = enrich_cluster(
                api_key=api_key,
                base_url=base_url,
                model=model,
                articles=articles,
            )
            # Keyed by url_hash (not index or source_name) so a lookup on the FastAPI side is
            # unambiguous even if the model returns a duplicate/out-of-range index - out-of-range
            # entries are just dropped here rather than crashing a whole cluster's enrichment.
            source_perspectives = [
                (url_hashes[p.index - 1], p.focus)
                for p in enrichment.source_perspectives
                if 1 <= p.index <= len(url_hashes)
            ]
            row = (
                cluster_id,
                enrichment.summary,
                enrichment.keywords,
                enrichment.topic,
                enrichment.sentiment,
                enrichment.sentiment_score,
                model,
                "success",
                None,
                len(articles),
                enriched_at,
                enrichment.key_facts.organizations,
                enrichment.key_facts.locations,
                enrichment.key_facts.people,
                enrichment.why_it_matters,
                enrichment.before_state,
                enrichment.after_state,
                enrichment.consensus_points,
                enrichment.disagreement_points,
                source_perspectives,
            )
            succeeded += 1
        except Exception as exc:
            raw_response = getattr(exc, "raw_response", "") or str(exc)[:2000]
            row = (
                cluster_id,
                "",
                [],
                "",
                "",
                None,
                model,
                "failed",
                raw_response,
                len(articles),
                enriched_at,
                [],
                [],
                [],
                "",
                None,
                None,
                [],
                [],
                [],
            )
            failed += 1

        # Inserted one row at a time, not batched at the end: if the task later fails or times
        # out mid-batch, clusters already enriched stay recorded and won't be re-billed on rerun.
        client.insert("mart.summary_clusters", [row], column_names=_INSERT_COLUMNS)
        log.info(
            "llm_enrichment: %d/%d done (cluster_id=%s, articles=%d, status=%s)",
            i,
            len(pending),
            cluster_id,
            len(articles),
            row[7],
        )

    return succeeded + failed, succeeded, failed
