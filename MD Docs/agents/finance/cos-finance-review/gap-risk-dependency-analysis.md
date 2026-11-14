# Phase 5: Gap, Risk, Dependency & Modification-Point Analysis

**Review Target:** Finance Agent (`business-os/agents/finance`)  
**Project Base:** `OpenBooks/` monorepo  
**Evaluation Perspective:** Chief of Staff (CoS) Integration Feasibility & Finance Domain Correctness

---

## 1. Gap Register

Gaps preventing an external Chief of Staff agent from commanding, delegating, orchestrating, monitoring, and reporting on the Finance Agent through the integration layer:

| Gap ID | CoS Lens Affected | Description of Gap | Existing Code / Evidence Anchor | Impact on CoS Integration |
|---|---|---|---|---|
| **GAP-01** | **Command / Identity** | **Absence of Dedicated Machine `'agent'` Identity in Auth Resolvers.** While `@openbooks/plugin-api/src/actor.ts` recognizes `actorType = 'agent'`, the API-key resolver assigns `actorType = 'automation'` with `userId = null` (`server/src/modules/auth/api-key-identity.ts#L76`), and OAuth resolves to `'user'`. | `packages/server/src/modules/auth/api-key-identity.ts#L72-L78`<br>`packages/server/src/modules/auth/oauth-identity.ts#L84-L90` | CoS machine actions cannot be formally distinguished from automated background crons in the audit log; journals lack true autonomous agent provenance. |
| **GAP-02** | **Command / Posting** | **MCP Write Tools are Propose-Only (No Autonomous Posting Seam).** `journal.propose` refuses `mode: "execute"` outright (`modules/mcp/tools.ts#L195-L208`, Decision D-60). Proposals must land in `journal_drafts` and await human approval in `agents.review`. | `packages/server/src/modules/mcp/tools.ts#L175-L214`<br>`packages/server/src/modules/agents/review.service.ts#L10-L46` | CoS cannot autonomously post entries to the ledger via MCP even for trivial, pre-approved adjustments; every proposal forces human UI interaction. |
| **GAP-03** | **Monitoring** | **Absence of Outbound Webhook or Event Bus Push.** OpenBooks only supports pull-based consumption of its transactional outbox via `GET /v1/change-feed` (`routes/change-feed.ts#L23-L41`). There is no outbound HTTP webhook dispatcher and no Redis/message-broker publishing seam. | `packages/server/src/transport/routes/change-feed.ts#L1-L41`<br>`packages/server/src/modules/events/outbox.ts#L61-L80` | CoS cannot react asynchronously to financial events (e.g. invoice paid, payment failed, low bank balance); CoS must maintain a continuous polling loop. |
| **GAP-04** | **Delegation** | **No Direct External REST Route to Submit Proposals.** Proposals can only be submitted via MCP (`journal.propose` or `work_queue.submit_proposal`). There is no `POST /v1/agent-proposals` endpoint in REST (`transport/routes/agent-proposals.ts#L27-L35`). | `packages/server/src/transport/routes/agent-proposals.ts#L27-L35` | An external orchestrator calling REST APIs cannot submit an agent proposal without speaking JSON-RPC 2.0 over MCP. |
| **GAP-05** | **Shared Intelligence** | **No Direct Semantic Knowledge / Vector Store Sync Seam.** OpenBooks exposes relational data and tabular reports, but has no built-in embedding generation or sync pipeline to external PostgreSQL + Qdrant shared stores. | Negative search in repo: `qdrant` (0 hits), `pgvector` (0 hits). | CoS must build an external ETL ingestion pipeline to extract financial metrics, CoA definitions, and customer aging into enterprise RAG. |
| **GAP-06** | **Orchestration** | **Limited MCP Tool Suite Coverage.** MCP exposes only 8 tools (`accounts.list`, `contacts.list`, `reports.trial_balance`, `invoices.list`, `bills.list`, `journal.propose`, `work_queue.poll`, `work_queue.submit_proposal`). Operations like issuing payments, voiding bills, closing periods, or running dunning are missing from MCP. | `packages/server/src/modules/mcp/tools.ts#L312-L321` | Complex financial workflows require CoS to switch between MCP (for drafting) and REST (for operational actions). |
| **GAP-07** | **Monitoring** | **Gaps in Domain Event Emission to Outbox.** As proven by `packages/e2e/tests/platform-oauth-mcp.spec.ts#L59-L70`, raw journal postings made via `postJournal` or `approveProposal` emit **no change-feed event**. `emitEvent` is called only from subledger services (`payments`, `ar-documents`, `bills`, `reconciliation`). | `packages/e2e/tests/platform-oauth-mcp.spec.ts#L61-L70`<br>`packages/server/src/modules/ledger/posting.service.ts#L115-L153` | Postings approved through the agent review queue do not appear on `GET /v1/change-feed`, blinding CoS to journal approval completion without explicit polling of drafts. |

