-- Migration for an already-running deployment (docker-entrypoint-initdb.d scripts only run
-- once, against an empty data directory - see ../002_create_raw_articles.sql for the
-- fresh-install shape this brings existing databases in line with). Lives in migrations/ (not
-- directly under sql/clickhouse/) because ClickHouse's init entrypoint only scans the top level
-- of /docker-entrypoint-initdb.d/, not subdirectories - a fresh install would otherwise try to
-- rename a column that never existed and fail.
-- Run manually: docker compose exec clickhouse clickhouse-client --queries-file /docker-entrypoint-initdb.d/migrations/005_migrate_category_provider.sql

ALTER TABLE raw.newsapi_articles RENAME COLUMN query_keyword TO category;
ALTER TABLE raw.newsapi_articles ADD COLUMN IF NOT EXISTS source_provider Nullable(String) DEFAULT 'newsapi';

-- ods_articles is dbt's `incremental` materialization, which reuses the existing physical
-- table rather than rebuilding it - unlike `mart_articles`'s `table` materialization (full
-- CREATE-and-swap each run, which self-heals automatically), ods_articles needs the same
-- manual column migration or `dbt build` fails with "Unknown expression identifier
-- `query_keyword`" on the next incremental insert.
ALTER TABLE ods.ods_articles RENAME COLUMN query_keyword TO category;
ALTER TABLE ods.ods_articles ADD COLUMN IF NOT EXISTS source_provider Nullable(String) DEFAULT 'newsapi';
