# R&D Execution Prompt — Marketing/Chopify (`business-os/agents/marketing`) System Review & Chief-of-Staff Integration Readiness

> Copy this entire document into the executing agent's session as its task instruction.
> It is self-contained: role, sources, evidence baseline, method, phases, and acceptance checks.

---

## 0. Role, Mission, and Hard Constraints

**Role.** You are a Senior AI Systems Architect and R&D Engineer specializing in agentic business systems, integration layers, and marketing-domain automation.

**Mission.** Perform a complete, evidence-based review of the current active `business-os` marketing agent project — Chopify scope — to (a) understand the existing system, and (b) assess how a future **Chief of Staff (CoS) agent** can integrate with or modify it through the integration layer. Produce a review report with gap/risk/dependency registers and ranked modification points.

**Primary evaluation criterion.** The integration layer's ability to support future CoS **command, delegation, orchestration, monitoring, and reporting**. Evaluate every finding against this criterion.

**Scope fence.** Marketing agent scope, currently the Chopify project (`business-os/agents/marketing/chopify`). The business platform (Shopify/custom website) is out of scope — analyze it only as the upstream event source named in the Recommended Architecture, never as a review target. Postiz (the second named component of the marketing repo) is inspected only to establish its presence/absence, not reviewed in depth if absent.

**Terminology note.** The tasking says "marketing-chopigy"; the evidence calls the project **Chopify** and the repo root `agents/marketing`. Treat "chopigy" as a typo for Chopify and state this normalization in the report. Do not invent a separate "Chopigy" project.

**Hard constraints (non-negotiable).**
1. **Do not modify any project file.** Read-only review. No writes, refactors, config changes, or `git` state changes.
2. **Do not fabricate.** No invented repositories, capabilities, interfaces, endpoints, or architecture details. Every claim must cite a concrete file path (plus line/symbol where possible) or be tagged `ASSUMPTION` / `OPEN`.
3. **Preserve the target architecture vocabulary** in all analysis and recommendations: (1) Chief of Staff agent; (2) independent specialized agents; (3) internal orchestrators; (4) individual UI per agent; (5) integration layer = APIs / MCP / webhooks / adapters; (6) shared intelligence; (7) controlled data access. Do not rename, merge, or drop elements.
4. **Separate evidence classes.** Tag every finding `FACT` (observed in repo/sources), `ASSUMPTION` (stated inference needing validation), or `OPEN` (insufficient context).
5. **Flag ambiguities explicitly.** Never resolve ambiguity by invention.
6. **Respect the repo's own docs as spec.** Chopify self-documents (`docs/AGENT-API.md`, `docs/CLI.md`, `llms.txt`, `docs/superpowers/{plans,specs}`); verify documented behavior against code and tests before relying on it.

**Method (applies to all phases).**
- **ReAct:** Reason (state the expectation and why) → Act (inspect files/sources) → Observe (record evidence) → Refine (update the hypothesis, repeat).
- **Iterative self-correction:** keep a hypothesis list; actively attempt refutation; promote a finding to `FACT` only with ≥1 citation, preferably two independent ones (e.g., doc + code + test). "No evidence of X" must list the search terms used and locations covered.
- **Chain-of-thought stays internal.** Expose only conclusions, decisions, and concise justifications with citations.

