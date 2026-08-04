-- Runs against the "newsdata" application database (see 001_create_newsdata_db.sql).
\c newsdata

-- Phase 7: thumbs up/down votes, one per (user, cluster) - upserted on repeat votes, deleted on
-- un-vote (see fastapi_app/routers/discover.py). cluster_id references mart.summary_clusters in
-- ClickHouse, a different database - no FK possible there, just a matching string column.
CREATE TABLE IF NOT EXISTS cluster_feedback (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cluster_id  TEXT NOT NULL,
    vote        SMALLINT NOT NULL CHECK (vote IN (-1, 1)),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_cluster_feedback_user_id ON cluster_feedback (user_id);
