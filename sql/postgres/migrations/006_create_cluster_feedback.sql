-- Migration for an already-running deployment (docker-entrypoint-initdb.d scripts only run
-- once, against an empty data directory - see ../005_create_cluster_feedback.sql for the
-- fresh-install shape this brings existing databases in line with). Lives in migrations/ (not
-- directly under sql/postgres/) because Postgres's init entrypoint only scans the top level of
-- /docker-entrypoint-initdb.d/, not subdirectories.
-- Run manually: docker compose exec -T postgres psql -U <user> -d newsdata -f - < this file
\c newsdata

CREATE TABLE IF NOT EXISTS cluster_feedback (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cluster_id  TEXT NOT NULL,
    vote        SMALLINT NOT NULL CHECK (vote IN (-1, 1)),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_cluster_feedback_user_id ON cluster_feedback (user_id);
