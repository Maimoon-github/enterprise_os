# R&D Execution Prompt — Marketing/Postiz (`business-os/agents/marketing`) System Review & Chief-of-Staff Integration Readiness

> Copy this entire document into the executing agent's session as its task instruction.
> It is self-contained: role, sources, evidence baseline, method, phases, and acceptance checks.

---

## 0. Role, Mission, and Hard Constraints

**Role.** You are a Senior AI Systems Architect and R&D Engineer specializing in agentic business systems, integration layers, and marketing-domain automation.

**Mission.** Perform a complete, evidence-based review of the current active `business-os` marketing agent project — Postiz scope — to (a) understand the existing system, and (b) assess how a future **Chief of Staff (CoS) agent** can integrate with or modify it through the integration layer. Produce a review report with gap/risk/dependency registers and ranked modification points.

**Primary evaluation criterion.** The integration layer's ability to support future CoS **command, delegation, orchestration, monitoring, and reporting**. Evaluate every finding against this criterion.

**Scope fence.** Marketing agent scope, currently the Postiz project (`business-os/agents/marketing/postiz-app`). The business platform (Shopify/custom website) is out of scope — reference it only as the upstream event source named in the Recommended Architecture. Chopify (the marketing repo's other component) is referenced only for scope arbitration where Postiz features overlap it; do not re-review Chopify.

**Hard constraints (non-negotiable).**
1. **Do not modify any project file.** Read-only review. No writes, refactors, config changes, or `git` state changes.
2. **Do not fabricate.** No invented repositories, capabilities, interfaces, endpoints, or architecture details. Every claim must cite a concrete file path (plus line/symbol where possible) or be tagged `ASSUMPTION` / `OPEN`.
3. **Preserve the target architecture vocabulary** in all analysis and recommendations: (1) Chief of Staff agent; (2) independent specialized agents; (3) internal orchestrators; (4) individual UI per agent; (5) integration layer = APIs / MCP / webhooks / adapters; (6) shared intelligence; (7) controlled data access. Do not rename, merge, or drop elements.
4. **Separate evidence classes.** Tag every finding `FACT` (observed in repo/sources), `ASSUMPTION` (stated inference needing validation), or `OPEN` (insufficient context).
5. **Flag ambiguities explicitly.** Never resolve ambiguity by invention.
6. **Postiz is agent-native — do not rubber-stamp it.** The pre-survey shows Postiz ships an MCP relay, an agent tool registry, Temporal workflows, and an SDK. That raises the bar, not the conclusion: "ready" verdicts require code-level proof of auth scope, idempotency, tenancy, and approval semantics for machine principals.

**Method (applies to all phases).**
- **ReAct:** Reason (state the expectation and why) → Act (inspect files/sources) → Observe (record evidence) → Refine (update the hypothesis, repeat).
- **Iterative self-correction:** keep a hypothesis list; actively attempt refutation; promote a finding to `FACT` only with ≥1 citation, preferably two independent ones (e.g., controller + service + DTO). "No evidence of X" must list the search terms used and locations covered.
- **Chain-of-thought stays internal.** Expose only conclusions, decisions, and concise justifications with citations.

**Working environment facts (verified by the requester's pre-survey; re-verify on arrival).**
- Repo root: `/enterprise_os/business-os/agents/marketing`; the project is `postiz-app/` (plus `README.md`, `.gitkeep` at the agent root). Sources **Agents info.md** and **Recommended architecture.md** are available as chat-project uploads — read them directly.
- The sandbox may not have the repo checked out. If the working directory lacks the repo, stop, report the blocker, and request the checkout/location. Do not simulate the review from this prompt.

---

## 1. Source-Comprehension Plan (Agents Info & Recommended Architecture)

**Sources (available; read fully).**
- `Agents info.md` — per-agent capability sheets. The **Marketing agent** sheet is normative for this review: create social posts (captions/carousels in brand voice), edit short-form videos, schedule and publish (best-time posting on every platform), analyze metrics (weekly report). The **Chief of Staff** sheet defines the CoS contract: send CEO brief, delegate to agents, track open loops, build scorecard (weekly KPIs from Strapi, CRM, and ads).
- `Recommended architecture.md` — "Local-First Federated Multi-Agent Business OS": marketing = **Postiz + Chopify**; five layers; CoS coordinates via the integration layer while agents stay mutually unaware; worked example "new Shopify order → CoS → Marketing: trigger eligible retention campaign".

**Procedure.**
1. Read both sources twice; second pass extracts normative statements about publishing/scheduling/metrics and CoS↔agent interaction.
2. Decompose the Marketing agent sheet into its four capabilities and map each to expected components: **scheduling/publishing and metrics → Postiz; video editing → Chopify; posts → Postiz (with generation features to verify)**. Record any capability whose ownership is ambiguous between the two components — that is a finding.
3. Extract the CoS's five verbs and, for each, what Postiz would need to expose (expected anchors exist in the tree — see Appendix A: agent tools, MCP, Temporal workflows, webhooks, analytics).
4. Note the Recommended Architecture's event-flow model (CoS delegates via APIs/MCP/adapters; Redis events; agents unaware of each other) as the yardstick Phase 4 measures against.

**Output of this phase:** `source-comprehension.md` — element table with verbatim quotes, the four-capability decomposition with Postiz/Chopify ownership, and the CoS-verb → expected-surface table.

---

## 2. Marketing-Context Architecture Mapping

Map each architecture element onto the marketing/Postiz domain. For each row: element → marketing-domain counterpart → candidate code anchors (from Appendix A) → status (`EXISTS` / `PARTIAL` / `ABSENT`) → citation.

| # | Architecture element | Marketing-domain counterpart to investigate |
|---|---|---|
| 1 | Chief of Staff agent | External command/orchestration consumer. Expect **no CoS implementation** (pre-survey: no `chief`/`of-staff` files) — but Postiz already hosts *other* AI agents: `.github/agents/*` (claude, codex, cursor, grok, hermes-agent, muse, nanoclaw, openclaw, paperclip, perplexity-computer, mcp-server), `chatgpt-app-submission.json`, `apps/backend/src/api/routes/copilot.controller.ts`. Assess what a CoS would ride on and whether external-agent onboarding is first-class. |
| 2 | Independent specialized agents | Postiz itself (publishing brain of the marketing agent). **Scope-arbitration finding:** Postiz contains its own video/clipping features (`apps/orchestrator/src/workflows/clipping.workflow.ts`, `generate.video.workflow.ts`, libs `videos/{images-slides,seedance}`, `3rdparties/{heygen,reelfarm}`, `deepgram/`) that may overlap Chopify's role — map which component owns what. |
| 3 | Internal orchestrators | Temporal app: `apps/orchestrator/src/{activities,signals,workflows}` — activities for autopost/clipping/email/integrations/media/post/video; workflows incl. **12 versioned post workflows (`post.workflow.v1.0.1`→`v1.1.2`)**, autopost, digest.email, generate.video, missing.post, process.media, refresh.token, send.email, streak; `dynamicconfig/{development-cass.yaml,development-sql.yaml}`; `apps/commands/src/tasks/{agent.run.ts,refresh.tokens.ts}`; libs `temporal/`, `redis/`. |
| 4 | Individual UI | `apps/frontend` (Next.js app-router): pages for `agents/[id]`, analytics, billing, media, plugs, settings, third-party, `integrations/connect/social/[provider]`, `webhooks.tsx`, auth flows (login/activate/forgot); `libraries/react-shared-libraries`. |
| 5 | Integration layer (APIs, MCP, webhooks, adapters) | REST: `apps/backend/src/api/routes/*` (~33 controllers) + `public-api/v1/public.integrations.controller.ts`; **MCP**: `libraries/nestjs-libraries/src/chat/{mcp.relay.service.ts, start.mcp.ts, oauth-middleware.ts, oauth-types.ts}`; **agent tools**: `chat/tools/*` (26 tools: integration.schedule.post, integration.connect/list/trigger/validation, posts.list, delete.post, generate.image/video, media.list/status, upload.from.url, upload.widget.*, video.function/status, clipping.*, tool.list registry); **webhooks**: `webhooks.controller.ts`, `database/prisma/webhooks/{repository,service}`, `webhooks.dto.ts`, `webhook.url.validator.ts`, UI page; **adapters**: `integrations/social/` platform providers, `3rdparties/{heygen,hubspot,reelfarm}`, auth login providers; **SDK**: `apps/sdk` (published package); **browser extension**: `apps/extension` (provider.registry, skool.provider). |
| 6 | Shared intelligence | `database/prisma/*` (18 repos incl. organizations, agencies, posts, integrations, third-party), `redis/`, `mastra.service.ts`/`mastra.store.ts` (agent memory), `agent/agent.graph.service.ts` + `agent.graph.insert.service.ts` + `agent.topics.ts`/`agent.categories.ts` (graph knowledge), `openai/`, `dtos/*` contracts. Assess what brand/business context lives here vs. the Recommended Architecture's PostgreSQL+Qdrant layer (not evidenced — verify and record). |
| 7 | Controlled data access | `services/auth/permissions/{permissions.ability.ts, permissions.guard.ts, permissions.service.ts}`, `super.admin.guard.ts`, OAuth agent middleware/types, `signature.controller.ts`, `throttler/`, subscription gating (`subscription.exception.ts`, billing/stripe controllers), `webhook.url.validator.ts`, `.env.example` secret surface. |

**Procedure.** Verify every candidate anchor by opening files (prioritized inspection, Section 3). Every `ABSENT` verdict cites negative searches; every `PARTIAL` verdict states what exists and what is missing.

**Output of this phase:** `marketing-architecture-mapping.md` — completed mapping table with citations, per-element narrative, and the explicit Postiz/Chopify ownership statement for the four Marketing-agent capabilities.

---

## 3. Current-Project Inspection Plan

The repo is large; inspect prioritized-but-deep. Priority order: agent/chat surfaces → orchestrator → API/auth → webhooks/adapters → UI → ops. Everything else is skimmed with explicit out-of-scope notes.

**3.1 Self-description first.** `README.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `apps/sdk/README.md`, `.env.example`, `docker-compose.yaml` (+`.dev.yaml`), `package.json`/`pnpm-workspace.yaml` (workspace map, scripts), `version.txt`, `.claude/settings.json`, `.coderabbit.yaml`. Establish: what Postiz claims to be (open-source social publishing tool vs. the business-OS marketing agent), its deployment modes (Docker, Railway, AWS), and its multi-tenancy posture (organizations/agencies).

**3.2 Agent & MCP surfaces (highest priority).** Read fully: `chat/agent.tool.interface.ts`, `chat/tools/tool.list.ts` and every tool file (record each tool's name, inputs, auth context, side effects — publishing? deleting?), `mastra.service.ts`/`mastra.store.ts`, `mcp.relay.service.ts`, `start.mcp.ts`, `oauth-middleware.ts`, `oauth-types.ts`, `load.tools.service.ts`, `chat.module.ts`, `auth.context.ts`, libs `agent/*` (graph services, topics, categories). Questions: How is an external agent authenticated (OAuth client? user-delegated token? org-scoped?)? Which tools are destructive (delete.post) and is there human approval? Is tool scope per-org/per-user? How does the MCP relay differ from `start.mcp.ts`? What does `copilot.controller.ts` expose?

**3.3 Orchestrator (Temporal).** Read `apps/orchestrator/src/*` fully: every workflow (note why 12 post-workflow versions exist — versioning strategy is an orchestration design fact), activities and their failure/retry semantics, signals (async cancel/complete?), `health.controller.ts`, `dynamicconfig/*.yaml`, libs `temporal/`. Map: how a post travels (submission → scheduling → publishing → retries → analytics?) and where a CoS could inject commands or observe state. Also `apps/commands/src/tasks/agent.run.ts` — what "agent.run" does.

**3.4 API, auth, and tenancy.** Enumerate the ~33 controllers (path, methods, auth guard, idempotency, org scoping): priority `posts`, `integrations`, `oauth`, `oauth-app`, `webhooks`, `monitor`, `public-api/v1`, `third-party`, `signature`, `no.auth.integrations` (why does an unauthenticated integrations controller exist?), `copilot`, `admin`. Auth: `services/auth/*` — middleware chain, casl ability definitions (the actual permission vocabulary), login providers, `public.auth.middleware.ts`, widget auth middlewares. Tenancy: `database/prisma/{organizations,agencies,users}` repos — who sees whose posts/integrations; cross-org isolation guarantees.

**3.5 Webhooks & adapters.** Inbound: `webhooks.controller.ts` (who calls it — platform events? payments?), `webhook.url.validator.ts` (SSRF protections — security finding material), `webhooks.dto.ts`. Outbound: `database/prisma/webhooks/{repository,service}` (does Postiz emit events to subscribers — the CoS monitoring channel?), `notifications` repos/controllers. Adapters: `integrations/social/` (enumerate platforms supported, refresh-token handling), `3rdparties/*` (what for), `apps/extension` provider registry, `newsletter/providers`, `services/{attribution,payment}/providers`, `short-linking/providers`.

**3.6 UI inventory.** `apps/frontend/src/app/(app)/*`: which human workflows exist (planner, analytics, billing, agents detail page — what is it for?, settings, webhooks config, admin stats/errors); how the UI calls the API (`apps/frontend/src/app/(app)/api` proxies); the MCP client icons in UI (`mcp.client.icons.tsx`) and `webhooks.tsx` settings page — evidence that agent/webhook configuration is user-facing.

**3.7 Tests & quality gates.** `jest.config.ts`/`jest.preset.js` (what's covered), `sonar-project.properties`, `.coderabbit.yaml`, CodeQL workflow, Jenkins buildfiles — record what CI enforces; note test coverage of the agent/MCP surfaces (likely thin — a finding).

**Output of this phase:** `project-inspection.md` — per-area findings with citations; the verified agent-tool/MCP/API inventory; the Temporal workflow map; the authn/authz/tenancy matrix; the webhook in/out picture; explicitly listed absences with search terms.

---

## 4. Integration-Layer Assessment Plan (CoS Lenses)

Assess each channel against the five CoS capabilities. For every (channel × capability) cell assign a readiness rating with evidence:

- **0 – Absent** (no surface found; cite negative searches)
- **1 – Partial** (surface exists but not machine-consumable as-is: no contract, interactive-only auth, no status)
- **2 – Ready** (documented contract, non-interactive authn, scoped access, test coverage)
- **3 – Extensible** (ready *and* designed for external machine consumers: versioned contracts, registry patterns, per-org tool scoping, webhooks out, SDK)

| Channel \ Lens | Command (issue/authorize actions) | Delegation (hand off task, track status) | Orchestration (multi-step, idempotent, cancellable) | Monitoring (events, state changes, health) | Reporting (metrics, audit) |
|---|---|---|---|---|---|
| REST + SDK (`api/routes/*`, `public-api/v1`, `apps/sdk`) | | | | | |
| MCP (`chat/mcp.relay.service.ts`, `start.mcp.ts`, tools registry) | | | | | |
| Webhooks / events (inbound `webhooks.controller`, outbound `prisma/webhooks` service, notifications) | | | | | |
| Temporal / orchestrator surface (`apps/orchestrator`, `apps/commands`, `monitor.controller`) | | | | | |

**Concrete questions each cell must answer** (inspect code, not file names):
- **Command:** Can an external principal authenticate and act — schedule a post (`integration.schedule.post` tool / posts controller), connect an integration, generate media? What identity model (OAuth for agents: `oauth-middleware.ts`/`oauth-types.ts`; API keys? `api.key.dto.ts`)? What permission entries apply (casl abilities)? Is there human approval before publishing, or can a CoS publish directly? What does `public-api/v1` expose?
- **Delegation:** Is there a job/task abstraction with status (Temporal workflow IDs? `monitor.controller.ts`? `media.status.tool.ts`, `video.status.tool.ts`, `posts.list.tool.ts`)? Cancellation signals? What does `agent.run.ts` task do?
- **Orchestration:** Can multi-step flows be composed externally (upload → generate → schedule per-platform)? What guarantees exist (Temporal retries/versioned workflows vs. fire-and-forget controllers)? Idempotency keys for repeated CoS commands? Failure semantics on partial publish (some platforms fail)?
- **Monitoring:** Does Postiz emit observable state (outbound webhooks service, notifications, `health.controller.ts`, Sentry)? Is there an event catalog a CoS can subscribe to (webhook event types)? What does `monitor.controller.ts` monitor?
- **Reporting:** What can a CoS read — analytics controller (per-platform metrics for the CEO brief/scorecard), admin stats, digest.email workflow outputs? Are agent-initiated actions attributable in audit trails (who/what triggered each post)?

**Output of this phase:** `integration-assessment.md` — the filled 4×5 readiness matrix with citations per cell, plus the top-5 findings that most affect CoS feasibility.

---

## 5. Gap / Risk / Dependency / Modification-Point Analysis Plan

**5.1 Gap register.** For each CoS lens, what is missing for a CoS to command Postiz through the integration layer — derived strictly from the Phase 4 matrix. Candidate gaps to confirm or refute (hypotheses from the pre-survey; do not assert as fact): CoS onboarding path (which of the existing external-agent mechanisms — MCP/OAuth/SDK/ChatGPT app — fits a CoS, and what's missing); documented machine-facing contract (OpenAPI completeness for `public-api/v1` and routes); outbound event catalog (typed webhook payloads, signing); cross-component workflow (Chopify renders → Postiz uploads — evidence of any existing bridge or none); approval semantics for publishing; audit trail linking posts to originating agents.

**5.2 Risk register.** For each gap and reused surface: description, affected lens, likelihood × impact, mitigation. Publishing-specific risks: public-facing posts made without human review (brand damage — the CoS "command" verb becomes dangerous); platform ToS/rate limits on automation (`throttler/`, refresh token races); credential/SSRF exposure via webhooks (`webhook.url.validator.ts`) and agent OAuth; cross-org data leakage (agencies model); duplicate posting under retries (idempotency); destructive tools (delete.post) reachable by machines; Postiz↔Chopify overlap causing double-publishing or divergent pipelines; versioned-workflow drift (v1.1.2 vs v1.0.x semantics).

**5.3 Dependency map.** Runtime: Temporal (`dynamicconfig` cass/sql implies selectable persistence), Redis, Prisma DB (which engine — from compose files), object storage/upload providers, email providers, social platform APIs (OAuth tokens, refresh workflows), HeyGen/ReelFarm/DeepGram/OpenAI third parties, Stripe billing. Build/deploy: pnpm workspaces, Jenkins, GitHub Actions (build, build-containers, deploy-aws, codeql), Railway, Docker, devcontainer, i18n (inlang). Mark which dependencies a CoS integration would add load to (Temporal task queue, webhook fan-out, MCP relay).

**5.4 Modification points.** Rank candidate change sites by minimal-touch principle: extend `chat/tools` registry + `tool.list.ts` with CoS-scoped tools (additive; likely highest leverage given existing agent infra); register the CoS as an OAuth/MCP client using existing `oauth-middleware`/`oauth-types`; add outbound signed webhooks for post lifecycle events beside `prisma/webhooks` service; complete machine-facing API contract (OpenAPI) for command/status endpoints; idempotency keys on posting endpoints; approval gate for publish-class tools. Explicitly separate **integration-only** (CoS consumes existing MCP/tools/SDK with zero repo change) from **modification** (repo change), and mark what is blocked by the missing shared infrastructure (Redis event bus ownership, Qdrant brand knowledge, Chopify bridge).

**Output of this phase:** `gap-risk-dependency-analysis.md` — three registers + ranked modification points, each row cited or explicitly tagged `ASSUMPTION`/`OPEN`.

---

## 6. Step-by-Step Execution Methodology

Execute phases in order; each phase gates the next. Record everything in a worklog.

1. **Gate 0 — Environment & inputs.** Confirm repo location/branch (root `/enterprise_os/business-os/agents/marketing`); locate `Agents info.md` and `Recommended architecture.md` in the chat-project uploads; read agent-level `README.md` beside the project. If either source is missing, record `OPEN` and proceed with Phases 2–5 using Appendix A, marking source-dependent conclusions provisional.
2. **Phase 1 — Sources** (Section 1). Produce `source-comprehension.md`.
3. **Phase 2 — Mapping** (Section 2). Verify every Appendix A anchor by opening the file. Produce `marketing-architecture-mapping.md`.
4. **Phase 3 — Inspection** (Section 3). Prioritized-deep: self-description → agent/MCP surfaces → orchestrator → API/auth/tenancy → webhooks/adapters → UI → tests/CI. Produce `project-inspection.md`.
5. **Phase 4 — Integration assessment** (Section 4). Fill the matrix; for each cell cite code or the negative search that proves absence. Produce `integration-assessment.md`.
6. **Phase 5 — Analysis** (Section 5). Registers + modification points, including the Postiz/Chopify ownership arbitration. Produce `gap-risk-dependency-analysis.md`.
7. **Phase 6 — Self-correction pass.** Re-audit: (a) every `FACT` has ≥1 citation; (b) every `ABSENT` lists negative-search terms; (c) every register row is cited or tagged; (d) run three adversarial refutation attempts against your strongest claims (e.g., unauthenticated paths in `no.auth.integrations.controller.ts`, hidden approval flows for publishing, event emission outside the webhooks service); (e) verify the scope fence — no business-platform analysis, no Chopify re-review beyond arbitration.
8. **Phase 7 — Recommendations** (Section 8) and final report assembly.
9. **Throughout:** update the evidence ledger (`FACT`/`ASSUMPTION`/`OPEN`) and worklog after every ReAct cycle; never batch-write findings from memory at the end.

**Deliverables to produce:** `review-report.md` (executive summary, per-phase findings, matrix, registers, recommendations), the six per-phase artifacts, and `worklog.md` (cycle log: reason → action → evidence → refinement). Save all under a single `cos-postiz-review/` directory. Do not modify anything inside the repo.

---

## 7. Measurable Acceptance Checks

The report passes only if every check is demonstrably true:

- [ ] **A1 — Sources reviewed & mapped:** Agents Info and Recommended Architecture tables exist with verbatim quotes; marketing-domain interpretation written for all 7 elements; the four Marketing-agent capabilities decomposed with Postiz/Chopify ownership stated.
- [ ] **A2 — Inspection cited & prioritized:** ≥25 distinct file paths cited; all agent/MCP/orchestrator surfaces read fully; every claimed absence lists search terms used.
- [ ] **A3 — Integration layer assessed:** the 4×5 matrix is fully filled, every cell has a readiness rating + citation or cited negative search, and the five CoS capabilities (command, delegation, orchestration, monitoring, reporting) are each covered for all four channels (APIs/SDK, MCP, webhooks/events, Temporal/orchestrator).
- [ ] **A4 — Registers complete:** gap, risk (likelihood/impact/mitigation), and dependency registers each have ≥5 rows; modification points ≥5, ranked, each labeled integration-only vs. additive vs. invasive, flagged where blocked by missing shared infrastructure.
- [ ] **A5 — Agent-native claims verified, not assumed:** the report's verdicts on MCP tool scope, agent OAuth, approval-before-publish, idempotency, and cross-org isolation each cite code, not file names.
- [ ] **A6 — Postiz/Chopify arbitration stated:** an explicit statement of which component owns video clipping/generation and where the overlap or bridge gaps are, with citations from both trees.
- [ ] **A7 — Methodology followed:** `worklog.md` shows ReAct cycles per phase and the Phase 6 self-correction pass results, including the three adversarial refutation attempts.
- [ ] **A8 — Ambiguities flagged:** a dedicated section lists every `OPEN` item with the question and what is needed to resolve it; `ASSUMPTION` items are listed with their validation condition.
- [ ] **A9 — No unsupported claims / scope fence holds:** spot-check 10 random `FACT` claims — each resolves to a real file/line; zero fabricated endpoints or capabilities; no business-platform analysis; no project files modified (`git status` clean at the end, modulo untracked review-output directory outside the repo).

---

## 8. Goal-Oriented Next-Step Recommendations

Close the report with recommendations a decision-maker can act on, in this structure:

1. **Integration posture decision.** Recommend one primary posture, justified by evidence: (a) *consume-only* — CoS registers as an external agent via Postiz's existing MCP/OAuth/agent-tool infrastructure (state exactly which capabilities that unlocks today and which lack contracts); (b) *contract-first extension* — formalize a CoS tool set in the `chat/tools` registry + signed outbound lifecycle webhooks + OpenAPI for command/status routes; (c) *deep integration* — Temporal-level co-orchestration between CoS and Postiz workflows. State the evidence that drove the choice and what would change the decision.
2. **Sequenced roadmap.** 3–4 phases, each with: goal, concrete steps anchored to Section 5.4 modification points, the CoS lens unlocked, and a verification method (contract tests; Temporal workflow tests; webhook signature tests). Order must respect dependencies: authenticated read-only access before write tools; status/monitoring before autonomous scheduling; approval gate before any direct publishing.
3. **Risk burn-down.** Map top risks to roadmap phases (each phase retires ≥1 risk) and name the gates the CoS must pass before public-facing autonomy: permission-catalog scoping, idempotent command execution, human-in-the-loop for publishing, audit provenance for every agent-initiated post, cross-org isolation proof.
4. **Open decisions for the requester.** Enumerate `OPEN` items that block design: which external-agent mechanism the CoS should use (MCP vs OAuth app vs SDK); who owns video clipping — Postiz's internal workflows or Chopify (arbitration affects both prompts); whether publishing requires human approval by default; ownership of the outbound event catalog vs. the Recommended Architecture's Redis bus; CoS org/brand scoping under the agencies model. For each, state the specific input needed from the architecture owners.

Recommendations must stay inside the marketing/Postiz scope and must not redesign the CoS itself — the deliverable is how Postiz receives and supports CoS command/orchestration, not the CoS's internals.

---

## Appendix A — Baseline Evidence (from requester's pre-survey)

**Source documents (available as chat-project uploads; read in full).**
- `Agents info.md`: nine agent sheets. Marketing agent = "Creates posts, edits videos, tracks metrics": create social posts (captions/carousels in brand voice), edit short-form videos (cut long videos into captioned reels), schedule and publish (best-time posting on every platform), analyze metrics (weekly report). Chief of Staff = "runs your other agents, briefs you daily": CEO brief (revenue, leads, cash, top 3), delegate to agents (routes work to marketing, sales, finance), track open loops, build scorecard (weekly KPIs from Strapi, CRM, and ads).
- `Recommended architecture.md`: "Local-First Federated Multi-Agent Business OS"; `agents/marketing/` = "Postiz + Chopify"; five layers (CoS command/delegation/orchestration/monitoring/reporting; independent agents with internal orchestrators and individual UIs; integration layer APIs/MCP/webhooks/adapters; shared intelligence PostgreSQL+Qdrant, Redis events; business platform Shopify — out of scope); "agents don't need to know each other"; CoS "delegates via APIs, MCP, or lightweight adapters"; worked example: new Shopify order → CoS → Marketing triggers eligible retention campaign; Python for CoS/orchestration/adapters; Docker Compose isolation.

**Project tree (verified `FACT`s from the uploaded dump of `/enterprise_os/business-os/agents/marketing`; project dir `postiz-app/`).**

- **Monorepo (pnpm):** `apps/{backend, commands, extension, frontend, orchestrator, sdk}` + `libraries/{helpers, nestjs-libraries, react-shared-libraries}`; `dynamicconfig/{development-cass.yaml, development-sql.yaml}`; `Jenkins/{Build, BuildPR}.Jenkinsfile`; `docker-compose.yaml` + `docker-compose.dev.yaml` + `Dockerfile.dev`; `railway.toml`; deploy workflows (`deploy-aws.yml`, `build-containers.yml`); `chatgpt-app-submission.json`; `CLAUDE.md`, `.claude/settings.json`, `.github/copilot-instructions.md`, `.coderabbit.yaml`, `sonar-project.properties`, `jest.config.ts`, `i18n.json`/`i18n.lock`, `version.txt`.
- **External-agent program (`FACT` — unusual and decisive for CoS):** `.github/agents/` ships icons/entries for claude, claude-code, claude-cowork, codex, cursor, grok (bot/build), hermes-agent, muse, nanoclaw, openclaw, paperclip, perplexity-computer, and **mcp-server**.
- **Backend (`apps/backend/src/`):** `api/routes/` — ~33 controllers: admin, analytics, announcements, approved-apps, auth, autopost, billing, clipping, clipping.widget, **copilot**, enterprise, integrations, media, media.widget, **monitor**, `no.auth.integrations`, notifications, oauth, oauth-app, payment, posts, public, root, sets, settings, **signature**, stripe, **third-party**, users, **webhooks**; `public-api/routes/v1/public.integrations.controller.ts`; `services/auth/`: middleware, casl-style `permissions/{ability,guard,service,permission.exception.class,subscription.exception}`, `super.admin.guard.ts`, login providers (apple, farcaster, github, google, wallet, oauth.provider, providers.manager), `public.auth.middleware.ts`, widget auth middlewares.
- **Agent/chat infrastructure (`libraries/nestjs-libraries/src/chat/`):** `tools/` — 26 tools incl. `integration.schedule.post.ts`, `integration.connect.tool.ts`, `integration.list/trigger/validation.tool.ts`, `posts.list.tool.ts`, `delete.post.tool.ts`, `generate.image.tool.ts`, `generate.video.tool.ts`, `generate.video.options.tool.ts`, `media.list/status.tool.ts`, `upload.from.url.tool.ts`, `upload.widget.{tool,status,ticket}.tool.ts`, `clipping.{tool,status,widget.ticket}.tool.ts`, `video.function/status.tool.ts`, `post.settings.tool.ts`, `group.list.tool.ts`, `tool.list.ts` (registry), `ui/{clipping.widget,upload.widget}.ts`; `agent.tool.interface.ts`, `auth.context.ts`, `chat.module.ts`, `load.tools.service.ts`, `mastra.service.ts`, `mastra.store.ts`, `mcp.relay.service.ts`, `start.mcp.ts`, `oauth-middleware.ts`, `oauth-types.ts`, `async.storage.ts`, `validation.schemas.helper.ts`, `rules.description.decorator.ts`. Plus libs `agent/`: `agent.graph.service.ts`, `agent.graph.insert.service.ts`, `agent.categories.ts`, `agent.topics.ts`, `agent.module.ts`.
- **Orchestrator (`apps/orchestrator/src/`):** `activities/` — autopost, clipping, email, integrations, media, post, video; `signals/` — email, send.email; `workflows/` — `post-workflows/post.workflow.v1.0.1` … `v1.1.2` (12 versions), autopost, clipping, digest.email, generate.video, missing.post, process.media, refresh.token, send.email, streak, index; `health.controller.ts`, `app.module.ts`, `main.ts`.
- **Commands app:** `apps/commands/src/tasks/{agent.run.ts, configuration.ts, refresh.tokens.ts}`.
- **Libraries (`libraries/nestjs-libraries/src/`):** `database/prisma/` repos: admin-stats, agencies, announcements, autopost, clipping, errors, integrations, media, notifications, oauth, organizations, posts, sets, signatures, subscriptions, third-party, users, **webhooks** (repository + service); `dtos/` incl. `plugs/{providers-settings, transformers}`; `integrations/social/` (platform providers); `3rdparties/{heygen, hubspot, reelfarm}`; `deepgram/`; `openai/`; `redis/`; `sentry/`; `temporal/`; `throttler/`; `upload/`; `videos/{images-slides, seedance}`; `emails/`; `newsletter/providers/`; `services/{attribution, payment}/providers/`; `short-linking/providers/`; `track/`; `user/`; `chat/`+`agent/` above; webhooks DTOs incl. `webhook.url.validator.ts`.
- **Frontend (`apps/frontend/src/app/(app)/`):** pages for `agents/[id]`, analytics, billing (incl. lifetime), launches, media, plugs, settings, third-party, admin/{stats, errors}, auth flows, `integrations/connect/[token]` and `integrations/connect/social/[provider]`, preview routes, api/uploads proxy; UI webhooks settings page (`webhooks.tsx`), `mcp.client.icons.tsx` (frontend MCP client indicators); `public/` assets incl. platform icons and third-party.
- **SDK (`apps/sdk/`):** `src/index.ts`, tsup config, README, package.json — published programmatic client.
- **Extension (`apps/extension/`):** browser extension with `providers/{list/skool.provider.ts, cookie-provider.interface.ts, provider.registry.ts}`, background script, Vite build configs, publish workflow.
- **Ops:** GitHub workflows (build, build-containers, codeql, deploy-aws, issue-label-triggers, publish-extension, eslint), Dependabot, Jenkins build files, devcontainer, CodeRabbit review config, Sonar.

**Verified absences at tree level (search terms: `chief`, `of-staff`, `of staff`, `qdrant`, `postgres` filenames, `langgraph`).** No Chief-of-Staff implementation; no Qdrant/shared-knowledge layer (Prisma app DB, Redis, Mastra store and agent-graph services are the nearest counterparts); no CoS↔Chopify bridge visible in either tree. Postiz's own clipping/video/deepgram features overlap Chopify's role — ownership is an `OPEN` arbitration. Absence at tree level is not absence at code level — Phases 3/4 must re-verify inside files.

**Environment note from pre-survey.** The requester's sandbox did not contain the checked-out repo (only this tree dump plus the two source documents). Conclusions in this prompt are tree-level evidence; code-level verification is mandatory in Phases 2–4.
