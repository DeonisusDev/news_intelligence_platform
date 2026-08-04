# ADR 0009: User accounts - email/password JWT, not anonymous IDs or OAuth

## Status
Accepted

## Context
Phase 7 (recommendations) needs a stable identity to attach `cluster_feedback` votes to. Two
options were on the table: an anonymous localStorage-generated UUID per browser, or real
accounts. The product-vision discussion (2026-07-29) settled on real accounts - each person
should get their own feed by interests across devices, which an anonymous per-browser ID can't
give them. This became its own phase (6.5), sequenced between the frontend (6) and
recommendations (7), since Phase 7's `cluster_feedback.user_id` should reference a real
`users.id` from the start rather than a throwaway identifier that gets migrated away later.

## Decision
**Email + password, not OAuth/social login.** A `users` table (`id`, `email UNIQUE`,
`password_hash`, `created_at` - see `sql/postgres/004_create_users.sql`), bcrypt-hashed
passwords (the `bcrypt` package directly, not `passlib` - fewer version-compat footguns), no
email verification and no password reset flow. All three are disproportionate overhead for a
portfolio project with no real inbox/deliverability infrastructure behind it; revisit only if a
concrete reason emerges.

**JWT in an httpOnly cookie, not a client-read token.** `POST /auth/login` issues a 24h JWT
(`sub`=user id, `email`) signed with `JWT_SECRET` and sets it via `Response.set_cookie(httponly=
True, samesite="lax")`. The frontend never touches the token directly - every `fetch` call just
passes `credentials: "include"` (see `frontend/src/api/auth.ts`). This avoids the XSS-exposure
that comes with storing a token in localStorage/a JS-readable cookie.

**Stateless verification - no DB round-trip per protected request.** `get_current_user`
(`fastapi_app/dependencies.py`) decodes and trusts the JWT's claims directly; it doesn't re-query
`users` on every request. Simpler and matches the "no logout-everywhere/session-revocation"
scope - if that's ever needed, it would require moving to a server-side session store, which is
explicitly not being built now.

**`auth.py` has no FastAPI/DB imports.** Password hashing (`hash_password`/`verify_password`)
and JWT issuance/validation (`create_access_token`/`decode_access_token`) are pure functions,
matching the project's established pattern (see `enrich_cluster`'s injectable `client` param,
Post-Phase-5 test suite) of keeping business logic importable and unit-testable without a real
Postgres connection. `routers/auth.py` is the only thing that talks to the database.

**Register does not auto-issue a cookie; login does.** `POST /auth/register` returns the new
`UserPublic` record but sets no session - a user still has to log in afterward. Keeps the two
concerns (account creation vs. establishing a session) cleanly separated in the API, even though
the frontend's `AuthDialog` chains register→login into one submit for a smoother first-run UX.

## Consequences
- `cors_allowed_origins` (already not a wildcard, see `config.py`) and `CORSMiddleware`'s
  `allow_credentials=True` (already set when the frontend shipped in Phase 6) turned out to be
  exactly the CORS shape cookie-based auth needs - no changes required there.
- Existing deployments need `sql/postgres/migrations/005_create_users.sql` applied manually
  (`docker-entrypoint-initdb.d` only runs against an empty data volume); a fresh `docker compose
  up` picks up `sql/postgres/004_create_users.sql` automatically.
- `JWT_SECRET` is a new required env var (`.env.example`, `docker-compose.yml`'s `fastapi`
  service) - no default, matching the `AIRFLOW_API_SECRET_KEY`/`AIRFLOW_JWT_SECRET` convention
  already in the codebase.
- Verified against the live stack end-to-end (not just unit tests): register, duplicate-email
  409, wrong-password 401, `/auth/me` 401 with no cookie and 200 with a valid one, logout clears
  the cookie - all via real `curl` calls, then the same flow again through the actual `AuthDialog`
  UI in a real (headless) browser, including dark mode and the inline error state.
- Phase 7's `get_current_user` dependency is ready to reuse as-is for the feedback endpoint and
  for re-ranking `GET /discover` per logged-in user.
