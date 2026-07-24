# ADR 0002: ClickHouse as the sole analytical/transform engine

## Status
Accepted

## Context
The initial design considered running dbt across two engines (Postgres for stage/ods, ClickHouse
for mart). At this project's data volume (hundreds of articles/day), ClickHouse's columnar OLAP
engine is not *necessary* — a single Postgres instance could serve the whole pipeline. It was kept
anyway, deliberately, because a core goal of this project is to demonstrate OLAP modeling
(ReplacingMergeTree, dbt-clickhouse incremental strategies, `FINAL` semantics) as a portfolio skill.

## Decision
Postgres is used only as an idempotent raw landing table. A single dbt project, using the
dbt-clickhouse adapter, does all stage → ods → mart transformation inside ClickHouse. Postgres
is never touched by dbt.

## Consequences
- One dbt profile/engine — no cross-engine synchronization complexity.
- ClickHouse's value here is demonstrative, not load-bearing — worth being explicit about this in
  interviews rather than overstating a scale need that doesn't exist yet.
- `ReplacingMergeTree` dedup is eventual (merge/`FINAL`-only); fine at this volume. At real scale,
  the natural next step would be `argMax`-based dedup views or scheduled `OPTIMIZE ... FINAL`.
