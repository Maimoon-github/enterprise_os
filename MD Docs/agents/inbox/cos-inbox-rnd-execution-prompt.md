# R&D Execution Prompt — Inbox (`business-os/agents/inbox`) System Review & Chief-of-Staff Integration Readiness

> Copy this entire document into the executing agent's session as its task instruction.
> It is self-contained: role, sources, evidence baseline, method, phases, and acceptance checks.

---

## 0. Role, Mission, and Hard Constraints

**Role.** You are a Senior AI Systems Architect and R&D Engineer specializing in agentic business systems, integration layers, and inbox-domain automation.

**Mission.** Perform a complete, evidence-based review of the current active `business-os` project (inbox scope) to (a) understand the existing system, and (b) assess how a future **Chief of Staff (CoS) agent** can integrate with or modify it through the integration layer. Produce a review report with gap/risk/dependency registers and modification points.

**Primary evaluation criterion.** The integration layer's ability to support future CoS **command, delegation, orchestration, monitoring, and reporting**. Evaluate every finding against this criterion.

**Scope fence.** Inbox agent only (`business-os/agents/inbox`). The business platform is out of scope. Do not analyze it, do not design for it, and do not pull requirements from it.

**Hard constraints (non-negotiable).**
1. **Do not modify any project file.** Read-only review. No writes, no refactors, no config changes, no `git` state changes.
2. **Do not fabricate.** No invented repositories, capabilities, interfaces, endpoints, architecture details, or file contents. Every claim about the system must cite a concrete file path (and line/symbol where possible) or be labeled `ASSUMPTION` / `OPEN QUESTION`.
3. **Preserve the target architecture in all analysis and recommendations.** The seven elements are fixed vocabulary: (1) Chief of Staff agent; (2) independent specialized agents; (3) internal orchestrators; (4) individual UI per agent; (5) integration layer = APIs / MCP / webhooks / adapters; (6) shared intelligence; (7) controlled data access. Do not rename, merge, or drop elements.
4. **Separate evidence classes.** Tag every finding `FACT` (observed in repo/sources), `ASSUMPTION` (stated inference needing later validation), or `OPEN` (insufficient context).
5. **Flag ambiguities explicitly** where sources or code leave intent unclear. Do not resolve ambiguity by invention.

**Method (applies to all phases).**
- **ReAct:** Reason (state what you expect and why) → Act (inspect files/sources) → Observe (record evidence) → Refine (update the hypothesis, repeat).
- **Iterative self-correction:** maintain a hypothesis list; actively try to refute each finding; require at least one code citation (prefer two independent ones, e.g., route + test) before promoting a finding to `FACT`. Re-run greps with different terms to confirm absences ("no evidence of X" must list the search terms used and locations covered).
- **Chain-of-thought stays internal.** Expose only conclusions, decisions, and concise justifications with citations.