**Working environment facts (verified by the requester's pre-survey; re-verify on arrival).**
- Repo root: `/enterprise_os/business-os/agents/marketing`; the sole project in the tree is `chopify/` (plus `README.md`, `.gitkeep` at the agent root). Sources **Agents info.md** and **Recommended architecture.md** are available as chat-project uploads — read them directly (no need to request them).
- The sandbox may not have the repo checked out. If the working directory lacks the repo, stop, report the blocker, and request the checkout/location. Do not simulate the review from this prompt.

---

## 1. Source-Comprehension Plan (Agents Info & Recommended Architecture)

**Sources (available; read fully).**
- `Agents info.md` — per-agent capability sheets for nine agents. The **Marketing agent** sheet is normative for this review: create social posts (captions/carousels in brand voice), edit short-form videos (cut long videos into captioned reels), schedule and publish (best-time posting on every platform), analyze metrics (weekly report). The **Chief of Staff** sheet defines the CoS contract: send CEO brief, delegate to agents, track open loops, build scorecard.
- `Recommended architecture.md` — "Local-First Federated Multi-Agent Business OS": parent workspace of independent repos; marketing = **Postiz + Chopify**; five layers; CoS coordinates via the integration layer while agents stay mutually unaware; shared intelligence = PostgreSQL + Qdrant (+ Redis events); Shopify as source of truth; the worked example "new Shopify order → CoS → Marketing: trigger eligible retention campaign".

**Procedure.**
1. Read both sources twice: first for intent, second for normative statements about the marketing agent and CoS↔agent interaction.
2. Extract, for each of the seven architecture elements, the marketing-domain interpretation, quoting the sources verbatim where explicit (e.g., "agents don't need to know each other", "delegates via APIs, MCP, or lightweight adapters").
3. Decompose the Marketing agent sheet into its four capability sheets and map each to expected implementing components: video editing → Chopify; scheduling/publishing → Postiz; posts and metrics → Postiz and/or dashboard; brand voice → brand configuration. Record which capabilities have **no implementing component in evidence** — these are findings, not gaps to be filled by assumption.
4. Reconcile the two sources where they differ (e.g., Agents Info lists a "Reviews" agent while Recommended Architecture names `reputation/OpenGMB`; Agents Info has no separate "research" split though the repo tree does). Record mismatches as `OPEN`, without editing either source's intent.
5. Read Chopify's self-description next (`README.md`, `docs/product.json`, `llms.txt`) and reconcile it with the marketing-agent sheet: state in one paragraph what Chopify is in the target architecture (expected: the "edit short-form videos" capability) and what the marketing agent still lacks.

**Output of this phase:** `source-comprehension.md` — element table with verbatim quotes, the four-capability decomposition with component mapping, source-mismatch list (`OPEN`), and the Chopify-vs-marketing-agent reconciliation paragraph.

---

## 2. Marketing-Context Architecture Mapping

Map each architecture element onto the marketing/Chopify domain and the current codebase. For each row: element → marketing-domain counterpart → candidate code anchors (from Appendix A) → status (`EXISTS` / `PARTIAL` / `ABSENT`) → citation.

| # | Architecture element | Marketing-domain counterpart to investigate |
|---|---|---|
| 1 | Chief of Staff agent | External command/orchestration consumer. Expect **no CoS implementation** (pre-survey found no `chief`/`of-staff`/`orchestrat*` files in the tree); assess the *receptacle*: `docs/AGENT-API.md`, `docs/CLI.md`, `llms.txt`. |
| 2 | Independent specialized agents | The marketing agent (Postiz + Chopify per source) — Chopify present in tree; **Postiz absence must be verified and stated**. Chopify's own "agentness" is to be determined: scripted pipeline vs. agentic runtime. |
| 3 | Internal orchestrators | Chopify's internal pipeline stages and their sequencer: root modules `chopify.py`, `projects.py`, `ingest.py`, `download_and_transcribe.py`, `sections.py`, `evidence.py`, `score_clips.py`, `tighten.py`, `captions.py`, `visual.py`, `render_clips.py`, `branding.py`; batch execution via `examples/batch.json`. Determine whether stage sequencing is a hardcoded pipeline, a state machine, or an agent loop. |
| 4 | Individual UI | `assets/studio/` (app.js, index.html, style.css — the Studio), `dashboard.py`, `tools/build_site.py` (docs/preview site), `.github/workflows/pages.yml` (GitHub Pages). Determine how UI and pipeline communicate (files? local server? none?). |
| 5 | Integration layer (APIs, MCP, webhooks, adapters) | Documented agent surface: `docs/AGENT-API.md` + `docs/CLI.md` + `llms.txt`; data contracts: `examples/batch.json`, `examples/brand.json`, `docs/product.json`; ingestion adapters: `download_and_transcribe.py` (which sources? YouTube? uploads?); transcription backend. **Expect ABSENT at tree level: HTTP server framework, MCP, webhooks, auth** — verify in content, cite negative searches. |
| 6 | Shared intelligence | Local brand context (`examples/brand.json`), product knowledge (`docs/product.json`, `docs/USER-DEMAND-RESEARCH.md`), discoverability docs. The Recommended Architecture's shared layer (PostgreSQL + Qdrant + Redis events) has **no counterpart in the tree** — verify and record. |
| 7 | Controlled data access | Expect **ABSENT at tree level**: no auth, API keys, permission model, or audit trail visible. Local-first single-user posture. Verify in content (any token handling in `download_and_transcribe.py`, install scripts, CI). |

**Procedure.** Verify every candidate anchor by opening the files (the tree is small — a full read of every Python module, doc, and test is feasible and required). Every `ABSENT` verdict cites the greps/negative searches that established it; every `PARTIAL` verdict states what exists and what is missing.

**Output of this phase:** `marketing-architecture-mapping.md` — completed mapping table with citations, plus a one-paragraph narrative per element explaining how Chopify realizes (or fails to realize) it today, and an explicit statement of which Marketing-agent capabilities are unimplemented.

---

## 3. Current-Project Inspection Plan

The repo is small enough to inspect exhaustively; "sampled" is not acceptable here.

**3.1 Self-description first.** Read in order: `README.md`, `docs/product.json`, `llms.txt`, `docs/AGENT-API.md`, `docs/CLI.md`, `docs/WORKFLOWS.md`, `docs/DISCOVERABILITY.md`, `docs/TROUBLESHOOTING.md`, `docs/USER-DEMAND-RESEARCH.md`, then all six `docs/superpowers/plans/*.md` and three `docs/superpowers/specs/*.md` (dated 2026-10/11 — they define intended architecture: Studio, adaptive clip discovery, caption studio, creator evidence, long-source ingest). Treat docs as `FACT` about intent; verify against code and tests. Note `llms.txt` and `AGENT-API.md` as the project's own machine-facing contract — decisive for CoS readiness.

**3.2 Pipeline & internal orchestration.** For each root Python module, record: responsibility, inputs/outputs (files? JSON?), external services called (YouTube? Whisper/transcription? LLM APIs?), and how stages chain (`chopify.py` as CLI entry? `projects.py` state?). Establish: end-to-end flow (ingest → transcribe → sections → evidence → score → tighten → captions → render → branding → dashboard/site), where intermediate artifacts live, what "batch" runs (`examples/batch.json`), and how a run is resumed/failed. Map this to "internal orchestrator" — most likely a scripted pipeline; say so with evidence, not apology.

**3.3 Interfaces & contracts.**
- CLI: enumerate every command and flag from `chopify.py` + `docs/CLI.md`; cross-check with tests (`test_chopify.py`). This is today's only command surface.
- Agent API: read `docs/AGENT-API.md` fully — determine its nature (conventions for driving the CLI? JSON contracts? an actual HTTP interface?). Cross-check against `test_studio.py`, `test_dashboard.py`, `test_site.py`, and `assets/studio/app.js` (what the Studio calls).
- Data contracts: `examples/batch.json`, `examples/brand.json`, `docs/product.json` — schema, validation (is there any?), and who consumes them.
- Long-running work: render/transcribe durations; is there job status, progress, resumption (`test_long_projects.py`, `test_chunked_transcription.py` are leads)?

**3.4 Boundaries, runtime, and data access.**
- Runtime model: local process(es)? Any server (`dashboard.py` — file server? API?)? Ports? Persistence (file layout under projects; `projects.py`)?
- External calls and credentials: `download_and_transcribe.py` (platform adapters, API keys/tokens handling), transcription and LLM providers (from `requirements.txt`/`semantic.py`/`visual.py`/`score_clips.py`), `install.sh`/`install.ps1` (what they fetch), CI (`ci.yml` secrets usage). Any secret handling → tag as the only "controlled data access" material in evidence.
- Multi-tenancy/brand isolation: is `brand.json` the only brand-context mechanism? What happens with concurrent projects/users?

**3.5 Tests as executable spec.** All 14 `tests/*.py` + `pytest.ini`: what behaviors are pinned (block scan, chunked transcription, evidence, sections, studio, visual, render integration, site build). Record the test-to-module map; tests are the strongest evidence of intended contracts.

**3.6 UI inventory.** Studio (`assets/studio/*`): what a user does there (review clips? captions? select moments?); `dashboard.py` output; docs site (`tools/build_site.py`, `index.html`, `sitemap.xml`, Pages workflow). These are the human interaction patterns a CoS would replace or drive programmatically.

**Output of this phase:** `project-inspection.md` — per-area findings with citations; the verified CLI/agent-API inventory; the pipeline stage map; the runtime/data-flow diagram in text; the credential/secret surface; explicitly listed absences with search terms.

---

## 4. Integration-Layer Assessment Plan (CoS Lenses)

Assess each channel against the five CoS capabilities. For every (channel × capability) cell assign a readiness rating with evidence:

- **0 – Absent** (no surface found; cite the negative searches)
- **1 – Partial** (surface exists but not machine-consumable as-is: undocumented, no contract, no status)
- **2 – Ready** (documented contract, non-interactive invocation, deterministic outputs, test coverage)
- **3 – Extensible** (ready *and* designed for machine consumers: versioned contract, job model, event notifications, pluggable adapters)

| Channel \ Lens | Command (issue/authorize actions) | Delegation (hand off task, track status) | Orchestration (multi-step, idempotent, cancellable) | Monitoring (events, state changes, health) | Reporting (results, metrics, audit) |
|---|---|---|---|---|---|
| Documented agent API / CLI (`docs/AGENT-API.md`, `docs/CLI.md`, `llms.txt`, root modules) | | | | | |
| HTTP service surface (expect ABSENT — verify: any server, ports, endpoints) | | | | | |
| Webhooks / events (expect ABSENT — verify) | | | | | |
| MCP (expect ABSENT — verify) | | | | | |

**Concrete questions each cell must answer** (inspect code, not file names):
- **Command:** Can a CoS start a job non-interactively (single CLI invocation with inputs; batch.json)? What inputs must it fabricate (video URL, brand file, output paths)? Is there input validation with actionable errors? Anything requiring human judgment mid-run (Studio review steps)? What stops a bad command (validation, dry-run)?
- **Delegation:** Is there a job/task abstraction with status a caller can poll (project directory state? progress files? exit codes only?)? Can work be submitted and picked up later (queue? none?)? Is there cancellation?
- **Orchestration:** Can multi-step workflows be composed (transcribe once → score variants → render per-platform)? Are stages idempotent/resumable (`test_long_projects.py` evidence)? What happens on partial failure (crash mid-render)? Any transactional guarantees over artifacts?
- **Monitoring:** Does anything emit observable state (progress output, log files, webhook, change notifications)? How would a CoS know a render finished or failed — polling what?
- **Reporting:** What does the system produce for consumption (clip scores from `score_clips.py`, dashboard, site build, captions)? Is there machine-readable output (JSON) for the CoS scorecard ("analyze metrics / weekly report" per Agents Info — note which of that lives in Chopify vs. is unimplemented)?

**Output of this phase:** `integration-assessment.md` — the filled 4×5 readiness matrix with citations per cell, plus the top-5 findings that most affect CoS feasibility.

---

## 5. Gap / Risk / Dependency / Modification-Point Analysis Plan

**5.1 Gap register.** For each CoS lens, list what is missing for a CoS to command this agent through the integration layer — derived strictly from the Phase 4 matrix. Candidate gaps to confirm or refute (hypotheses from the pre-survey; do not assert as fact): no network-reachable command surface (CLI-only, local-first); no job/status API (delegation); no MCP server; no webhook/event emission (monitoring); no auth/permission model (controlled data access — who may command Chopify?); no machine-readable run summary (reporting); Postiz absent so scheduling/publishing commands have no target; no shared-intelligence connection (brand context is a local file).

**5.2 Risk register.** For each gap and each reused surface: description, affected CoS lens, likelihood × impact, mitigation. Marketing-specific risks to evaluate: credential leakage via new machine surfaces (download/transcription keys); destructive local file operations if CoS commands paths blindly; silent partial failures (renders without verification) misleading the CoS scorecard; brand-voice/config drift (`brand.json` unvalidated); concurrency collisions on shared project directories; long-running render jobs blocking command throughput; dependency drift (transcription/LLM providers) breaking the pipeline silently.

**5.3 Dependency map.** Runtime: Python + `requirements.txt`/`requirements-dev.txt` (enumerate actual deps in inspection — transcription engine, media tooling e.g. ffmpeg, LLM clients), external platforms (video sources in `download_and_transcribe.py`), optional Studio browser. Build/deploy: `install.sh`/`install.ps1`, pytest, GitHub Actions (`ci.yml`, `pages.yml`). Per the Recommended Architecture: Docker Compose isolation, Redis events, PostgreSQL+Qdrant shared knowledge — none visible in Chopify; record which dependencies a CoS integration would introduce vs. assume.

**5.4 Modification points.** Rank candidate change sites by minimal-touch principle, each with: file/area, what would change, which CoS lens it serves, blast radius, additive vs invasive. Candidates to evaluate (verify before including): formalize `docs/AGENT-API.md` into a versioned, testable JSON contract over the existing CLI (additive, highest leverage); add a structured run-summary output (JSON per stage) for monitoring/reporting; wrap `chopify.py`/`projects.py` stages as an MCP tool server (per Recommended Architecture's MCP integration intent); add resumable job state (`projects.py`) for delegation; introduce a minimal local service (FastAPI per Recommended Architecture's Python convention) only if CLI contract proves insufficient; connect brand context to the shared intelligence layer (defer — depends on infrastructure that doesn't exist yet). Explicitly separate **integration-only** (no repo change; CoS drives the existing CLI) from **modification** (repo change) options, and mark what is blocked by missing shared infrastructure (Redis/Qdrant/Postgres, Postiz).

**Output of this phase:** `gap-risk-dependency-analysis.md` — three registers + ranked modification points, each row cited or explicitly tagged `ASSUMPTION`/`OPEN`.

---

## 6. Step-by-Step Execution Methodology

Execute phases in order; each phase gates the next. Record everything in a worklog.

1. **Gate 0 — Environment & inputs.** Confirm repo location/branch (root `/enterprise_os/business-os/agents/marketing`); locate `Agents info.md` and `Recommended architecture.md` in the chat-project uploads; read agent-level `README.md` beside the project. If either source is missing, record `OPEN` and proceed with Phases 2–5 using Appendix A, marking source-dependent conclusions provisional.
2. **Phase 1 — Sources** (Section 1). Produce `source-comprehension.md`.
3. **Phase 2 — Mapping** (Section 2). Verify every Appendix A anchor by opening the file. Produce `marketing-architecture-mapping.md`.
4. **Phase 3 — Inspection** (Section 3). Exhaustive read: self-description → pipeline → interfaces → boundaries/runtime → tests → UI. Produce `project-inspection.md`.
5. **Phase 4 — Integration assessment** (Section 4). Fill the matrix; for each cell cite code or the negative search that proves absence. Produce `integration-assessment.md`.
6. **Phase 5 — Analysis** (Section 5). Registers + modification points. Produce `gap-risk-dependency-analysis.md`.
7. **Phase 6 — Self-correction pass.** Re-audit the report: (a) every `FACT` has ≥1 citation; (b) every `ABSENT` lists negative-search terms; (c) every register row is cited or tagged; (d) run three adversarial refutation attempts against your strongest claims (e.g., hidden HTTP server in `dashboard.py`, undocumented CLI flags, event emission in `build_site.py`/CI); (e) verify the scope fence — no business-platform analysis beyond the event-source reference.
8. **Phase 7 — Recommendations** (Section 8) and final report assembly.
9. **Throughout:** update the evidence ledger (`FACT`/`ASSUMPTION`/`OPEN`) and worklog after every ReAct cycle; never batch-write findings from memory at the end.

**Deliverables to produce:** `review-report.md` (executive summary, per-phase findings, matrix, registers, recommendations), the six per-phase artifacts, and `worklog.md` (cycle log: reason → action → evidence → refinement). Save all under a single `cos-marketing-review/` directory. Do not modify anything inside the repo.

---

## 7. Measurable Acceptance Checks

The report passes only if every check is demonstrably true:

- [ ] **A1 — Sources reviewed & mapped:** Agents Info and Recommended Architecture tables exist with verbatim quotes; marketing-domain interpretation written for all 7 elements; the four Marketing-agent capabilities decomposed with implementing-component mapping (including which are unimplemented).
- [ ] **A2 — Inspection exhaustive & cited:** every Python module, doc, and test file in the tree is either cited or explicitly marked out-of-scope with a reason; ≥20 distinct file paths cited; every claimed absence lists search terms used.
- [ ] **A3 — Integration layer assessed:** the 4×5 matrix is fully filled, every cell has a readiness rating + citation or cited negative search, and the five CoS capabilities (command, delegation, orchestration, monitoring, reporting) are each covered for all four channels (agent API/CLI, HTTP, webhooks/events, MCP).
- [ ] **A4 — Registers complete:** gap, risk (likelihood/impact/mitigation), and dependency registers each have ≥5 rows; modification points ≥5, ranked, each labeled additive vs invasive and flagged where blocked by missing shared infrastructure.
- [ ] **A5 — Postiz & CoS status stated:** the report explicitly states Postiz's presence/absence and the CoS's implementation status, each with citation or negative search — no silent omission.
- [ ] **A6 — Methodology followed:** `worklog.md` shows ReAct cycles per phase and the Phase 6 self-correction pass results, including the three adversarial refutation attempts.
- [ ] **A7 — Ambiguities flagged:** a dedicated section lists every `OPEN` item (including the chopigy/chopify naming normalization and source mismatches like Reviews-vs-reputation) with the question and what is needed to resolve it; `ASSUMPTION` items are listed with their validation condition.
- [ ] **A8 — No unsupported claims:** spot-check 10 random `FACT` claims — each resolves to a real file/line; zero fabricated endpoints, capabilities, or components.
- [ ] **A9 — Scope fence holds:** no business-platform analysis beyond the Recommended Architecture's event-source reference; no project files modified (`git status` clean at the end, modulo untracked review-output directory outside the repo).

---

## 8. Goal-Oriented Next-Step Recommendations

Close the report with recommendations a decision-maker can act on, in this structure:

1. **Integration posture decision.** Recommend one primary posture, justified by evidence: (a) *consume-only* — CoS drives Chopify's existing CLI/batch interface locally with zero repo change (state its real limits: no status, no events, no auth); (b) *contract-first extension* — formalize the documented agent API into a versioned JSON contract with structured run summaries and, where needed, a small MCP/FastAPI wrapper per the Recommended Architecture's conventions; (c) *defer* — declare Chopify not yet integration-ready until job state and machine-readable outputs exist. State the evidence that drove the choice and what would change the decision.
2. **Sequenced roadmap.** 3–4 phases, each with: goal, concrete steps anchored to Section 5.4 modification points, the CoS lens unlocked, and a verification method (which tests pin the contract — e.g., new contract tests beside `test_chopify.py`). Order must respect dependencies: machine-readable run output before status/delegation; status before event emission; auth only once a network surface exists.
3. **Risk burn-down.** Map top risks to roadmap phases (each phase retires ≥1 risk) and name the gates the CoS must pass before commanding money-adjacent or public-facing actions (publishing lives in Postiz — flag that any publish command is blocked on Postiz's presence/absence).
4. **Open decisions for the requester.** Enumerate `OPEN` items that block design: Postiz availability and repo location; whether the marketing agent's metrics-analysis capability belongs in Chopify, Postiz, or the CoS scorecard; whether Chopify should join the shared intelligence layer (Redis events, Qdrant brand knowledge) now or later; the chopigy/chopify naming normalization; source mismatches (Reviews vs reputation/OpenGMB). For each, state the specific input needed from the architecture owners.

Recommendations must stay inside the marketing/Chopify scope and must not redesign the CoS itself — the deliverable is how the marketing agent receives and supports CoS command/orchestration, not the CoS's internals.

---

## Appendix A — Baseline Evidence (from requester's pre-survey)

**Source documents (available as chat-project uploads; read in full).**
- `Agents info.md`: nine agent sheets. Marketing agent = "Creates posts, edits videos, tracks metrics": create social posts (captions/carousels in brand voice), edit short-form videos (cut long videos into captioned reels), schedule and publish (best-time posting on every platform), analyze metrics (weekly report). Chief of Staff = "runs your other agents, briefs you daily": CEO brief (revenue, leads, cash, top 3), delegate to agents (routes work to marketing, sales, finance), track open loops, build scorecard (weekly KPIs from Strapi, CRM, and ads).
- `Recommended architecture.md`: "Local-First Federated Multi-Agent Business OS"; repo tree with `agents/marketing/` = "Postiz + Chopify"; five layers (CoS command/delegation/orchestration/monitoring/reporting; independent agents with internal orchestrators and individual UIs; integration layer APIs/MCP/webhooks/adapters; shared intelligence PostgreSQL+Qdrant, Redis events; business platform Shopify — out of scope); "agents don't need to know each other"; CoS "delegates via APIs, MCP, or lightweight adapters"; worked example: new Shopify order → CoS → Marketing triggers eligible retention campaign; Python for CoS/orchestration/adapters; Docker Compose isolation.

**Project tree (verified `FACT`s from the uploaded dump of `/enterprise_os/business-os/agents/marketing`; project dir `chopify/`).**

- **Root Python modules (flat layout):** `chopify.py`, `branding.py`, `captions.py`, `dashboard.py`, `download_and_transcribe.py`, `evidence.py`, `ingest.py`, `projects.py`, `render_clips.py`, `score_clips.py`, `sections.py`, `semantic.py`, `tighten.py`, `visual.py`; `tools/{build_site.py, make_social_preview.py}`. Config: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `install.sh`, `install.ps1`, `llms.txt`.
- **Tests (14):** `tests/{test_block_scan, test_caption_studio, test_chopify, test_chunked_transcription, test_dashboard, test_evidence, test_ingest, test_long_projects, test_project_render, test_render_integration, test_sections, test_site, test_studio, test_visual}.py`.
- **Docs:** `docs/AGENT-API.md`, `CLI.md`, `DISCOVERABILITY.md`, `TROUBLESHOOTING.md`, `USER-DEMAND-RESEARCH.md`, `WORKFLOWS.md`, `product.json`, docs-site assets (`index.html`, `site.css`, `robots.txt`, `sitemap.xml`); `docs/superpowers/plans/` (6 dated plans: 2026-10-23 chopify-studio, 2026-10-31 adaptive-clip-discovery-phase-1-selection-core, 2026-10-31 chopify-caption-studio, 2026-11-01 creator-evidence-audio-and-action, 2026-11-01 creator-evidence-visual, 2026-11-02 long-source-ingest-and-sections) and `docs/superpowers/specs/` (3 design specs: chopify-studio-design, chopify-adaptive-clip-discovery-design, chopify-caption-studio-design).
- **UI assets:** `assets/studio/{app.js, index.html, style.css}`; brand assets (`banner.svg`, `demo.gif`, `pipeline.svg`, `social-preview.png`, `studio-preview.png`).
- **Examples/data contracts:** `examples/{batch.json, brand.json}`.
- **CI:** `.github/workflows/{ci.yml, pages.yml}`; `CONTRIBUTING.md`, `CHANGELOG.md`, `LICENSE`, `README.md`, `.gitignore`.

**Verified absences at tree level (search terms: `mcp`, `webhook`, `server`, `api` filenames, `auth`, `orchestrat*`, `chief`, `of-staff`, `postiz`, `docker`, `redis`, `qdrant`, `postgres`).** No MCP files; no webhook files; no server/framework files (no FastAPI/Flask/Express markers in filenames); no auth or permission files; no database/config for shared intelligence; no Dockerfile or compose file; no Postiz component; no `chief`/`of-staff`/`orchestrat*` files. The repo is a local-first Python CLI + static Studio UI. Absence at tree level is not absence at code level — Phase 3/4 must re-verify inside file contents (especially `dashboard.py` for any HTTP behavior and `AGENT-API.md` for a documented remote contract).

**Environment note from pre-survey.** The requester's sandbox did not contain the checked-out repo (only this tree dump plus the two source documents). Conclusions in this prompt are tree-level evidence; code-level verification is mandatory in Phases 2–4.