---

## 2. Risk Register

Evaluation of finance-specific risks arising from integrating CoS with OpenBooks:

| Risk ID | Risk Description | Affected CoS Lens | Likelihood | Impact | Inherent Severity | Mitigation Strategy |
|---|---|---|---|---|---|---|
| **RSK-01** | **Unauthorized Fund Disbursement via Leaked API Key.** If an API key issued to CoS is granted `disbursements.issue`, a compromised CoS prompt or leaked credential could release batch payments via payment rails without human executive review. | Command / Orchestration | Medium | Critical | **HIGH** | Enforce Separation of Duties (Decision D-109): grant CoS only `pending_payments.write` (can prepare queues); withhold `disbursements.issue` so payment release requires human approval in `screens/pay-bills`. |
| **RSK-02** | **Duplicate Posting or Disbursement Under Network Retries.** Network timeouts between CoS and OpenBooks during payment execution could cause CoS to re-issue payments, leading to double vendor payments or duplicate ledger postings. | Command / Orchestration | High | High | **HIGH** | Mandatory `Idempotency-Key` headers on all write calls (`server/src/transport/idempotency.ts#L58-L80`). Two-level idempotency in `issuePendingPayment` (`external_refs` + connection locks) ensures retried requests replay cached results safely. |
| **RSK-03** | **Posting Against Closed Accounting Periods.** Automated journal proposals executed near month-end might attempt to post into an already-closed fiscal period, potentially corrupting historical statements. | Command / Orchestration | Low | Critical | **MEDIUM** | Invariant enforced in ledger kernel: `assertPostable` takes an exclusive row lock (`FOR UPDATE`) on `periods` (`modules/ledger/posting.service.ts#L131`). Any posting against a closed period fails fast with `PreconditionFailedError`. |
| **RSK-04** | **Double-Entry Balance or Floating-Point Corruption.** External LLM generating debit/credit amounts could produce imbalanced journals or introduce decimal floating-point rounding errors. | Command / Ledger Integrity | High | Critical | **HIGH** | Enforced by design: (1) Minor-unit `bigint` types end-to-end; strings rejected if not exact minor units (`CLAUDE.md#L116`). (2) `posting.service.ts#L361-L373` strictly enforces $$\sum \text{Debits} == \sum \text{Credits}$$. (3) AST rule `openbooks/no-float-money`. |
| **RSK-05** | **Cross-Tenant Data Leakage via Ambiguous Scoping.** In multi-entity operations, an un-scoped CoS query could expose financial records of one organization to another. | Controlled Data Access | Low | Critical | **HIGH** | Queries enforced via `tenantDb(orgId)` with composite keys `(org_id, id)`. Dependency Cruiser rule `tenant-tables-scoped-through-tenant-db` blocks unscoped queries at build time. Cross-tenant reads return 404 (`CLAUDE.md#L132`). |
| **RSK-06** | **Silent Blind Spot from Missing Outbox Events.** CoS assumes an approved journal generates an event on the change feed, waits indefinitely for completion, and stalls cross-agent orchestration loops. | Monitoring / Orchestration | High | Medium | **MEDIUM** | CoS must explicitly correlate journal approval by listening to draft resolution or polling `external_refs` rather than relying solely on `change-feed` for raw manual journals (`platform-oauth-mcp.spec.ts#L61-L75`). |
| **RSK-07** | **SQS Queue Poisoning / Starvation on Worker.** Ill-formatted asynchronous jobs enqueued by CoS could crash worker consumers or block financial background sweeps (e.g. daily dunning or recurring journals). | Internal Orchestration | Low | High | **MEDIUM** | Strict Zod input validation on queue payloads; dedicated SQS dead-letter queues (`DLQ`) configured in Terraform (`infra/terraform/modules/messaging/sqs.tf#L1-L60`); daily cron ticks partitioned by task. |
| **RSK-08** | **Audit Trail Provenance Dilution.** When CoS executes actions via API keys, actions are recorded under `actorType: 'automation'` with `actorId` set to the API key UUID, obscuring the specific agent prompt or context that triggered the write. | Reporting / Audit | Medium | Medium | **MEDIUM** | Require CoS to populate `memo` and `external_refs` on all entity creations; pass detailed context envelopes when creating work items (`modules/automations/engine.ts#L44-L49`). |

