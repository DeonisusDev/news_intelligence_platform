-- Runs against the "newsdata" application database (see 001_create_newsdata_db.sql).
\c newsdata

-- Phase 6.5: real user accounts backing auth and (Phase 7+) personalization. Deliberately
-- minimal - no email verification/password reset/OAuth columns, see docs/adr/0009-user-accounts.md.
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
