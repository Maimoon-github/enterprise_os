# R&D Execution Prompt — Finance (`business-os/agents/finance`) System Review & Chief-of-Staff Integration Readiness

> Copy this entire document into the executing agent's session as its task instruction.
> It is self-contained: role, sources, evidence baseline, method, phases, and acceptance checks.

---

## 0. Role, Mission, and Hard Constraints

**Role.** You are a Senior AI Systems Architect and R&D Engineer specializing in agentic business systems, integration layers, and finance-domain automation.

**Mission.** Perform a complete, evidence-based review of the current active `business-os` project — finance scope — to (a) understand the existing system, and (b) assess how a future **Chief of Staff (CoS) agent** can integrate with or modify it through the integration layer. Produce a review report with gap/risk/dependency registers and ranked modification points.

**Primary evaluation criterion.** The integration layer's ability to support future CoS **command, delegation, orchestration, monitoring, and reporting**. Evaluate every finding against this criterion.

**Scope fence.** Finance agent only (`business-os/agents/finance`). The business platform is out of scope. Do not analyze it, design for it, or pull requirements from it.

**Hard constraints (non-negotiable).**
1. **Do not modify any project file.** Read-only review. No writes, refactors, config changes, or `git` state changes.
2. **Do not fabricate.** No invented repositories, capabilities, interfaces, endpoints, or architecture details. Every claim about the system must cite a concrete file path (plus line/symbol where possible) or be tagged `ASSUMPTION` / `OPEN`.
3. **Preserve the target architecture vocabulary in all analysis and recommendations.** The seven elements are fixed: (1) Chief of Staff agent; (2) independent specialized agents; (3) internal orchestrators; (4) individual UI per agent; (5) integration layer = APIs / MCP / webhooks / adapters; (6) shared intelligence; (7) controlled data access. Do not rename, merge, or drop elements.
4. **Separate evidence classes.** Tag every finding `FACT` (observed in repo/sources), `ASSUMPTION` (stated inference needing validation), or `OPEN` (insufficient context).
5. **Flag ambiguities explicitly** where sources or code leave intent unclear. Never resolve ambiguity by invention.
6. **Finance-domain caution.** Money, ledger, and payment-rail findings carry correctness/security weight out of proportion to other domains. Claims about posting paths, invariants, and idempotency must be verified in code, not inferred from names.

**Method (applies to all phases).**
- **ReAct:** Reason (state the expectation and why) → Act (inspect files/sources) → Observe (record evidence) → Refine (update the hypothesis, repeat).
- **Iterative self-correction:** keep a hypothesis list; actively attempt refutation; promote a finding to `FACT` only with ≥1 code citation, preferably two independent ones (e.g., route + service + test). "No evidence of X" must list the search terms used and locations covered.
- **Chain-of-thought stays internal.** Expose only conclusions, decisions, and concise justifications with citations.