---

## 3. Dependency Map

Runtime, operational, and development dependencies analyzed for CoS integration impact:

| Dependency Component | Current Architecture / Code Location | Role in Finance System | Impact of CoS Integration (Load / Modifications) |
|---|---|---|---|
| **MySQL 8.4 (RDS / Local)** | `server/src/db/*`, `0001_tenancy` → `0999_app_grants`, `docker-compose.yml` | Authoritative persistence: double-entry ledger, outbox, tenant isolation, idempotency claims. | **Increased Read/Write Load**: CoS polling of change feed and frequent work item queries will increase connection pool pressure. Recommend read-replica for reporting. |
| **AWS SQS / In-Process Queue** | `server/src/providers/queue/{in-process,sqs}.ts`, `infra/terraform/modules/messaging/sqs.tf` | Asynchronous task execution for statements, OCR, sweeps, and automations. | **Increased Message Volume**: CoS-triggered automation runs will increase queue depth; requires monitoring DLQ alarms. |
| **Fastify API Server** | `server/src/entrypoints/api.ts`, `server/src/transport/*` | Hosts REST routes (`/v1/*`), OpenAPI 3.1 swagger, and MCP JSON-RPC host (`POST /mcp`). | **Primary Interface**: Direct target of all CoS commands, MCP tool calls, and polling requests. |
| **Worker Process** | `server/src/entrypoints/worker.ts` | Executes background cron ticks, reconciliation, and automations. | **Shared Capacity**: CoS delegating heavy workloads must not starve daily dunning or bank feed sweeps. |
| **OAuth 2.1 AS & API Keys** | `server/src/modules/auth/*`, `server/src/modules/oauth/*`, `server/src/modules/api-keys/*` | Authenticates external clients, evaluates roles, and applies live scope narrowing. | **Critical Path**: CoS authentication credentials originate here; key management must be provisioned during setup. |
| **Payment Processors (Stripe/Square)** | `server/src/modules/payments-processing/*`, `providers/payment/*` | External payment settlement, clearing, and webhook ingestion. | **Indirect Load**: CoS orchestrating receivables/payables will trigger payouts and settlements on processors. |
| **Yarn 4 / Build Tooling** | `.yarnrc.yml`, `package.json`, `scripts/build-server.mjs`, `entrypoints/spec.ts` | Workspace management, type-checking, ESLint invariant checks, OpenAPI drift verification. | **CI/CD Impact**: Any schema or route modifications for CoS must pass `yarn drift` and ESLint checks. Note: `ci.yml.disabled` requires manual gate execution. |

---

## 4. Ranked Modification Points

Candidate change sites evaluated according to the **minimal-touch principle** (ranked from lowest blast radius to highest):

