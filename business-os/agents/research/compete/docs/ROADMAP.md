# ROADMAP — From "complete" to portfolio-grade

The original build (Phases 0-7) is done and verified: collection, LLM extraction,
DuckDB + dbt warehouse, FastAPI, the Next.js dashboard with the bone/ink/lime
brand, weekly reports, and alerts. This document is the honest gap analysis of
what stands between "the system works" and "this project wins me interviews",
organized as build phases 8-13 in the same style as the original brief: each
phase has a goal, the reasoning, detailed tasks, and verification gates. Build a
phase, verify it, pause, then continue.

**Priority order matters.** Phases 8-10 close credibility holes (a recruiter can
find these in five minutes). Phases 11-12 add depth. Phase 13 makes people
actually see it. If time is short, do 8, 9, and 13 and skip the middle.

---

## Current state audit (what a reviewer sees today)

Strengths already in place, worth protecting:

- End-to-end pipeline that genuinely runs (collect → extract → dbt → report).
- 41 passing tests, ruff/black clean, 50 passing dbt assertions.
- A designed frontend with a real brand, landing page, and docs page, not a
  default shadcn template.
- Real documentation: ARCHITECTURE, DATA_MODEL, AGENTS, RUNBOOK, DEPLOYMENT,
  three ADRs, CONTRIBUTING.

Holes, in the order a stranger would hit them:

1. **No live demo URL.** The static-export deploy (Vercel, $0) is built but
   uncommitted and unverified. Until a link exists, the project is "trust me".
2. **No CI quality gate.** The only workflow is the weekly data cron. Nothing
   runs pytest, ruff, mypy, dbt, or the web build on push. The Actions tab is
   the first place a technical reviewer looks.
3. **Zero frontend tests.** The web app (the explicit differentiator) has no
   unit tests and no E2E tests. `mypy` is installed but not enforced anywhere.
4. **Data goes stale.** The demo warehouse is seeded with June 2026 dates. A
   dashboard whose newest signal is weeks old reads as abandoned. The weekly
   cron exists but the deployed dashboard is not yet wired to benefit from it.
5. **The dashboard is shallow one level down.** You can see a table of changes
   but cannot click a signal to see the evidence (the before/after page diff
   that the whole pipeline exists to produce). No search, no compare view.
6. **SEO/sharing is broken for a portfolio artifact.** `metadataBase` is the
   placeholder `https://compete.local`, there is no OG image, no sitemap, no
   robots.txt. A LinkedIn share of the demo URL renders with no card.
7. **The story is untold.** `blog/watching-the-competition.mdx` exists but is
   wired to nothing. No demo GIF/video, no case-study framing, repo has no
   topics/social image/release tag.
8. **No Dockerfile.** Intentional (DuckDB is file-based), but "clone and run"
   credibility on someone else's machine still benefits from one; reviewers
   pattern-match on its absence.

---

## Phase 8 — Ship it: live demo + repo hygiene

**Goal:** a public URL at the top of the README that anyone can click, backed by
the static-export deploy, plus a repo that presents well on GitHub.

**Why first:** everything else compounds from a working link. The static-export
work is already 90% done in the working tree; finishing and verifying it is the
highest ROI move available.

### Tasks

1. **Finish and verify the static export path (in-flight work).**
   - Regenerate `web/public/api-static/` from the demo warehouse with
     `uv run python scripts/export_static_data.py` and diff-check a few files
     against live FastAPI responses.
   - Add `generateStaticParams` to `web/src/app/(dashboard)/competitors/[id]`
     so the whole app is fully static output (the DEPLOYMENT note already flags
     this). Verify `next build` emits it as `● (SSG)` not `ƒ (Dynamic)`.
   - Exercise static mode locally: `NEXT_PUBLIC_STATIC_DATA=1 npm run build &&
     npm run start`, click through every page, confirm filtering/sorting/
     pagination of signals and changes work client-side, confirm the
     `static-store.ts` localStorage overlay handles competitor CRUD and the
     "Run pipeline" button gracefully (optimistic UI plus an honest "demo mode"
     toast, not a silent no-op).
   - Confirm report PDFs download from `/api-static`.
2. **Deploy to Vercel** (root `web`, framework preset from `vercel.json`, no env
   needed). Attach a clean domain: `compete.yerradouani.me` or the default
   `*.vercel.app`. Verify light/dark, mobile, and the landing page live.