**Working environment facts (verified by the requester's pre-survey; re-verify on arrival).**
- Repository root for the finance agent: `/enterprise_os/business-os/agents/finance`; the project itself is the `OpenBooks/` monorepo (Yarn 4: `.yarnrc.yml`, `yarn.lock`). Agent-level files beside the project: `prompt.md` (content unknown — likely the finance agent's local definition; read it first), `README.md`.
- The sandbox may not have the repo checked out. If the working directory lacks the repo, stop, report the blocker, and request the checkout/location. Do not simulate the review from this prompt.

---

## 1. Source-Comprehension Plan (Agent Info & Recommended Architecture)

**Sources.** The chat-project sources **Agent Info** and **Recommended Architecture** are the baseline. Obtain their full text from the requester before Phase 1 begins. Do not substitute general accounting-domain or agentic-architecture literature for them.

**Procedure.**
1. Read each source completely, twice: first for intent, second for normative statements (MUST/SHOULD, boundaries, ownership, data-access rules).
2. For each of the seven architecture elements, extract: intent, responsibilities, boundaries (what it may/may not do), interface expectations (what it exposes/consumes), dependencies on other elements. Record as a structured table with verbatim quotes where the source is explicit.
3. Interpret both sources **within the financial context**: for each element write the finance-domain interpretation (e.g., "internal orchestrator, finance sense" = the automations engine sequencing jobs that post to the ledger; "controlled data access, finance sense" = permissioned, tenant-scoped, audit-logged ledger access where direct journal writes are forbidden outside the kernel).
4. Build a glossary from the sources, then reconcile it with the project's own `docs/glossary.md` — mismatches are findings, not errors to silently normalize.
5. Where the sources are silent on a finance-relevant topic (agent identity/authn model, approval semantics for money-moving commands, event taxonomy), record `OPEN` with the exact question — do not fill gaps from general knowledge.

**Output of this phase:** `source-comprehension.md` — element/responsibility/boundary/interface table, finance-domain interpretations, glossary reconciliation, and the `OPEN` question list.

---

## 2. Finance-Context Architecture Mapping

Map each architecture element onto the finance domain and the current codebase. For each row: element → finance-domain counterpart → candidate code anchors (from Appendix A) → status (`EXISTS` / `PARTIAL` / `ABSENT`) → citation.

| # | Architecture element | Finance-domain counterpart to investigate |
|---|---|---|
| 1 | Chief of Staff agent | External command/orchestration consumer. Expect **no CoS implementation** in this repo (pre-survey found zero `chief`/`of-staff`/`orchestrat*` matches); assess the *receptacle* it would plug into. |
| 2 | Independent specialized agents | The finance agent (this repo) plus internal sub-agents; note the existing agent-native surface: `modules/agents/review.service.ts`, `routes/agent-proposals.ts`, web `screens/agent-proposals/*` — an agent-proposes/human-reviews workflow. |
| 3 | Internal orchestrators | `modules/automations` (`engine.ts`, `job.ts`, `queue.service.ts`), `modules/pay-bills` (`queue.service`, `issue.service`, `rail-disbursements.service`), `modules/recurring-journals` (`engine.ts`, `job.ts`), bank-feeds `feed-sync.job.ts`, payments-processing `poll.job.ts`, worker entrypoint `entrypoints/worker.ts`, `routes/scheduling.ts`. |
| 4 | Individual UI | `packages/web` (Vite + React): `src/screens/*` (accounts, agent-proposals, api-keys, automations, budgets, journals, pay-bills, processing, reports, roles, settings, work-items…), `src/shell/{app-shell,nav,org-switcher}`, thin client (`src/api/client.ts`, `lib/thin-client.ts`, `api/idempotency.ts`). |
| 5 | Integration layer (APIs, MCP, webhooks, adapters) | REST + OpenAPI (`server/src/transport/{app.ts,openapi.ts,idempotency.ts,health.ts}`, `transport/routes/*` ~50 files, root `openapi.json`); API keys (`modules/api-keys`, `auth/api-key-identity.ts`, `db/api-key-lookup.ts`); OAuth (`modules/oauth`, routes `oauth-clients`/`oauth-flow`, web `oauth-consent.tsx`); MCP server (`modules/mcp/{host.ts,tools.ts}`, `plugin-api/src/mcp.ts`, e2e `platform-oauth-mcp.spec.ts`); webhooks (inbound processor events: `modules/payments-processing/webhook.service.ts` + `routes/processing-webhook.ts` + `processor-events.repository.ts`, polling fallback `poll.job.ts`); adapters (`modules/reports/export/{adapters.ts,csv.ts,xlsx.ts}`, `plugin-api/src/providers.ts`, `modules/providers`, `config/providers.ts`); eventing (`routes/change-feed.ts`). |
| 6 | Shared intelligence | Ledger kernel (`modules/ledger`: `journal-read.service`, `posting.service`, `trial-balance.service`, migration `0005_subledger`), reports (`modules/reports`: aging, balance-sheet, cash-basis, audit.repository/service), provenance logging (`logging/provenance.ts`, `modules/log-retention`, migration `0026_logs`), docs `docs/architecture/ledger-kernel.md` + `money-and-invariants.md`. |
| 7 | Controlled data access | Permissions (`modules/permissions/{catalog,permissions.service}`, routes `roles.ts`), tenancy (`db/tenant.ts`, `db/org-scope.ts`, migration `0001_tenancy`), auth identities (`modules/auth`: api-key, oauth, password, tokens), app grants (migration `0999_app_grants.ts`), field encryption (`crypto/field-encryption.ts`), redaction (`config/redact.ts`, `logging/redact.ts`), ledger-write enforcement (`eslint-plugin/src/rules/no-journal-writes.js`, `modules/enforcement`), idempotency (migration `0003_idempotency`, `modules/idempotency`, `transport/idempotency.ts`), plugin permission model (`plugin-api/src/{actor.ts,permissions.ts}`). |

**Procedure.** Verify every candidate anchor in code before relying on it; search for counterparts not covered by Appendix A (list your search terms). Every `ABSENT` verdict cites the greps that established absence; every `PARTIAL` verdict states what exists and what is missing.

**Output of this phase:** `finance-architecture-mapping.md` — completed mapping table with citations plus a one-paragraph narrative per element explaining how the finance domain realizes (or fails to realize) it today.

---

## 3. Current-Project Inspection Plan

Inspect bottom-up. Use Appendix A as the map; confirm every anchor before relying on it, and expand the map where inspection reveals more.

**3.1 Self-description first.** Read `README.md`, `CLAUDE.md`, `ROADMAP.md`, root `prompt.md` (agent-level), and the docs set: `docs/architecture/{overview,api-and-transport,data-and-tenancy,ledger-kernel,money-and-invariants,providers-and-config,security}.md`, `docs/features/{foundation,frontend,banking-and-cash,payments-processing,purchases-ap,sales-ar,reporting-and-tax,platform-and-ai}.md`, ADRs (`docs/decisions/index.md`), `docs/guides/*`, `docs/glossary.md`. Treat these as `FACT` about intent, then verify against code. `platform-and-ai.md` and `ROADMAP.md` are especially relevant to CoS readiness — read them fully.

**3.2 Runtime topology.** Entrypoints (`entrypoints/{api,worker,main,migrate-cli,migrate,spec}.ts`); build (`scripts/build-server.mjs`, `codegen.mjs`); infra (`docker-compose.yml` with MySQL, `docker/mysql-init/*`, `infra/nginx/openbooks-web.conf`, Terraform modules: compute (ECS), data (RDS), edge (ALB/CloudFront/ACM), messaging (S3/SES/SQS), network, KMS, state-backend). Establish: what runs where, what queues exist (SQS), how worker consumes jobs.

**3.3 Interfaces & contracts.**
- Enumerate the REST surface: every file in `server/src/transport/routes/` (47 files) — record path, methods, auth requirement, idempotency behavior, org/tenant scoping. Priority: `agent-proposals.ts`, `automations.ts`, `work-items`-related routes, `api-keys.ts`, `oauth-clients.ts`/`oauth-flow.ts`, `change-feed.ts`, `external-refs.ts`, `processing-webhook.ts`, `scheduling.ts`, `roles.ts`, `health.ts`.
- Cross-check routes against root `openapi.json` and `transport/openapi.ts` (drift is a finding; `web/scripts/check-client-drift.mjs` suggests drift is a known concern).
- MCP: read `modules/mcp/host.ts` and `tools.ts` fully — which tools are exposed, under which actor/permissions, how consent works; read `plugin-api/src/mcp.ts` and the e2e `platform-oauth-mcp.spec.ts` (the executable spec of MCP behavior).
- Plugin system: read the whole `plugin-api` package (`actor`, `context`, `events`, `module`, `permissions`, `posting`, `primitives`, `providers`, `registry`, `routes`, `migrations`) — this SDK is the designed extension surface a CoS might ride on.
- Webhooks: `payments-processing` webhook.service + `processing-webhook` route — signature verification, replay protection, event types; the polling fallback and its trade-offs.
- Adapters: report export adapters (csv/xlsx/tabular), provider adapters (`modules/providers`, `config/providers.ts`), `plugin-api/providers.ts`.

**3.4 Boundaries, authn/authz, and money safety.**
- Identity: `modules/auth/*` (api-key-identity, oauth-identity, tokens, cookie, password), `context/authentication.ts`, `db/{api-key-lookup,oauth-lookup}.ts`. For each: what principal types exist (user? app? machine? plugin actor?) — decisive for CoS identity.
- Authorization: `modules/permissions/catalog.ts` (the permission vocabulary), `roles.ts`, `0999_app_grants.ts`, `plugin-api/permissions.ts`, `modules/enforcement`. Determine how a non-human principal gets scoped permissions.
- Tenancy: `db/{tenant.ts,org-scope.ts,tenant-tables.ts}` — every route's isolation guarantees; cross-tenant risk is a top-tier finance risk.
- Ledger integrity: `docs/architecture/money-and-invariants.md` + `ledger-kernel.md` verified against `modules/ledger/*` and the eslint rules `no-float-money.js`, `no-journal-writes.js` (what they enforce and where they're applied — `eslint.config.js`). Posting paths (`posting.service.ts`, `plugin-api/posting.ts`), `db/transaction-scope.ts`.
- Idempotency & delivery: migration `0003_idempotency`, `modules/idempotency`, `transport/idempotency.ts`, `db/delivery-lookup.ts`, `web/src/api/idempotency.ts` — how command retries behave (decisive for CoS command semantics).
- Secrets/PII: `crypto/field-encryption.ts`, `config/redact.ts`, `logging/redact.ts`, `db/secrets-store.ts`, `infra/terraform/{secrets.tf,kms.tf}`.

**3.5 Internal orchestrators & job model.** Automations engine (`automations/{engine,job,queue.service,repository}` + migration `0018_automations` + e2e `automations.spec.ts`): what job types exist, how results are recorded, retry/timeout semantics. Pay-bills pipeline (`pay-bills/{queue.service,issue.service,rail-disbursements.service,check-output}` + e2e `pay-bills.spec.ts`): the closest analogue to delegated money-moving tasks. Recurring journals engine; bank-feeds sync jobs; payments `poll.job.ts`. Worker entrypoint responsibilities. The `agents` module + `agent-proposals` route + web review UI: the existing propose→review→apply loop — the single most important precedent for CoS delegation.

**3.6 UI inventory.** Web screens list (from `src/screens/*` and `App.tsx`/`nav.ts`): which human workflows exist (books, approvals, payments, close), how proposals are reviewed (`agent-proposals/{list,review-dialog}`), what `work-items` shows. Note `mobile-smoke.spec.ts` (responsive UI claim to verify). These are the interaction patterns a CoS would replace, reuse, or automate.

**Output of this phase:** `project-inspection.md` — per-area findings with citations; the verified interface inventory; the authn/authz/tenancy matrix; the money-safety picture (invariants, posting paths, idempotency); explicitly listed absences with search terms.

---

## 4. Integration-Layer Assessment Plan (CoS Lenses)

Assess each channel against the five CoS capabilities. For every (channel × capability) cell assign a readiness rating with evidence:

- **0 – Absent** (no surface found; cite the negative searches)
- **1 – Partial** (surface exists but not agent-consumable as-is: interactive-session-only auth, no machine identity, no contract doc)
- **2 – Ready** (documented contract, non-interactive authn, scoped access, test coverage)
- **3 – Extensible** (ready *and* designed for third-party/machine consumers: plugin registry, versioned contract, permission tiers, idempotency keys, consent flow)

| Channel \ Lens | Command (issue/authorize actions) | Delegation (hand off task, track status) | Orchestration (multi-step, idempotent, cancellable) | Monitoring (events, state changes, health) | Reporting (stats, audit, analytics) |
|---|---|---|---|---|---|
| REST + API keys (`transport/routes/*`, `modules/api-keys`, `openapi.json`) | | | | | |
| MCP (`modules/mcp`, `plugin-api/src/mcp.ts`, `platform-oauth-mcp.spec.ts`) | | | | | |
| Webhooks / events (inbound `processing-webhook`, outbound `change-feed`, `plugin-api/events.ts`) | | | | | |
| Plugin API (`plugin-api/*`: actor, permissions, posting, registry, routes) | | | | | |

**Concrete questions each cell must answer** (inspect code, not file names):
- **Command:** Can an external principal authenticate (API key? OAuth client? plugin actor? MCP identity from `0999_app_grants`?) and act — post journals, approve proposals, pay bills, close periods? What permission catalog entries apply (`modules/permissions/catalog.ts`)? Does the agent-proposals flow gate money-moving commands (human confirmation), and can a CoS operate within it (propose on behalf of a human) or only around it?
- **Delegation:** Is there a job/task abstraction an external caller can create and poll (automations jobs, pay-bills queue, work-items)? Idempotency keys per command (`transport/idempotency.ts`)? Status/cancellation surfaces? What does the proposal lifecycle expose (submitted → reviewed → applied/rejected)?
- **Orchestration:** Can multi-step financial workflows be composed externally (proposal + approval + posting + reconciliation)? What atomicity/transaction guarantees exist (`db/transaction-scope.ts`, posting service, period close)? What happens on partial failure mid-payment-rail? Are period-close immutability boundaries respected by any external write path?
- **Monitoring:** Is state change observable externally — `change-feed.ts` (what events, what delivery model, what auth)? `plugin-api/events.ts`? processor-events records? `health.ts`? provenance logging (`logging/provenance.ts`)? Is there an event catalog a CoS can subscribe to?
- **Reporting:** What can a CoS read without DB access — reports routes (aging, balance-sheet, trial-balance, cash-basis, audit), export adapters (csv/xlsx), `reports/audit.service`. Are audit trails complete for agent-initiated actions (who/what triggered each posting)?

**Output of this phase:** `integration-assessment.md` — the filled 4×5 readiness matrix with citations per cell, plus the top-5 findings that most affect CoS feasibility.

---

## 5. Gap / Risk / Dependency / Modification-Point Analysis Plan

**5.1 Gap register.** For each CoS lens, list what is missing for a CoS to command this finance agent through the integration layer — derived strictly from the Phase 4 matrix and the Phase 3 boundary matrix. Candidate gaps to confirm or refute (hypotheses from the pre-survey; do not assert as fact): machine-scoped principal type with permission catalog entries; externally creatable delegations (proposal/job submission via API with tracking); outbound event subscriptions with typed payloads and signed delivery; a documented CoS-facing command contract (OpenAPI completeness for all routes); MCP tool coverage vs the full REST surface; per-action audit trail linking postings to originating agent commands.

**5.2 Risk register.** For each gap and each reused surface: description, affected CoS lens, likelihood × impact, mitigation. Finance-specific risks to evaluate: double-entry/invariant violations via new write paths; duplicate posting under retries (idempotency coverage per route); payment-rail disbursement without human approval; period-close boundary breaches; cross-tenant leakage (org-scope gaps); webhook replay/signature weaknesses; MCP tool over-privilege vs permission catalog; audit-trail gaps for machine actions; secrets exposure (`secrets-store`, field encryption); SQS queue poisoning/starvation affecting financial SLAs.

**5.3 Dependency map.** Runtime: MySQL (migrations 0001–0999), SQS (messaging module), S3 (storage: `modules/…/storage/{local,s3}.ts`), SES (email delivery: invites, invoices, dunning), payment processors (payments-processing connections + `processing-webhook` + `poll.job`), bank feeds provider, Terraform-managed AWS (ECS/RDS/ALB/CloudFront/KMS). Build/deploy: Yarn 4 workspaces, codegen, docker-compose, GitHub Actions (`ci.yml.disabled` — why disabled is a finding). Mark which dependencies a CoS integration would add load to or require changes in.

**5.4 Modification points.** Rank candidate change sites by minimal-touch principle, each with: file/area, what would change, which CoS lens it serves, blast radius, additive vs invasive. Candidates to evaluate (verify before including): extend `modules/mcp/tools.ts` (new CoS tool namespace under existing host); extend `plugin-api` with a CoS actor type + permission entries; formalize `agent-proposals` as the external delegation envelope (submit/track via API); add outbound signed webhooks beside `change-feed`; complete `openapi.json` for machine clients; scoped API-key grants in `modules/api-keys` referencing the permission catalog. Explicitly separate **integration-only** (no repo change; CoS consumes existing surfaces) from **modification** (repo change) options.

**Output of this phase:** `gap-risk-dependency-analysis.md` — three registers + ranked modification points, each row cited or explicitly tagged `ASSUMPTION`/`OPEN`.

---

## 6. Step-by-Step Execution Methodology

Execute phases in order; each phase gates the next. Record everything in a worklog.

1. **Gate 0 — Environment & inputs.** Confirm repo location/branch (root `/enterprise_os/business-os/agents/finance`); obtain Agent Info and Recommended Architecture source texts; read agent-level `prompt.md`. If the two sources are missing, record `OPEN` and proceed with Phases 2–5 using Appendix A, marking source-dependent conclusions provisional.
2. **Phase 1 — Sources** (Section 1). Produce `source-comprehension.md`.
3. **Phase 2 — Mapping** (Section 2). Verify every Appendix A anchor against code. Produce `finance-architecture-mapping.md`.
4. **Phase 3 — Inspection** (Section 3). Bottom-up: self-description → topology → interfaces → boundaries/money-safety → orchestrators → UI. Produce `project-inspection.md`.
5. **Phase 4 — Integration assessment** (Section 4). Fill the matrix; for each cell open the actual code. Produce `integration-assessment.md`.
6. **Phase 5 — Analysis** (Section 5). Registers + modification points. Produce `gap-risk-dependency-analysis.md`.
7. **Phase 6 — Self-correction pass.** Re-audit the report: (a) every `FACT` has ≥1 citation; (b) every `ABSENT` lists negative-search terms; (c) every register row is cited or tagged; (d) run three adversarial refutation attempts against your strongest claims (e.g., alternate auth paths for machine principals, undocumented routes missing from openapi.json, event emitters outside change-feed); (e) verify the scope fence — no business-platform content.
8. **Phase 7 — Recommendations** (Section 8) and final report assembly.
9. **Throughout:** update the evidence ledger (`FACT`/`ASSUMPTION`/`OPEN`) and worklog after every ReAct cycle; never batch-write findings from memory at the end.

**Deliverables to produce:** `review-report.md` (executive summary, per-phase findings, matrix, registers, recommendations), the six per-phase artifacts, and `worklog.md` (cycle log: reason → action → evidence → refinement). Save all under a single `cos-finance-review/` directory. Do not modify anything inside the repo.

---

## 7. Measurable Acceptance Checks

The report passes only if every check is demonstrably true:

- [ ] **A1 — Sources reviewed & mapped:** Agent Info and Recommended Architecture element tables exist with verbatim quotes, or an `OPEN` flag explains how the review proceeded without them; finance-domain interpretation written for all 7 elements.
- [ ] **A2 — Inspection cited:** ≥25 distinct file paths cited across `project-inspection.md`; every interface-inventory row has a path; every claimed absence lists search terms used.
- [ ] **A3 — Integration layer assessed:** the 4×5 matrix is fully filled, every cell has a readiness rating + citation, and the five CoS capabilities (command, delegation, orchestration, monitoring, reporting) are each covered for all four channels (APIs, MCP, webhooks/events, plugin API/adapters).
- [ ] **A4 — Registers complete:** gap, risk (likelihood/impact/mitigation), and dependency registers each have ≥5 rows; modification points ≥5, ranked, each labeled additive vs invasive.
- [ ] **A5 — Money-safety verified:** the ledger-write path, idempotency coverage, and period-close boundaries are described from code (not doc names alone), with the eslint invariant rules' actual enforcement scope stated.
- [ ] **A6 — Methodology followed:** `worklog.md` shows ReAct cycles per phase and the Phase 6 self-correction pass results, including the three adversarial refutation attempts.
- [ ] **A7 — Ambiguities flagged:** a dedicated section lists every `OPEN` item with the question and what is needed to resolve it; `ASSUMPTION` items are listed with their validation condition.
- [ ] **A8 — No unsupported claims:** spot-check 10 random `FACT` claims — each resolves to a real file/line; zero fabricated endpoints or capabilities.
- [ ] **A9 — Scope fence holds:** no business-platform analysis; no project files modified (`git status` clean at the end, modulo untracked review-output directory outside the repo).

---

## 8. Goal-Oriented Next-Step Recommendations

Close the report with recommendations a decision-maker can act on, in this structure:

1. **Integration posture decision.** Recommend one primary posture, justified by evidence: (a) *consume-only* — CoS drives the finance agent through existing API keys/OAuth/MCP/agent-proposals with zero repo change; (b) *contract-first extension* — formalize a CoS command contract (new MCP tool namespace and/or OpenAPI-completed command routes) with a machine principal type and permission-catalog entries; (c) *deep integration* — shared job/event fabric across agents. State the evidence that drove the choice and what would change the decision.
2. **Sequenced roadmap.** 3–4 phases, each with: goal, concrete steps anchored to Section 5.4 modification points, the CoS lens unlocked, and a verification method (which tests/specs prove it — e.g., `platform-oauth-mcp.spec.ts`, `automations.spec.ts`, `pay-bills.spec.ts` as executable baselines). Order must respect dependencies (machine identity before command surface; command surface before delegation tracking; human-approval semantics before any money-moving autonomy).
3. **Risk burn-down.** Map top risks to roadmap phases (each phase retires ≥1 risk) and name the finance gates the CoS must pass: permission-catalog scoping, idempotent command execution, human-in-the-loop for disbursements, audit provenance for every agent-initiated posting.
4. **Open decisions for the requester.** Enumerate `OPEN` items that block design (CoS principal/identity model, proposal-approval ownership, event taxonomy ownership, out-of-band questions about `platform-and-ai` roadmap intent) with the specific input needed from the architecture owners.

Recommendations must stay inside the finance scope and must not redesign the CoS itself — the deliverable is how the finance agent receives and supports CoS command/orchestration, not the CoS's internals.

---

## Appendix A — Baseline Evidence (from requester's pre-survey of the file tree)

Verified `FACT`s from the uploaded tree dump of `/enterprise_os/business-os/agents/finance` (project dir `OpenBooks/`). Re-verify in code before relying on any anchor. Paths below are relative to `OpenBooks/`.

**Monorepo & topology.** Yarn 4 (`yarn.lock`, `.yarnrc.yml`); packages: `server` (backend), `web` (Vite React thin client), `shared-types`, `plugin-api` (extension SDK), `eslint-plugin` (domain invariant lint rules), `e2e` (Playwright, `playwright.config.ts`, `scripts/start-stack.mjs`). Entrypoints: `server/src/entrypoints/{api,worker,main,migrate-cli,migrate,spec}.ts`. Root: `openapi.json`, `docker-compose.yml` (MySQL via `docker/mysql-init/{01-users,02-grants}.sql`), `Dockerfile`, `CLAUDE.md`, `ROADMAP.md`, `SECURITY.md`, `NOTICE`, `LICENSE`, `eslint.config.js`, `vitest.config.ts`. Infra: `infra/nginx/openbooks-web.conf`, `infra/db-bootstrap/*` (RDS users/grants + parity check script), Terraform modules `compute` (ECS cluster/services/tasks/ECR/IAM), `data` (RDS + secrets), `edge` (ACM/ALB/CloudFront), `messaging` (S3/SES/SQS), `network`, KMS, state-backend. Agent-level files beside the project: `prompt.md`, `README.md`.

**Server (`server/src/`).** `config/` (config, env, providers, redact, role), `context/` (authentication, context, store), `crypto/field-encryption.ts`, `db/` (migrations `0001_tenancy` → `0026_logs`, `0999_app_grants`; `api-key-lookup.ts`, `oauth-lookup.ts`, `org-scope.ts`, `tenant.ts`, `tenant-tables.ts`, `transaction-scope.ts`, `delivery-lookup.ts`, `processor-connection-lookup.ts`, `secrets-store.ts`, `statement-credential-lookup.ts`, `migrator.ts`, `keyset.ts`, `mysql-errors.ts`), `errors/` (codes, wire, parse, assert), `logging/` (logger, provenance, redact, serialize, log-sink-stream), `modules/` (~50 modules): account-statements (renderer, public token), accounts (chart templates, hierarchy), **agents** (`review.service.ts`), api-keys, auth (api-key-identity, oauth-identity, tokens, cookie, password), **automations** (engine, job, queue.service, repository), bank-feeds (connections, feed-sync.job/service), banking, bills, branding, budgets, catalog, contacts, dimensions, drafts, **enforcement**, estimates, expenses, fixed-assets, **idempotency**, imports, inventory, invoices, invoicing, **ledger** (journal-read, posting, trial-balance services), log-retention, members (invites, tokens), **mcp** (`host.ts`, `tools.ts`), **oauth** (credentials, repository, service), orgs (inbound-email), **pay-bills** (queue, issue, rail-disbursements, check-output/register, vendor-details), payment-terms (compute-term, suggestion), payments, **payments-processing** (connections, payout-account-map/config/sync, poll.job, posting, processor-events.repository, summary-journal.builder, **webhook.service.ts**), periods (calendar, period-close), **permissions** (catalog, repository, service), predocument-delivery, purchase-orders, providers, recurring-journals (engine, job), **reports** (aging, audit, balance-sheet, cash-basis recognition, export adapters csv/xlsx/tabular), schema, settings, setup, tax, ten99, **transport** (routes: 47 files incl. `agent-proposals.ts`, `api-keys.ts`, `artifacts.ts`, `auth.ts`, `automations.ts`, `bank-*`, `bill-*`, `budgets.ts`, `catalog.ts`, `change-feed.ts`, `chart-templates.ts`, `contacts.ts`, `customer-statements.ts`, `dimensions.ts`, `drafts.ts`, `dunning.ts`, `estimates.ts`, `expenses.ts`, `external-refs.ts`, `fixed-assets.ts`, `imports.ts`, `inventory.ts`, `invoices.ts`, `journal-lines.ts`, `journals.ts`, `members.ts`, `oauth-clients.ts`, `oauth-flow.ts`, `orgs.ts`, `pay-bills.ts`, `payment-terms.ts`, `payments.ts`, `periods.ts`, `predocument-delivery.ts`, `processing-webhook.ts`, `processing.ts`, `public-invoices.ts`, `public-pay-link.ts`, `public-statements.ts`, `purchase-orders.ts`, `reconciliation.ts`, `recurring-invoices.ts`, `recurring-journals.ts`, `report-export.ts`, `reports.ts`, `roles.ts`, `scheduling.ts`, `settings.ts`, `statement-lines.ts`, `statement-packages.ts`, `support.ts`, `tax-rates.ts`, `ten99.ts`; app.ts, context.ts, cors.ts, errors.ts, health.ts, **idempotency.ts**, openapi.ts).

**Plugin API (`plugin-api/src/`).** `actor.ts`, `context.ts`, `events.ts`, `mcp.ts`, `migrations.ts`, `module.ts`, `permissions.ts`, `posting.ts`, `primitives.ts`, `providers.ts`, `registry.ts`, `routes.ts` + README + LICENSE (third-party extension SDK with permission model, posting primitive, MCP surface, event surface).

**Web (`web/src/`).** `api/` (client, errors, idempotency, presentation, schema.d.ts), `auth/` (create-org, org-selection, switch-org, identity), `components/` (money-input, responsive-table, combobox…), `screens/` (accounts, **agent-proposals** (list, review-dialog, queries), **api-keys** (create-dialog), **automations** (action-editor, state), budgets, work-items (list, queries), ten99 center, statement-packages, periods, + top-level screens: auth, oauth-clients, oauth-consent, pay-bills, processing, journals, journal-entry, reports, roles, settings, disbursements, dunning, connected-apps, public-invoice…), `shell/` (app-shell, nav, org-switcher, query-scope), `money/format.ts`, `lib/thin-client.ts`. `scripts/check-client-drift.mjs` (client drift guard).

**E2E (`e2e/tests/`).** 18 Playwright specs: accountant-and-close, automations, bank-feeds, banking, bill-capture, budgets, cash-application, cash-basis, fixed-assets-and-recurring-journals, mobile-smoke, month-of-books, pay-bills, payment-integration, payout-sync, **platform-oauth-mcp**, procure-to-pay, quickbooks-import, recurring-and-dunning; support helpers (banking, books, cash-application, pay-bills, payments).

**ESLint invariants (`eslint-plugin/src/rules/`).** `no-float-money.js`, `no-journal-writes.js`, `no-process-env.js`, `no-raw-color.js` (with tests) — machine-enforced domain invariants; enforcement scope via root `eslint.config.js` must be verified.

**Docs.** `docs/architecture/{overview,api-and-transport,data-and-tenancy,ledger-kernel,money-and-invariants,providers-and-config,security}.md`; `docs/features/{foundation,frontend,banking-and-cash,payments-processing,purchases-ap,sales-ar,reporting-and-tax,platform-and-ai}.md`; `docs/decisions/{adr-template,index}.md`; `docs/guides/{adding-a-feature,database-and-migrations,deployment,development,get-started,hosted-infra,testing}.md`; `docs/{README,ci,glossary}.md`.

**Verified absences in the tree dump (searched: filenames + content markers).** No `chief`, no `of-staff`/`of staff`, no `orchestrat*` files. The only agent-native code is `modules/agents/review.service.ts` + `agent-proposals` route/UI + `work-items` screens. No CoS-facing API, no externally documented event-subscription surface beyond `change-feed.ts`, no dedicated event catalog is visible at tree level. Absence at tree level is not absence at code level — Phases 3/4 must re-verify inside files.

**Environment note from pre-survey.** The requester's sandbox did not contain the checked-out repo (only this tree dump). Conclusions in this prompt are tree-level evidence; code-level verification is mandatory in Phases 2–4.
