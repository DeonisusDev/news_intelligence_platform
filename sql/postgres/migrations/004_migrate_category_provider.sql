-- Migration for an already-running deployment (docker-entrypoint-initdb.d scripts only run
-- once, against an empty data directory - see ../002_create_raw_articles.sql for the
-- fresh-install shape this brings existing databases in line with). Lives in migrations/ (not
-- directly under sql/postgres/) because Postgres's init entrypoint only scans the top level of
-- /docker-entrypoint-initdb.d/, not subdirectories - a fresh install would otherwise try to
-- rename a column that never existed and fail.
-- Run manually: docker compose exec -T postgres psql -U <user> -d newsdata -f - < this file
\c newsdata

ALTER TABLE raw_articles RENAME COLUMN query_keyword TO category;
ALTER TABLE raw_articles ADD COLUMN IF NOT EXISTS source_provider TEXT NOT NULL DEFAULT 'newsapi';
