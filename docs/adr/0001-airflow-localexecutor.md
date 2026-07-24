# ADR 0001: Airflow with LocalExecutor, not CeleryExecutor

## Status
Accepted

## Context
The pipeline is a single daily batch DAG running on one node. CeleryExecutor adds Redis plus
worker containers, which buys horizontal scalability this project has no use for.

## Decision
Use Airflow 3.x with LocalExecutor and `max_active_runs=1`. All components (api-server,
scheduler, dag-processor, triggerer) run against one Postgres backend on a single host.

## Consequences
- Fewer moving parts, lower RAM footprint, simpler docker-compose stack.
- No horizontal scaling story — acceptable for a daily batch job of a few hundred rows.
- At real production scale with many concurrent DAGs, CeleryExecutor or KubernetesExecutor
  would be the natural next step; documented here as a deliberate, scale-aware simplification
  rather than an oversight.
