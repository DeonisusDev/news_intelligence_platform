# ADR 0007: Client-side React SPA over the existing FastAPI, not SSR

## Status
Accepted

## Context
Phase 4 already exposes the full Discovery-feed shape (`GET /discover`, `GET
/discover/{cluster_id}`, `/stats/*`) as plain JSON. The product vision (see product-vision
memory) calls for a web feed now and explicitly defers a native mobile app - a responsive web
frontend covers "usable on a phone" via the browser, and native app-store deployment is
disproportionate overhead for this project's scope.

## Decision
- **Vite + React + TypeScript, plain client-side rendering - not Next.js/SSR.** The entire
  frontend is rendering data already fetched as JSON from FastAPI; a server-rendering framework
  would add build/deploy complexity (a Node runtime in production, hydration concerns) without
  solving a problem this app actually has (no SEO requirement, no first-paint-sensitive content).
- **TanStack Query (`useInfiniteQuery`)** for the feed's data-fetching/caching/pagination, rather
  than hand-rolled `fetch`+`useEffect` state machines.
- **shadcn/ui (Radix primitives + Tailwind)** for the Dialog (source-list expand) and
  DropdownMenu (topic filter) - accessible focus-trap/keyboard behavior out of the box, without a
  full component-library runtime dependency (MUI, Ant).
- **Expand-to-sources is a Dialog, not a routed page.** Chosen over inline-accordion (would push
  other cards down the feed) and over a `/discover/:id` route (would need `react-router` wired in
  for a single use, more setup than value at this stage - can revisit if Phase 6.1's richer detail
  view outgrows a modal).
- **Topic filtering is a single dropdown trigger (`All topics ▾`), not a chip row.** The first
  implementation used an always-visible horizontal chip strip; feedback after seeing it rendered
  against real data (compared directly against Perplexity Discover's own layout) was that it
  competed for attention with the feed itself. Perplexity hides the same control behind a
  `Темы ▾` dropdown in the nav row - copied that pattern directly via
  `DropdownMenuRadioGroup`/`RadioItem` (built-in checkmark on the active selection).
- **Infinite scroll** (`IntersectionObserver` sentinel + `useInfiniteQuery`) over a "Load more"
  button or numbered pagination - matches the feed framing better, and `GET /discover`'s
  `limit`/`offset` params already support it directly.
- **A cheap, explicitly-labeled heuristic "consensus" badge** (High/Medium/Low, bucketed off
  `article_count`) ships on the card now; a real LLM-derived confidence score is deferred to
  Phase 6.1, once there's real enrichment data to base it on rather than a proxy.
- **Docker: multi-stage build, Node only at build time.** `frontend/Dockerfile` builds the static
  bundle with `node:22-slim`, then serves it with a plain `nginx:1.27-alpine` - no Node runtime
  in the deployed image. `VITE_API_BASE_URL` is a build ARG (baked into the JS bundle, since it's
  read by the *browser*, not the container - `fastapi:8000`, the Docker network the two
  containers share, is unreachable from the user's actual browser).

## Consequences
- FastAPI needed CORS middleware (`fastapi_app/main.py`), previously absent since nothing
  browser-based called it. Allowed origins are configurable (`CORS_ALLOWED_ORIGINS`, default
  `http://localhost:3000`), not wildcarded, since Phase 6.5 will carry auth cookies.
- `GET /discover`'s response gained `first_published_at` and `image_url` per card (a `cluster_id`
  → `min(published_at)`/`any(url_to_image)` CTE joined onto `summary_clusters` in
  `routers/discover.py`) so the feed can render a hero image and "published X ago" without an
  N+1 detail fetch per card just to populate the list view.
- CI gained a `frontend` job (`npm ci`, `oxlint`, `tsc -b`, `vite build`) alongside the existing
  `lint`/`test`/`dbt-build`/`compose-smoke` jobs - the scaffolded lint tool is `oxlint`, not
  eslint (matches the current `create-vite`/shadcn default, faster and equivalent for this
  project's needs).
- No routing library is in the dependency tree yet. Phase 6.1's richer detail view and Phase
  6.5's auth screens may be the point where a dedicated `/discover/:id` and `/login` route
  actually earns its setup cost - revisit then rather than adding it speculatively now.