**Working environment facts (verified by the requester's pre-survey; re-verify on arrival).**
- Repository root for the inbox agent: `/enterprise_os/business-os/agents/inbox`; the project itself is the `inbox-zero/` monorepo (pnpm + turbo: `pnpm-workspace.yaml`, `turbo.json`).
- The sandbox where you run may not have the repo checked out. If the working directory does not contain the repo, stop, report the blocker, and request the checkout/location before proceeding. Do not simulate the review from memory of this prompt.

---

## 1. Source-Comprehension Plan (Agent Info & Recommended Architecture)

**Sources.** The chat-project sources **Agent Info** and **Recommended Architecture** are the baseline. Obtain their full text from the requester (chat-project export or pasted content) before Phase 1 begins. Do not substitute blog posts, memory of "Inbox Zero the product", or general agentic-architecture literature for these sources.

**Procedure.**
1. Read each source completely, twice: first for intent, second for normative statements (MUST/SHOULD/must-not, boundaries, ownership).
2. For each of the seven architecture elements, extract from the sources: intent, responsibilities, boundaries (what it may/may not do), interface expectations (what it exposes/consumes), and dependencies on other elements. Record as a structured table with verbatim quotes where the source is explicit.
3. Interpret both sources **within the inbox domain**: for each element, write the inbox-domain interpretation in one or two sentences (e.g., "internal orchestrator, inbox sense" = the assistant chat agent loop coordinating tool calls; "individual UI" = the per-account web/desktop surfaces).
4. Build a short glossary of project terms (agent, orchestrator, integration layer, shared intelligence, controlled data access) as the sources define them, to be used consistently in the report.
5. Where the sources are silent on an inbox-relevant topic (e.g., agent identity/authn model, job handoff protocol), record it as `OPEN` with the exact question — do not fill gaps from general knowledge.

**Output of this phase:** `source-comprehension.md` — the element/responsibility/boundary/interface table, inbox-domain interpretations, glossary, and the `OPEN` question list.

---

## 2. Inbox-Context Architecture Mapping

Map each architecture element onto the inbox domain and the current codebase. For each row: element → inbox-domain counterpart → candidate code anchors (from Appendix A) → status (`EXISTS` / `PARTIAL` / `ABSENT`) → citation.

| # | Architecture element | Inbox-domain counterpart to investigate |
|---|---|---|
| 1 | Chief of Staff agent | External command/orchestration consumer. Expect **no implementation** in this repo (pre-survey found zero `chief`/`of-staff`/`orchestrator` matches); assess the *receptacle* it would plug into. |
| 2 | Independent specialized agents | The inbox agent itself (this repo) plus internal sub-agents (e.g., `utils/mcp/mcp-agent.ts`, `apps/unsubscribe-worker`). |
| 3 | Internal orchestrators | Assistant chat agent loop (`utils/actions/assistant-chat.ts`, ~60 test suites), automation-jobs executor (`app/api/automation-jobs/*` + `cron/*`), rules engine (`utils/actions/ai-rule.ts`, webhook event processing in `utils/webhook/`), `packages/mail-core` engine/operations. |
| 4 | Individual UI | `apps/web` Next.js UI (`app/(app)/[emailAccountId]/*`, `components/assistant-chat/*`), `apps/desktop` Electron renderer, mobile routes (`app/api/mobile*`), messaging channels (Slack/Teams/Telegram). |
| 5 | Integration layer (APIs, MCP, webhooks, adapters) | REST + API keys (`app/api/user/api-keys`, `openapi.json`, `packages/api`), MCP server + client (`app/api/mcp-server/route.ts`, `app/api/mcp/[integration]/*`, `utils/mcp/*`, `plugins/inbox-zero-mcp`), webhooks (provider inbound: `google/webhook`, `outlook/webhook`, `slack/events`, `telegram/events`, `stripe/webhook`; outbound rule-action webhooks: `webhook-action`/`webhook-flow` tests, `WebhookSection` UI), adapters (`packages/mail-core` ports/protocol/backend-adapters, desktop IPC, `unsubscribe-worker/src/adapters`). |
| 6 | Shared intelligence | Knowledge base (`app/api/knowledge`, `knowledge-base-mcp.ts`, UI `KnowledgeBase.tsx`), memories (`user/memories`), learned patterns (`LearnedPatterns.tsx`, `assistant-chat-*learned-patterns*` tests), sender categorization (`ai/analyze-sender-pattern`, `user/categorize`), assistant-state (`mail/v1/accounts/[accountId]/assistant-state`). |
| 7 | Controlled data access | Scopes/capabilities routes (`mail/v1/accounts/[accountId]/scopes`, `/capabilities`), MCP access control (`utils/mcp/access.ts`, `McpConsent.tsx`, `startMcpOAuth.ts`), API keys + validation, `SensitiveDataPolicySetting`, phishing-hardening tests, `verify-standard-webhook.ts`. |

**Procedure.** Verify each candidate anchor in code (open the files; confirm role). Search for additional counterparts not covered by Appendix A (list your search terms). Every `ABSENT` verdict must cite the greps that established absence. Every `PARTIAL` verdict must state what exists and what is missing.

**Output of this phase:** `inbox-architecture-mapping.md` — the completed mapping table with citations and a one-paragraph narrative per element explaining how the inbox domain realizes (or fails to realize) it today.

---

## 3. Current-Project Inspection Plan

Inspect the active project bottom-up. Use Appendix A as the map; confirm every anchor before relying on it, and expand the map where your inspection reveals more.

**3.1 Structure & runtime topology (FACT harvest).**
- Monorepo layout: `apps/*`, `packages/*`, `plugins/*`, `docs/*`, infra (`docker-compose*.yml`, `charts/inbox-zero` Helm chart with web/worker/cronjobs/postgresql/redis, `copilot/` ECS + `webhook-gateway.yml`).
- For each app (`web`, `desktop`, `worker`, `image-proxy`, `image-proxy-aws`, `unsubscribe-worker`): runtime, entry point, responsibility, how it is reached by the others. Read each app's `package.json` and README.
- Read the top-level `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/mail-api-splits.md`, `docs/mail-packages.md`, `docs/openapi.json`, `docs/api-reference/**` (incl. `mcp.mdx`, `cli.mdx`), and `agents/inbox-zero-api-cli.md` + `clawhub/inbox-zero-api/SKILL.md` (agent-facing API/CLI documentation). These are the project's self-description; treat them as `FACT` about intent, then verify against code.

**3.2 Interfaces & contracts.**
- Enumerate the HTTP surface under `apps/web/app/api/**`: for each route group record method, auth mechanism, request/response types, and whether it appears in `openapi.json` or `docs/api-reference`. Priority order: `mail/v1/**` (esp. `operations/[commandId]`, `scopes`, `capabilities`, `assistant-state`, `changes/batch`), `mcp-server`, `mcp/[integration]`, `user/api-keys`, `chat/*`, `automation-jobs/*`, `webhook`-related routes, `health`.
- MCP: server side (`app/api/mcp-server/route.ts`, `plugins/inbox-zero-mcp/mcp.json`, docs `mcp.mdx`), client side (`utils/mcp/mcp-agent.ts`, `mcp-tools.ts`, providers registry `utils/mcp/providers/{registry,composio}.ts`, `knowledge-base-mcp.ts`, `todoist-mcp.ts`, custom MCP server), consent/OAuth (`app/api/mcp/[integration]/{auth-url,callback,provider-callback}`, `McpConsent.tsx`, `startMcpOAuth.ts`), e2e `mcp-access.spec.ts`.
- Webhooks: inbound provider events (`app/api/{google,outlook,apple,slack,telegram,teams,stripe,lemon-squeezy,loops,recall}/…webhook|events`), outbound webhook rule-actions (`webhook-action.test.ts`, `webhook-flow.test.ts`, `WebhookSection.tsx`/`WebhookGenerate.tsx`/`WebhookDocumentation.tsx`, `utils/webhooks/verify-standard-webhook.ts`, `copilot/templates/webhook-gateway.yml`).
- Adapters/ports: `packages/mail-core/src/ports/*` (`assistant-source`, `mail-store`, `mailbox-source`, `operation-executor`, `runtime`) and `protocol/*` (`backend-adapter`, `routed-backend-adapter`, `mail-http`, `mail-ipc-*`); desktop IPC (`apps/desktop/src/mail-engine/ipc.ts`, renderer `desktop-api.ts`).
- Client package: `packages/api` (`client.ts`, `io.ts`, `api-types.ts`) and the documented CLI.

**3.3 Boundaries.** For each surface answer: who can call it (user session, API key, MCP client, webhook signature, internal service), what account/organization scoping applies, and what prevents cross-account or over-privileged access. Inspect actual middleware/auth code (better-auth `app/api/auth/[...all]`, API-key validation, `access.ts`, `verify-standard-webhook.ts`, scopes routes). Note the licensing boundary of `ee/` (billing; check `ee/LICENSE.md`) — flag anything the CoS would reuse that sits behind it.

**3.4 Internal orchestrators & agent internals.**
- Assistant chat: server-action boundary (`utils/actions/assistant-chat.ts`, `.validation.ts`, `assistant-chat.server-action-boundary.test.ts`), tool set (from `assistant-chat-*-tools` tests and `components/assistant-chat/tools.tsx`), confirmation flow (`chat/confirm-email-action`, `assistant-chat-confirmation.ts`), persistence (`chat-message-persistence.ts`), streaming (`chat/[id]/stream`, `[id]/stop`).
- Automation: job model (`utils/actions/automation-jobs.ts` + helpers + validation), execution path (API `automation-jobs/execute` + `queue`, `cron/automation-jobs`), scheduled actions/emails/snoozed-threads execute routes, rules engine (`ai-rule.ts`, webhook event processing `utils/webhook/{google,outlook}/process-history*`, executed-rules counters in `organizations/[organizationId]/executed-rules-count`).
- Bulk workflows: `bulk-inbox-action` (API `process` + `user/bulk-inbox-action/[jobId]` status + `bulk-inbox-action-card.tsx` UI) — likely the closest existing analogue to CoS-style delegated batch tasks.

**3.5 UI inventory.** Web (`app/(app)/[emailAccountId]/**`: assistant settings, knowledge, rules, learned patterns, API keys/MCP/webhook sections, AIChatButton), desktop (Electron renderer + `mail-ui`), mobile routes, external messaging channels (Slack `commands`/`events`, Telegram, Teams, `messaging-channel-hint.tsx`). For each: how a human drives the inbox agent today — these are the interaction patterns a CoS would replace or reuse.

**Output of this phase:** `project-inspection.md` — per-area findings with citations; the verified interface inventory table; the boundary/authz matrix; explicitly listed absences (with search terms used).

---

## 4. Integration-Layer Assessment Plan (CoS Lenses)

Assess each integration channel against the five CoS capabilities. For every (channel × capability) cell assign a readiness rating with evidence:

- **0 – Absent** (no surface found; cite the negative searches)
- **1 – Partial** (surface exists but not agent-consumable as-is: e.g., user-session-only auth, no machine identity, no contract doc)
- **2 – Ready** (documented contract, non-interactive authn, scoped access, test coverage)
- **3 – Extensible** (ready *and* designed for third-party/machine consumers: pluggable registry, versioned contract, consent tiers, idempotency keys)

| Channel \ Lens | Command (issue/authorize actions) | Delegation (hand off task, track status) | Orchestration (multi-step, idempotent, cancellable) | Monitoring (events, state changes, health) | Reporting (stats, audit, analytics) |
|---|---|---|---|---|---|
| REST + API keys (`user/api-keys`, `packages/api`, `openapi.json`, docs endpoints) | | | | | |
| MCP server (`mcp-server/route.ts`, `plugins/inbox-zero-mcp`, `mcp.mdx`) | | | | | |
| Webhooks outbound (rule-action webhooks, Standard Webhooks verify, `webhook-gateway.yml`) | | | | | |
| Adapters/ports (`mail-core` ports, backend-adapters, desktop IPC) | | | | | |
| Messaging channels (Slack/Teams/Telegram) | | | | | |

**Concrete questions each cell must answer** (inspect code, not file names):
- **Command:** Can an external principal *authenticate* (API key? OAuth? MCP?) and *act* (send, archive, create rule, run bulk action)? Which routes/tools, and with what scopes/consent (`scopes`, `capabilities`, `access.ts`, `McpConsent`)? Is there an authorization/confirmation gate (`confirm-email-action`) that a CoS must satisfy?
- **Delegation:** Is there a job/task abstraction an external caller can create and poll (`automation-jobs`, `bulk-inbox-action/[jobId]`, `operations/[commandId]`)? Idempotency keys? Status endpoints? Cancellation (`chat/[id]/stop`, job stop paths)?
- **Orchestration:** Can multi-step workflows be composed externally (rule CRUD via docs endpoints, `RuleImportExportSetting`, MCP tool composition)? What transactional/atomicity guarantees exist (`mail-core` operations, optimistic-client)? Failure semantics (partial-action-failure tests)?
- **Monitoring:** Are state changes observable externally — outbound webhooks per event type? streaming endpoints (`mail-stream`, `email-stream`, `chat/[id]/stream`)? health (`app/api/health`, desktop `health.ts`)? An event catalog?
- **Reporting:** Stats/audit surfaces (`organizations/[organizationId]/stats/*`, `executed-rules-count`, Tinybird packages `tinybird`, `tinybird-ai-analytics`, `admin/top-spenders`), chat history/audit trails, retention (`cron/*retention*`). What can a CoS read without DB access?

**Output of this phase:** `integration-assessment.md` — the filled 5×5 readiness matrix with citations per cell, plus the top-5 findings that most affect CoS feasibility.

---

## 5. Gap / Risk / Dependency / Modification-Point Analysis Plan

**5.1 Gap register.** For each CoS capability lens, list what is missing for a CoS to command this inbox agent through the integration layer — derived strictly from the matrix in Phase 4 and the boundary matrix in Phase 3.3. Candidate gaps to confirm or refute (do not assert them as fact; they are hypotheses from the pre-survey): machine-scoped credentials/identity model for agents; externally creatable jobs/tasks; an event-subscription API (typed outbound events beyond rule-action webhooks); a documented CoS-facing command contract; per-action audit trail exposed via API; rate limiting/quota semantics for machine callers.

**5.2 Risk register.** For each gap and each reused surface: description, affected CoS lens, likelihood × impact, mitigation. Consider at minimum: security (API-key scope granularity, webhook signature verification coverage, MCP consent bypass), correctness (idempotent command execution, race with rules engine), safety (phishing-hardening assumptions under agent-driven actions, sensitive-data policy), operability (queue capacity, streaming stability), licensing (`ee/` boundary), and contract drift (openapi.json vs actual routes; tests as the executable spec).

**5.3 Dependency map.** Runtime dependencies: Postgres/Prisma (migrations dir), Redis (queue/stream?), provider APIs (Google/Outlook watch webhooks, calendar/drive/linking), Composio + custom MCP providers, Tinybird, Slack/Telegram/Teams, Stripe/LemonSqueezy/Loops/Apple/Resend. Build-time/deploy dependencies: turbo pipeline, docker-compose, Helm, copilot ECS. Mark which dependencies a CoS integration would add load to or require changes in.

**5.4 Modification points.** Rank candidate change sites by minimal-touch principle, each with: file/area, what would change, which CoS lens it serves, blast radius, and whether it is additive (new route/plugin) or invasive (auth model, job executor). Candidates to evaluate (verify before including): extend `plugins/inbox-zero-mcp` + `mcp-server/route.ts` (new CoS tool namespace); extend `packages/api` client; add scoped machine API keys (Prisma `api_key` model already exists — verify its fields); formalize `operations/[commandId]` as the command envelope; add outbound event subscriptions beside rule-action webhooks; expose job status via `automation-jobs`. Explicitly separate **integration-only** (no repo change; CoS consumes existing surfaces) from **modification** (repo change) options.

**Output of this phase:** `gap-risk-dependency-analysis.md` — three registers + ranked modification points, each row carrying citations or an explicit `ASSUMPTION`/`OPEN` tag.

---

## 6. Step-by-Step Execution Methodology

Execute phases in order; each phase gates the next. Work in ReAct cycles and record everything in a worklog.

1. **Gate 0 — Environment & inputs.** Confirm repo location/branch (root `/enterprise_os/business-os/agents/inbox`); obtain Agent Info and Recommended Architecture source texts. If either is missing, record `OPEN` and proceed only with Phase 2–5 using Appendix A, marking all source-dependent conclusions as provisional.
2. **Phase 1 — Sources** (Section 1). Produce `source-comprehension.md`.
3. **Phase 2 — Mapping** (Section 2). Verify every Appendix A anchor against code before use. Produce `inbox-architecture-mapping.md`.
4. **Phase 3 — Inspection** (Section 3). Bottom-up: structure → interfaces → boundaries → orchestrators → UI. Produce `project-inspection.md`.
5. **Phase 4 — Integration assessment** (Section 4). Fill the matrix; for each cell open the actual code. Produce `integration-assessment.md`.
6. **Phase 5 — Analysis** (Section 5). Registers + modification points. Produce `gap-risk-dependency-analysis.md`.
7. **Phase 6 — Self-correction pass.** Re-audit your own report: (a) every `FACT` has ≥1 citation; (b) every `ABSENT` lists negative-search terms; (c) every register row is either cited or tagged; (d) re-run three adversarial greps attempting to refute your strongest claims (e.g., search for alternate auth paths, undocumented routes, event emitters); (e) check scope fence — no business-platform content.
8. **Phase 7 — Recommendations** (Section 8) and final report assembly.
9. **Throughout:** update the evidence ledger (`FACT` / `ASSUMPTION` / `OPEN`) and the worklog after every ReAct cycle; never batch-write findings from memory at the end.

**Deliverables to produce:** `review-report.md` (executive summary, per-phase findings, matrix, registers, recommendations), the six per-phase artifacts above, and `worklog.md` (cycle log: reason → action → evidence → refinement). Save all under a single `cos-inbox-review/` directory. Do not modify anything inside the repo.

---

## 7. Measurable Acceptance Checks

The report passes only if every check is demonstrably true:

- [ ] **A1 — Sources reviewed & mapped:** Agent Info and Recommended Architecture element tables exist with verbatim quotes or an `OPEN` flag explaining how the review proceeded without them; inbox-domain interpretation written for all 7 elements.
- [ ] **A2 — Inspection cited:** ≥25 distinct file paths cited across `project-inspection.md`; every interface-inventory row has a path; every claimed absence lists search terms used.
- [ ] **A3 — Integration layer assessed:** the 5×5 matrix is fully filled, every cell has a readiness rating + citation, and the five CoS capabilities (command, delegation, orchestration, monitoring, reporting) are each covered for all four channels (APIs, MCP, webhooks, adapters).
- [ ] **A4 — Registers complete:** gap, risk (with likelihood/impact/mitigation), and dependency registers each have ≥5 rows; modification points ≥5, ranked, each labeled additive vs invasive.
- [ ] **A5 — Methodology followed:** `worklog.md` shows ReAct cycles per phase and the Phase 6 self-correction pass results, including the three adversarial refutation attempts.
- [ ] **A6 — Ambiguities flagged:** a dedicated ambiguity section lists every `OPEN` item with the question and what is needed to resolve it; `ASSUMPTION` items are listed with their validation condition.
- [ ] **A7 — No unsupported claims:** spot-check 10 random `FACT` claims — each resolves to a real file/line in the repo; zero fabricated endpoints or capabilities.
- [ ] **A8 — Scope fence holds:** no business-platform analysis; no project files modified (`git status` clean at the end, modulo untracked review-output directory outside the repo).

---

## 8. Goal-Oriented Next-Step Recommendations

Close the report with recommendations that a decision-maker can act on, in this structure:

1. **Integration posture decision.** Recommend one primary posture, justified by evidence: (a) *consume-only* — CoS drives the inbox agent through existing API keys + MCP server + webhooks with zero repo change; (b) *contract-first extension* — formalize a CoS command contract (new MCP tool namespace and/or versioned REST surface on `mail/v1/operations`) with scoped machine credentials; (c) *deep integration* — shared job/event bus. State the evidence that drove the choice and what would change the decision.
2. **Sequenced roadmap.** 3–4 phases, each with: goal, concrete change/consumption steps anchored to the modification points from Section 5.4, the CoS lens it unlocks, and a verification method (which tests/specs prove it). Order must respect dependencies from the dependency map (e.g., machine identity before command surface; command surface before delegation status API).
3. **Risk burn-down.** Map the top risks to roadmap phases (each phase should retire at least one risk) and name the security/safety gates the CoS must pass (consent model, scopes, idempotency, audit).
4. **Open decisions for the requester.** Enumerate the `OPEN` items that block design (e.g., CoS identity model, event taxonomy ownership, ee/ licensing constraints) with the specific input needed from the architecture owners.

Recommendations must stay inside the inbox scope and must not redesign the CoS itself — the deliverable is how the inbox agent receives and supports CoS command/orchestration, not the CoS's internals.

---

## Appendix A — Baseline Evidence (from requester's pre-survey of the file tree)

Verified `FACT`s from the uploaded tree dump of `/enterprise_os/business-os/agents/inbox` (project dir `inbox-zero/`). Re-verify in code before relying on any anchor. Paths below are relative to `inbox-zero/`.

**Monorepo & apps.** pnpm+turbo (`pnpm-workspace.yaml`, `turbo.json`); `apps/web` (Next.js: UI + `app/api/**`), `apps/desktop` (Electron, `src/mail-engine/{ipc,sqlite,utility-host}.ts`, renderer `src/renderer/desktop-api.ts`), `apps/worker` (`src/{index,runtime}.mjs` — small, purpose to verify), `apps/image-proxy` (+`-aws`), `apps/unsubscribe-worker` (headless-browser unsubscribe service, `src/adapters/docker.ts`, `contracts.ts`, `server/service/runner.ts`, `verify-egress.ts`). Packages: `api` (typed client `client.ts`/`io.ts`/`api-types.ts`), `cli` (AWS/GCP/Vercel/Terraform setup), `mail-core` (ports: `assistant-source.ts`, `mail-store.ts`, `mailbox-source.ts`, `operation-executor.ts`, `runtime.ts`; protocol: `backend-adapter.ts`, `routed-backend-adapter.ts`, `mail-http.ts`, `mail-ipc-{client,}.ts`; `engine.ts`, `operations.ts`, `commands.ts`, `optimistic-client.ts`, `query-semantics.ts`, `sync.ts`), `mail-react`, `mail-sqlite`, `mail-ui`, `scheduling`, `tinybird`(+`-ai-analytics`), `transactional-email`, `email-editor`, `loops`, `network`. `plugins/inbox-zero-mcp` (`mcp.json`, `plugin.json`, SKILL.md). Repo-level agent tooling: `AGENTS.md`, `CLAUDE.md`, `.claude/agents/reviewer.md` + `.claude/skills/*`, `.codex/`, `.conductor/`, `.cursor-plugin/`, `agents/inbox-zero-api-cli.md`, `clawhub/inbox-zero-api/SKILL.md` + `references/cli-reference.md`. Docs: `docs/{openapi.json, mail-api-splits.md, mail-packages.md, api-reference/{introduction,cli,mcp}.mdx + endpoint/*.mdx (rules CRUD, stats, senders-unsubscribe), hosting/}`. Infra: `docker-compose{,.dev,.local}.yml`, `charts/inbox-zero` (Helm: web/worker deployments, cronjobs, postgresql, redis, redis-http), `copilot/` (ECS manifest, RDS/ElastiCache addons, `templates/webhook-gateway.yml`).

**API surface highlights (`apps/web/app/api/`).** `mail/v1/accounts/[accountId]/{assistant-state,bootstrap,capabilities,changes/batch,enumeration,hydration,operations/[commandId],scopes,search,splits}` + `mail/v1/devices`; `mcp-server/route.ts`; `mcp/[integration]/{arg-options,auth-url,callback,provider-callback}` + `mcp/integrations`; `user/api-keys`; `chat/{route,[id]/stream,[id]/stop,confirm-email-action}` + `chat-message-persistence.ts`; `chats`; `automation-jobs/execute{,/queue}`; `bulk-inbox-action/process`; `cron/{automation-jobs,draft-cleanup/*,*-retention,scheduled-actions,snoozed-threads…}`; `scheduled-actions/execute`, `scheduled-emails/execute`; `ai/{analyze-sender-pattern,compose-autocomplete,digest{,/queue},models,summarise,translate}`; provider/channel webhooks: `google/{calendar,drive,linking}/…+webhook`, `outlook/{admin-consent,calendar,drive,linking,watch,webhook}`, `apple/webhook`, `slack/{auth-url,callback,commands,events}`, `telegram/events`, `teams/events`, `recall/webhook`, `stripe/webhook`(+invoice-email), `lemon-squeezy/webhook`, `loops/webhook`; `auth/[...all]`, `sso/signin`, `mobile-auth/{browser-start,callback,exchange-code,start}`, `mobile/*`; `organizations/[organizationId]/{rules,members,stats/{email-buckets,rules-buckets,totals},executed-rules-count}`; `threads/{[id]/{archive,trash,unarchive,untrash},all,basic,batch}`; `messages/{attachment,batch,calendar-invitation,forward,send,source}`; `knowledge`; `labels/*`; `health`; `unsubscribe`; `reply-tracker/disable-unused-auto-draft`; `user/{account,ai-automation-status,api-keys,automation-jobs,bulk-inbox-action/[jobId],categories,categorize/senders/{batch,simple,categorized,progress,uncategorized},cold-email,contacts,digest-*,draft-*,memories,rules,…}`; `team-comments/*`(+`stream`); `email-stream`, `mail-stream`; `openapi.json` (multiple specs), plus Prisma migrations incl. `20240728084326_api_key`.

**Agent internals.** `utils/actions/assistant-chat.ts` (+ `.validation.ts`, server-action-boundary test) with ~60 test suites covering core tools, email actions, inbox-workflows (triage/search), rule editing (create/patch semantics/overlap exceptions/learned patterns), memory-safety, phishing-hardening, progressive-disclosure, long-context-trimming, bulk-inbox-action, partial-action-failures, final-reply-step, reply-language, calendar, outlook folders. `utils/actions/{ai-rule.ts,automation-jobs.ts(+helpers,validation),api-key.ts,admin.ts}`. MCP client: `utils/mcp/{mcp-agent.ts,mcp-tools.ts,docs-tools.ts,access.ts,account-selection.ts,providers/{registry.ts,composio.ts,types.ts}}`, `knowledge-base-mcp.ts`, `todoist-mcp.ts`, `custom-mcp-server(.test).ts`, `ai-mcp-agent.test.ts`; UI: `McpConsent.tsx`, `startMcpOAuth.ts`, `AddCustomMcpServerDialog.tsx`, `McpSection.tsx`, e2e `mcp-access.spec.ts`, `api-keys.spec.ts`. Webhook processing: `utils/webhook/{google/*,outlook/*,process-history*,validate-webhook-account.ts,error-handler.ts}`, `utils/webhooks/verify-standard-webhook.ts`, rule-action webhooks (`webhook-action.test.ts`, `webhook-flow.test.ts`), settings UI `WebhookSection.tsx`/`WebhookGenerate.tsx`/`WebhookDocumentation.tsx` + `useApiKeys.ts` + `ApiKeysSection.tsx`/`ApiKeysCreateForm.tsx`. UI: `components/assistant-chat/*` (`chat.tsx`, `tools.tsx`, `tool-label.ts`, `inline-email-card.tsx`, `inline-rule-suggestion-card.tsx`, `rule-summary-card.tsx`, `bulk-inbox-action-card.tsx`, `messaging-channel-hint.tsx`, `ChatHistoryItem.tsx`), `app/(app)/[emailAccountId]/assistant/**` (rules, knowledge `KnowledgeBase.tsx`, learned patterns `LearnedPatterns.tsx`, settings incl. `SensitiveDataPolicySetting.tsx`, `RuleImportExportSetting.tsx`, `WritingStyleSetting.tsx`, `LearnedPatternsSetting.tsx`, `AIChatButton.tsx`), `ee/billing/{apple,lemon,stripe}` (+ `ee/LICENSE.md`).

**Verified absences in the tree dump (searched: filenames + content markers).** No `chief`, no `of-staff`/`of staff`, no `orchestrat*` (single false positive: `index.openrouter-cost.test.ts` = "openrouter"). No dedicated CoS-facing API, job-submission API, or external event-subscription API is visible at tree level. Absence at tree level is not absence at code level — Phase 3/4 must re-verify inside files.

**Environment note from pre-survey.** The requester's sandbox did not contain the checked-out repo (only this tree dump; the local git repo there holds only an upload folder). Conclusions in this prompt are therefore tree-level evidence; code-level verification is mandatory in Phases 2–4.
