# ADR 0010: Content-based re-ranking, not collaborative filtering or embeddings

## Status
Accepted

## Context
Phase 7 adds thumbs up/down voting and personalizes `GET /discover` for logged-in users. The
plan (`serene-drifting-clover.md` §8) specced content-based affinity - topic/keyword overlap
with a user's previously-liked clusters, blended with recency - explicitly ruling out
collaborative filtering or embeddings (Phase 10's embedding work is a separate, later concern).
This builds directly on Phase 6.5's real `users`/`get_current_user`, replacing the
anonymous-client-UUID idea that was originally sketched for this phase.

## Decision
**`cluster_feedback` in Postgres, not ClickHouse.** `(user_id REFERENCES users(id), cluster_id,
vote SMALLINT CHECK (vote IN (-1, 1)), UNIQUE(user_id, cluster_id))` - see
`sql/postgres/005_create_cluster_feedback.sql`. Votes are low-volume, per-user, frequently
upserted rows; that's Postgres's strength, not ClickHouse's (append-heavy analytical scans).
`cluster_id` has no foreign key to `mart.summary_clusters` since that table lives in a different
database - just a matching string column, same as every other cross-database reference in this
codebase.

**Voting is upsert-on-POST, delete-on-DELETE, not a single mutable "current vote" PUT.**
`POST /discover/{cluster_id}/feedback` (`{"vote": 1 | -1}`) upserts via `ON CONFLICT (user_id,
cluster_id) DO UPDATE`; `DELETE /discover/{cluster_id}/feedback` removes the row entirely
(un-voting, not voting 0 - there's no neutral vote value to store). The frontend's thumbs
buttons implement toggle-off themselves: clicking the same direction twice calls DELETE instead
of POST again.

**Re-ranking is a pure function (`ranking.py`), not embedded in the SQL query.** `GET /discover`
pulls a bounded, already-recency-sorted candidate window from ClickHouse (`_CANDIDATE_WINDOW =
200` rows), builds an `AffinityProfile` (topic/keyword counts) from the user's liked clusters,
and calls `rank_by_affinity()` - a stable sort by affinity score, falling back to the incoming
recency order for ties (Python's `sorted` is stable, so "blended with recency" falls out of that
naturally rather than needing an explicit weighted formula). This mirrors the project's existing
pattern of keeping scoring/business logic DB-free and unit-testable (see `auth.py`,
`llm_client.py`'s response parsing) - `tests/fastapi_app/test_ranking.py` covers it with no
ClickHouse/Postgres involved at all, satisfying the plan's explicit *Done when* criterion.

**The candidate window is bounded, so re-ranking is one cheap query, not a full-table scan.**
Trade-off: a logged-in user's infinite scroll can run past the 200-row window and stop early
(`getNextPageParam` sees a shorter-than-`PAGE_SIZE` page and ends the scroll) even if older
matching clusters exist. Acceptable for a portfolio-scale dataset; revisit only if `/discover`
needs to serve much deeper pagination.

**Anonymous/logged-out users get the exact pre-Phase-7 code path**, not a "guest with an empty
profile" pass through the ranking machinery - `list_summary_cards` branches on `current_user is
None` before touching Postgres at all. Zero added latency/DB calls for anonymous browsing, and
zero risk of the refactor changing that feed's behavior.

**`SummaryCard.my_vote` rides along on the same list response**, rather than a second endpoint
the frontend would have to call per card. Free: the votes lookup already happens for ranking on
the logged-in path, so surfacing `{cluster_id: vote}` back onto each card costs nothing extra.

**No cluster_id existence check on feedback submission.** A bad/unknown `cluster_id` just creates
an orphan row that can never match anything in a ranking pass - not a security issue, and
validating it would mean an extra ClickHouse round-trip on every vote for a case that can't do
real damage.

## Consequences
- Existing deployments need `sql/postgres/migrations/006_create_cluster_feedback.sql` applied
  manually (`docker-entrypoint-initdb.d` only runs against an empty data volume); a fresh
  `docker compose up` picks up `sql/postgres/005_create_cluster_feedback.sql` automatically.
- `SummaryCard.tsx`'s root element changed from a `<button>` to a `role="button"` `<div>` (with
  matching `tabIndex`/`onKeyDown` for Enter/Space) so the new thumbs up/down `<Button>`s can live
  inside it without nesting interactive elements inside a `<button>`, which is invalid HTML.
- Verified: 15 new backend unit/endpoint tests (pure ranking-function tests plus feedback/list
  endpoint tests against fake Postgres/ClickHouse), 101/101 total passing; `tsc --noEmit`,
  `oxlint`, and `vite build` all clean on the frontend.
- Real end-to-end verification against the live stack caught a genuine bug: `fetchDiscoverPage`
  in `frontend/src/api/discover.ts` predates Phase 7 and was never sending `credentials:
  "include"`, so the browser silently dropped the session cookie on every `GET /discover` call -
  every logged-in request looked anonymous to the backend (no re-ranking, `my_vote` always
  `null`), even though `/auth/login`/`/auth/me` worked fine (those calls already had
  `credentials: "include"` from Phase 6.5). Caught by comparing a raw `fetch()` from inside the
  page (which returned `my_vote: 1`, correct) against the same value read out of the actual React
  fiber tree (`null`) after a real vote - not something unit tests with fake dependencies would
  have caught, since they call the router directly and never exercise the browser's own
  same-origin-credentials behavior. Fixed by adding `credentials: "include"` to that one fetch
  call; re-verified with the same scripted vote sequence afterward.