| Rank | File / Area | Proposed Change | CoS Lens Unlocked | Blast Radius | Change Nature |
|---|---|---|---|---|---|
| **1** | **`packages/server/src/modules/mcp/tools.ts`** | **Expand MCP Tool Suite for Reporting & Operations.** Add read tools for `reports.aging`, `reports.balance_sheet`, `reports.profit_and_loss`, and operational tool `scheduling.run_due_work`. | Reporting & Monitoring | **Minimal** (Confined to `mcp/tools.ts`; reuses existing, tested domain services with zero database schema impact). | **Additive** |
| **2** | **`packages/server/src/transport/routes/agent-proposals.ts`** | **Expose External Proposal Submission via REST.** Add `POST /v1/agent-proposals` route allowing CoS to submit a journal proposal directly over REST with an `Idempotency-Key` (mirroring `journal.propose`). | Delegation | **Low** (Adds one route in `agent-proposals.ts`; calls existing `createDraft` service; updates `openapi.json`). | **Additive** |
| **3** | **`packages/server/src/modules/auth/api-key-identity.ts`** | **Support Dedicated `'agent'` Principal Type.** Allow an API key to declare `actor_type = 'agent'` with an agent identifier string, setting `ResolvedIdentity.actorType = 'agent'`. | Command & Audit | **Low-Medium** (Modifies `api-key-identity.ts` and `api_keys` table; enables true agent provenance in `journals.actor_type`). | **Additive** |
| **4** | **`packages/server/src/modules/ledger/posting.service.ts`** | **Emit Outbox Events for Manual & Approved Journals.** Add `emitEvent(ctx, { name: 'journal.posted', ... })` inside `postJournal` transaction. | Monitoring | **Medium** (Closes the change-feed blind spot; increases `event_log` row generation for all manual/approved postings). | **Additive** |
| **5** | **`packages/server/src/modules/events/` & `providers/`** | **Add Outbound Webhook Dispatcher / Redis Publisher.** Implement an outbound event delivery seam that dispatches committed `event_log` entries to CoS via HTTP POST or Redis pub/sub. | Monitoring & Orchestration | **High** (Adds a new outbound dispatcher worker, retry queue, HMAC signing mechanism, and webhook subscriptions table). | **Invasive / Architectural** |

---

## 5. Architectural Separation: Integration-Only vs. Modification Options

### Option A: Integration-Only (Zero Code Changes in `OpenBooks/`)
- **Posture:** CoS integrates strictly as an external client using existing surfaces.
- **Implementation:**
  1. Provision an API key (`obk_...`) via `screens/api-keys` assigned to a custom role holding necessary permissions (`reports.read`, `invoices.read`, `pending_payments.write`, `workflows.activate`).
  2. CoS commands operations via REST (`/v1/*`) with mandatory `Idempotency-Key` headers.
  3. CoS polls and leases agent work items over MCP (`POST /mcp` calling `work_queue.poll`) and submits proposals via `work_queue.submit_proposal`.
  4. Human operators approve proposals in `screens/agent-proposals` and release payments in `screens/pay-bills`.
  5. CoS monitors state changes by periodically polling `GET /v1/change-feed` with persistent cursors.
- **Trade-offs:** 100% compliant with zero-touch boundary; preserves all human-in-the-loop safety guarantees; requires CoS to maintain polling loops and speak both REST and JSON-RPC.

### Option B: Contract-First Extension (Controlled, Additive In-Repo Modifications)
- **Posture:** Implement minimal, additive enhancements in OpenBooks to streamline machine interaction.
- **Implementation:**
  1. Implement **Modification Point 1**: Add P&L, Balance Sheet, and Aging read tools to `modules/mcp/tools.ts`.
  2. Implement **Modification Point 2**: Add `POST /v1/agent-proposals` to REST route table.
  3. Implement **Modification Point 4**: Emit `journal.posted` events in `posting.service.ts` to ensure change-feed completeness.
- **Trade-offs:** Requires running `yarn codegen`, `yarn spec`, and `yarn check` to prevent drift; preserves double-entry invariants and MySQL grant immutability; significantly reduces CoS integration friction.