3. **Fix production metadata before sharing the URL:** set `metadataBase` to
   the real domain (env-driven, `NEXT_PUBLIC_SITE_URL`), correct canonical
   URLs. (Full OG/social treatment is Phase 12; the base URL must not ship
   wrong.)
4. **Commit the in-flight work** as a coherent series: static export script,
   api.ts static mode, static-store, vercel.json, workflow changes, DEPLOYMENT
   rewrite. Write an ADR: `adr/0004-static-snapshot-deploy.md` (why bake JSON
   instead of hosting FastAPI; tradeoffs: no write-through CRUD, weekly
   freshness; why TestClient guarantees schema fidelity).
5. **README top matter:** first screen must contain the live demo link, a
   one-line pitch, and (after Phase 13) the demo GIF. Move "Status: complete"
   into a shields.io badge row (build, tests, license, live demo).
6. **GitHub repo hygiene:** repo description + website field, ~10 topics
   (`competitive-intelligence`, `llm`, `duckdb`, `dbt`, `fastapi`, `nextjs`,
   `data-engineering`, ...), a social preview image (reuse the OG image from
   Phase 12 or a landing screenshot for now), tag `v1.0.0` with release notes
   summarizing Phases 0-7, pin the repo on the profile.

### Verification gates

- Live URL loads every route with real-looking data; zero console errors.
- `npm run build` shows all dashboard routes as static; no serverless functions
  in the Vercel deploy summary.
- Weekly Action run (manually dispatched) regenerates JSON, commits, and
  triggers a redeploy end-to-end once.
- Fresh-clone test: `git clone` on a clean machine → README quickstart works
  verbatim.

---

## Phase 9 — Engineering credibility: CI, tests, types

**Goal:** a green Actions tab that proves the quality gates on every push, and
test coverage for the two currently untested surfaces (the web app and the
type layer).

**Why:** this is the difference between "side project" and "engineer who ships
production software". It is also cheap: the local gates already pass; CI mostly
codifies them.

### Tasks

1. **`.github/workflows/ci.yml`** on push + PR, three parallel jobs:
   - **python**: `uv sync --all-extras` → `ruff check` → `black --check` →
     `mypy pipeline api` → `pytest --cov=pipeline --cov=api
     --cov-report=xml --cov-fail-under=80`. Cache uv.
   - **dbt**: seed the demo warehouse (`scripts/seed_demo.py`) → `dbt build`
     (all 50 assertions run against real data, not just compile).
   - **web**: `npm ci` → `next lint` → `tsc --noEmit` → `vitest run` →
     `next build` (static mode env) → Playwright E2E (below).
   - Badges for all three in the README.
2. **Make mypy actually pass.** It is in dev deps but not enforced. Run it,
   burn down the errors, add `[tool.mypy]` config (start non-strict, enable
   `strict = true` per-module for `pipeline.extract` and `api` where Pydantic
   makes it cheap). This usually surfaces one or two real bugs; fix them.
3. **Web unit tests (Vitest + React Testing Library).** Target the logic that
   can actually break, not snapshot noise:
   - `lib/api.ts` static mode: URL mapping, client-side filter/sort/paginate
     of the signals and changes feeds (this is new, hand-rolled logic with
     real edge cases: empty filters, out-of-range offsets, date ordering).
   - `lib/static-store.ts`: overlay CRUD semantics, localStorage round-trip.
   - `signal-meta.tsx`: every signal type maps to a badge (guards against
     adding an enum value and forgetting the UI).
   - One or two component tests: DataTable sorting, empty/error states render.
4. **E2E smoke (Playwright, already a project dependency via Python; use
   `@playwright/test` for the web).** Five journeys against a static-mode
   production build: landing renders + CTA navigates; /dashboard shows stat
   cards with non-zero numbers; changes table filters by competitor and
   signal type; competitor detail renders all three charts; theme toggle
   flips `html.dark` and persists. Run headless in the web CI job.
5. **Python test gaps** (keep it honest, no busywork):
   - An integration test for `run-all` with the mock provider against a temp
     DB (collect-cap small), asserting signals land and marts build.
   - `export_static_data.py` test: run it against the seeded warehouse into a
     tmp dir, assert file inventory and that JSON parses back into the
     Pydantic schemas.
   - Coverage report will show the real gaps; fill anything under ~60% that
     contains branching logic (alerts gating, change-detection thresholds).
6. **Supply-chain basics:** `dependabot.yml` (pip + npm + github-actions,
   weekly, grouped), `pip-audit` and `npm audit --audit-level=high` as
   non-blocking CI steps. Pin GitHub Action versions by SHA in workflows.
