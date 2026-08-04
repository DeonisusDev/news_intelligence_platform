-- Migration for an already-running deployment (docker-entrypoint-initdb.d scripts only run
-- once, against an empty data directory - see ../004_create_users.sql for the fresh-install
-- shape this brings existing databases in line with). Lives in migrations/ (not directly under
-- sql/postgres/) because Postgres's init entrypoint only scans the top level of
-- /docker-entrypoint-initdb.d/, not subdirectories.
-- Run manually: docker compose exec -T postgres psql -U <user> -d newsdata -f - < this file
\c newsdata

CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
