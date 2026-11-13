# ADR 0004 - Static snapshot deploy over a hosted API

- **Status:** Accepted
- **Date:** 2026-07-02

## Context

The dashboard needs a public, always-on demo URL for the portfolio. The obvious
topology is the one we built: a hosted FastAPI service reading the DuckDB
warehouse, with the Next.js app calling it. But hosting a live Python API for a
demo has real downsides:

- A free-tier VM (Oracle Always Free, Fly.io) means cold starts, a process to
  keep alive, an attack surface, and a second thing that can be down when a
  recruiter clicks the link at 11pm.
- The demo data is **curated and changes at most weekly** (the pipeline runs on
  a weekly cron). Serving it from a live query engine is capability the demo
  never exercises.
- $0 hosting is a stated project goal; a live API is the only piece that pushes
  against it.

The data is small (5 competitors, ~33 signals, a handful of reports) and
read-mostly. That shape fits a static bundle.

## Decision

**Bake every API response into static JSON shipped with the web app**, and read
it directly in the browser. There is no backend in production.

1. `scripts/export_static_data.py` drives the *real* FastAPI app through
   Starlette's `TestClient` and writes each response to
   `web/public/api-static/**` (JSON for every endpoint plus rendered report
   PDFs). Because the responses come from the actual app, the JSON shapes match
   the Pydantic schemas exactly - `Page[T]` envelopes, date formats, field
   names - with no hand-maintained fixtures to drift.
2. `web/.env.production` sets `NEXT_PUBLIC_STATIC_DATA=1`. In that mode
   `web/src/lib/api.ts` reads from `/api-static` instead of proxying `/api`, and
   runs filtering, sorting, and pagination for the signals/changes feeds
   **client-side**. The full feeds are exported unpaginated; the client slices
   them.
3. Writes (competitor create/update/delete, "Run pipeline") have no server to
   hit. They apply to a `localStorage` overlay (`web/src/lib/static-store.ts`)
   so the demo stays interactive per-session, and "Run pipeline" shows an honest
   "Demo mode" toast rather than pretending a job started.
4. The competitor detail route (`/competitors/[id]`) uses
   `generateStaticParams` (reading the baked competitor list at build time) with
   `dynamicParams = false`, so the entire app builds to static output - **no
   serverless functions** in the Vercel deploy.
5. The weekly GitHub Actions run regenerates the JSON after `run-all` and commits
   it back, which triggers a Vercel redeploy. Between runs, the committed
   snapshot is served.

The live-backend topology (hosted FastAPI) remains fully supported and
documented in DEPLOYMENT.md - it is the right choice if you want write-through
CRUD or on-demand pipeline runs. Static mode is the default for the public demo.

## Consequences

**Positive**
- Genuinely $0, always-on, zero cold starts. Static hosting only (Vercel Hobby).
- No live attack surface; nothing to keep running or patch.
- Schema fidelity is guaranteed by construction (responses come from the real
  app via `TestClient`), not by keeping fixtures in sync by hand.
- The dashboard code stays backend-agnostic: one `STATIC` flag switches modes,
  so the same components serve both topologies.

**Negative / trade-offs**
- CRUD and pipeline runs are not durable - they live in the visitor's
  `localStorage` and reset when storage clears or a new snapshot ships. This is
  called out in the UI (demo badge, "Demo mode" toast) and in `/docs`.
- Data freshness is bounded by the weekly cron. Acceptable because the pipeline
  cadence is weekly anyway.
- Client-side filtering loads the full feed into the browser. Fine at this data
  volume; would need real pagination or an edge function at large scale.
- Adding a competitor in static mode does not schedule real collection (there is
  no scheduler running); it only overlays the UI list.

## Alternatives considered

- **Hosted FastAPI on a free VM** - the original topology. Rejected as the
  default for the demo: cold starts, uptime risk, and hosting cost/effort that
  the read-mostly weekly data does not justify. Kept as documented live mode.
- **Next.js API routes / serverless functions reading DuckDB** - would keep one
  codebase but reintroduces per-request compute, bundling DuckDB into
  serverless, and cold starts, for no benefit over static JSON at this scale.
- **`output: 'export'` (pure static export)** - would also work, but it disables
  Next rewrites (needed for the dev/live proxy) and other niceties. Using
  `generateStaticParams` + `dynamicParams = false` gets the same fully-static
  output while keeping one config that also serves live mode.