7. **Pre-commit config** (`.pre-commit-config.yaml`: ruff, black, prettier) so
   the gates run locally too; document in CONTRIBUTING.

### Verification gates

- CI green on a real PR (open one to prove the badge isn't decorative).
- Coverage ≥80% python, reported in CI logs; vitest + Playwright suites pass
  headless.
- `mypy` clean. Dependabot opens its first PRs and CI validates them.

---

## Phase 10 — Keep it alive: real data, freshness, observability

**Goal:** the deployed dashboard shows genuinely fresh, real competitor data
every week, visibly states when it was last updated, and the pipeline reports
its own health.

**Why:** a competitive-intelligence product with stale data refutes its own
pitch. "Last updated 3 days ago" on a live dashboard is the single most
convincing signal that this system actually runs.

### Tasks

1. **Switch the weekly cron to real extraction.** Add `GOOGLE_API_KEY` to repo
   secrets; run `compete run-all` with Gemini Flash against the real
   competitor list (keep the collect cap conservative; free tier is ample at
   weekly cadence). The mock path stays for CI and offline dev.
2. **Decide the seed-vs-real data story.** Recommended: the deployed dashboard
   serves *real* collected data (that is the whole point), with the curated
   seed kept only for local demo (`scripts/demo.py`) and CI. If real
   extraction quality is not presentable yet, interim fix: make seed dates
   relative to today at export time so the demo never looks dead. Do not ship
   dates frozen in June 2026.
3. **Pipeline run history as data.** New `raw.pipeline_runs` table (run id,
   started/finished, per-stage counts: pages fetched, signals extracted,
   changes detected, failures, token spend from `raw.llm_calls`). `run-all`
   writes it. Export it in the static JSON.
4. **Surface health in the product:**
   - "Data updated <relative time>" chip in the dashboard AppShell header,
     from the export timestamp.
   - A small **Pipeline status** section (Settings or a `/status` page): last
     run, stage table, token cost, failure count. This is an impressive,
     unusual feature that showcases the engineering.
5. **dbt source freshness:** add `loaded_at_field` + `freshness` config on the
   raw sources; run `dbt source freshness` in the weekly workflow; fail loudly.
6. **Failure alerting for the pipeline itself:** the weekly workflow posts to
   the existing Slack webhook path on failure (reuse `pipeline/report/alerts.py`
   or a simple curl step). A dead cron that nobody notices is how demos rot.
7. **Extraction quality pass with the real provider:** run a real Gemini
   extraction over a week of collected pages, read 20-30 signals, tune the
   prompt/schema where the output is weak (pricing extraction is known-sparse;
   either improve the heuristic + prompt or drop the sparse chart from the
   default view rather than showing a nearly-empty chart).

### Verification gates

- Two consecutive scheduled runs complete green and the live site's "updated"
  chip advances without manual intervention.
- `dbt source freshness` passes; forcing a stale source fails the workflow.
- Pipeline status page shows real run history including token spend.
- A deliberately broken run (bad key) produces a Slack alert.

---

## Phase 11 — Product depth: the features that make people say "oh, nice"

**Goal:** close the drill-down gap. Today the dashboard summarizes; after this
phase it lets you investigate, which is what an analyst actually does.

**Why:** reviewers who click past the landing page need a second "wow" within
two clicks. Evidence-level drill-down is also the honest payoff of the
snapshot-diff architecture you already built.

### Tasks

1. **Signal detail view (the flagship feature).** Route
   `/signals/[id]` (or a slide-over panel from the changes table):
   - Full extracted fields, significance, competitor, source link.
   - **Before/after evidence**: render the stored prior and current snapshot
     content with a computed inline diff (added/removed spans highlighted).
     The raw snapshots are already in the warehouse; add a
     `GET /signals/{id}/evidence` endpoint returning both texts plus the diff,
     and bake it into the static export. Use a small client-side diff lib
     (`diff` npm package) or precompute server-side.
   - Related signals block (see task 3).
   This single feature justifies the entire pipeline visually.
2. **Global search + command palette (cmd+k).** One component, two payoffs:
   fuzzy search over competitors, signals (title/summary), and pages
   (navigation actions included). Static mode searches the baked JSON
   client-side; keep the index small (id, title, type, competitor, date).
   `cmdk` is the standard library and matches the existing Radix stack.
3. **Related signals via the existing embeddings.** You already compute
   embeddings and have `fct_signal_duplicates` with cosine similarity. Extend
   to a top-5 "related signals" list per signal (threshold lower than the
   0.95 dedup bar, e.g. 0.75), exported per signal. Zero new infrastructure,
   demonstrates the embedding layer is real.
4. **Competitor compare view.** `/compare?a=anthropic&b=openai`: side-by-side
   stat columns, overlaid pricing lines, overlaid hiring bars, signal cadence.
   Reuses every chart component that exists; mostly composition work with one
   new page and a competitor picker.
5. **Alert history in the UI.** Alerts currently fire into Slack/email and
   vanish. Log dispatches to a `raw.alerts` table and show them in Settings →
   Alerts ("what would have fired" in dry-run mode too). Makes a configured
   but invisible feature visible.
6. **Stretch (only if the above is done and verified): "Ask the analyst".**
   A chat box over the warehouse: either LLM-generated SQL against the marts
   (read-only, statically infeasible — live mode only) or, static-friendly,
   LLM answers grounded in the exported signals JSON via the client calling
   Gemini with the user's own key. Scope it ruthlessly or skip it; a bad
   chatbot hurts more than no chatbot.

### Verification gates

- From /changes, any row → detail → visible before/after diff in ≤2 clicks.
- cmd+k finds a competitor and a signal by fuzzy substring; keyboard-only
  navigation works.
- Compare view renders correctly with any competitor pair including sparse
  ones (empty-state handling).
- All new surfaces work in static mode on the live deploy, light/dark, mobile.
- Suites from Phase 9 extended to cover the new logic (diff computation,
  search index, compare data merging); CI green.

---

## Phase 12 — Frontend excellence: a11y, perf, SEO/sharing

**Goal:** the measurable polish layer: audited accessibility, verified
performance, and link previews that look intentional everywhere the URL gets
pasted.

**Why:** the frontend is the stated differentiator, so it should survive expert
scrutiny, not just look good in screenshots. And a portfolio project lives or
dies on how its link unfurls on LinkedIn.

### Tasks

1. **Accessibility audit and fixes.**
   - Run axe (browser extension or `@axe-core/playwright` wired into the E2E
     suite) over landing, dashboard, changes, competitor, settings.
   - Known risk areas: lime-on-bone contrast for text-sized elements (the
     brand lime is bright; verify ≥4.5:1 for text, adjust the darkened
     `--primary` usage where needed), focus visibility on the ink panels,
     aria-labels on icon-only buttons (theme toggle, mobile nav), chart
     alt/summary text (Tremor charts are div soup to a screen reader; add
     `aria-label` summaries), keyboard reachability of the changes table
     filters and dialogs, `prefers-reduced-motion` already handled (verify).
   - Gate: axe critical/serious = 0, wired into CI E2E.
2. **Performance verification.** Lighthouse CI (or manual, documented) against
   the production deploy: targets ≥90 performance, ≥95 a11y/best-practices/SEO
   on landing and /dashboard. The Phase 6 perf work (dynamic Tremor imports,
   content-visibility) should get you close; likely remaining offenders are
   `heroBackground.jpg`/`footerBackground.jpg` (convert to AVIF/WebP via
   `next/image`), font loading, and GSAP main-thread time on mid-tier mobile.
3. **SEO + sharing.**
   - Designed OG image (1200×630) in the bone/ink/lime brand; per-page titles
     and descriptions; `metadataBase` from env (done in Phase 8, verify).
   - `app/sitemap.ts`, `app/robots.ts`, canonical URLs.
   - Validate with the actual unfurlers (LinkedIn Post Inspector, Twitter/X
     card validator, iMessage/Slack paste).
   - Reuse the OG image as the GitHub social preview.
4. **State-audit sweep.** Systematically visit every page in four states:
   loading (throttled), empty (fresh DB export), error (rename a JSON file),
   and populated. Fix what's ugly; the memory notes claim these states exist,
   this pass proves it. Custom 404 and error.tsx pages in-brand.
5. **Analytics:** Vercel Analytics (zero config on Hobby) or Plausible. You
   want to know when someone visits the demo the night after an interview.
6. **Micro-polish backlog** (timebox this, it is a rabbit hole): table row
   hover → detail affordance, chart tooltips styled to brand, skeleton
   loaders match final layout (no CLS), scroll restoration on back-nav,
   favicon set complete (`icon`/`apple-icon`, dark-mode variant).

### Verification gates

- Lighthouse scores recorded in the README or docs (screenshots or CI badge).
- axe: zero critical/serious across audited pages, enforced in CI.
- Link pastes unfurl with the branded card on LinkedIn, X, and Slack.
- Keyboard-only walkthrough: landing → dashboard → filter changes → open a
  signal → toggle theme, without touching the mouse.

---

## Phase 13 — Storytelling: make people actually see it

**Goal:** the project markets itself: a compelling README, a published
write-up, a demo video, and integration into yerradouani.me.

**Why:** nobody reads code first. They read the README, watch 30 seconds of
video, maybe skim the blog post, and only then clone. This phase is cheap
relative to everything above and multiplies its value.

### Tasks

1. **Demo GIF/video.** 30-45s screen capture: landing scroll → dashboard →
   filter changes → signal diff (Phase 11's payoff shot) → compare view →
   theme flip → report PDF. Convert the short loop to an optimized GIF or
   `<video>` for the README top; upload the full cut wherever you host video.
   Script it so it can be re-recorded after UI changes.
2. **README as a case study.** Restructure: hero (pitch, live link, badges,
   GIF) → "why this exists" (2 paragraphs, the analyst problem) → architecture
   diagram → "interesting decisions" (link the ADRs: DuckDB over Postgres,
   snapshot diffing, static-snapshot deploy, deterministic mock path) →
   quickstart → the rest. Recruiters skim; front-load the impressive parts.
3. **Architecture diagram as an image.** The ASCII diagram is charming in
   /docs; the README wants a designed one (Excalidraw or Figma, exported dark
   + light). Show the full flow: scheduler → collectors → LLM → warehouse →
   dbt → static export → dashboard, with the weekly-commit loop drawn in.
4. **Finish and publish the blog post.** `blog/watching-the-competition.mdx`
   exists; finish it as a build-log essay: the problem, the architecture
   decisions and their tradeoffs, what the LLM layer actually gets wrong, the
   static-deploy trick, honest limitations. Publish on yerradouani.me, link it
   from the README and the site footer. (A `/blog` route inside compete is an
   option but publishing on the personal site with a link back is better for
   the portfolio.)
5. **Portfolio integration:** project card on yerradouani.me (live demo +
   GitHub + write-up links), pinned repo, and a LinkedIn post with the video
   when everything above is live.
6. **Honesty pass on claims.** Re-read README/docs/landing after phases 10-12:
   every number ("5 competitors", "424 snapshots", coverage %) should match
   reality; the /docs Limitations section should mention static-mode
   constraints (demo CRUD is local-only, weekly freshness). Overclaiming is
   the one unrecoverable mistake in a portfolio piece.

### Verification gates

- A stranger test: send the repo link to one person, no context; they should
  find the live demo in <10 seconds and explain back what the project does.
- README renders correctly on GitHub (GIF plays, badges resolve, diagram
  legible in dark mode).
- Blog post live and linked bidirectionally.
- LinkedIn unfurl of both repo and demo URL looks intentional.

---

## Explicitly out of scope (documented so it's a decision, not an omission)

- **Auth/multi-tenancy** — this is a single-analyst demo product; adding auth
  adds friction to the demo and no portfolio signal. Mention in /docs.
- **Postgres/Supabase migration** — ADR-0001 already argues DuckDB; revisiting
  it adds cost, not signal.
- **Docker Compose for the full stack** — still intentionally omitted (the
  static deploy removed the last server), but add a single optional
  `Dockerfile` for the pipeline in Phase 9 *only if* CI needs it; otherwise
  keep the DEPLOYMENT.md note.
- **Mobile app, browser extension, email digests UI** — fun, zero marginal
  interview value relative to cost.

## Suggested order and effort

| Phase | Theme | Effort (focused days) | Cut line |
|-------|-------|----------------------|----------|
| 8 | Live demo + repo hygiene | 1-2 | Never cut |
| 9 | CI + tests + types | 2-3 | Never cut |
| 10 | Fresh data + observability | 2-3 | Trim to tasks 1, 2, 4a |
| 11 | Product depth | 3-5 | Trim to tasks 1, 2 |
| 12 | A11y/perf/SEO | 2-3 | Trim to tasks 1, 3 |
| 13 | Storytelling | 1-2 | Never cut |

Total: roughly two to three focused weeks for everything, or about one week for
the never-cut spine (8, 9, 13 plus the freshness fix from 10.2).
