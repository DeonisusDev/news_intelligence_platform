-- Migration for an already-running deployment (docker-entrypoint-initdb.d scripts only run
-- once, against an empty data directory - see ../004_create_summary_clusters.sql for the
-- fresh-install shape this brings existing databases in line with). Lives in migrations/ (not
-- directly under sql/clickhouse/) because ClickHouse's init entrypoint only scans the top level
-- of /docker-entrypoint-initdb.d/, not subdirectories.
-- Run manually: docker compose exec clickhouse clickhouse-client --queries-file /docker-entrypoint-initdb.d/migrations/006_add_rich_event_detail_columns.sql

ALTER TABLE mart.summary_clusters ADD COLUMN IF NOT EXISTS key_facts_organizations Array(String);
ALTER TABLE mart.summary_clusters ADD COLUMN IF NOT EXISTS key_facts_locations Array(String);
ALTER TABLE mart.summary_clusters ADD COLUMN IF NOT EXISTS key_facts_people Array(String);
ALTER TABLE mart.summary_clusters ADD COLUMN IF NOT EXISTS why_it_matters String DEFAULT '';
ALTER TABLE mart.summary_clusters ADD COLUMN IF NOT EXISTS before_state Nullable(String);
ALTER TABLE mart.summary_clusters ADD COLUMN IF NOT EXISTS after_state Nullable(String);
ALTER TABLE mart.summary_clusters ADD COLUMN IF NOT EXISTS consensus_points Array(String);
ALTER TABLE mart.summary_clusters ADD COLUMN IF NOT EXISTS disagreement_points Array(String);
ALTER TABLE mart.summary_clusters ADD COLUMN IF NOT EXISTS source_perspectives Array(Tuple(String, String));
