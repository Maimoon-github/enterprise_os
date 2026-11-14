# Phase 2: Finance-Context Architecture Mapping

**Review Target:** Finance Agent (`business-os/agents/finance`)  
**Project Base:** `OpenBooks/` monorepo  
**Status Evidence Legend:**  
- `EXISTS`: Code anchor verified in source tree with full implementation.  
- `PARTIAL`: Code surface exists but has limitations, incomplete coverage, or requires adaptation for autonomous agent consumption.  
- `ABSENT`: No code implementation found in the repository (negative searches documented).

---

## 1. Architecture Mapping Table

| # | Architecture Element | Finance-Domain Counterpart | Code Anchors in Repo | Status | Verification & Code Citations |
|---|---|---|---|---|---|
| **1** | **Chief of Staff (CoS) Agent** | External supervisor / command issuer. OpenBooks has **zero CoS implementation**; it provides the receptacle (API keys, OAuth AS, MCP host) that an external CoS plugs into. | Receptacles: `server/src/modules/auth/oauth-identity.ts`, `server/src/modules/auth/api-key-identity.ts`, `server/src/modules/mcp/host.ts`, `server/src/modules/automations/queue.service.ts` | **ABSENT** *(Internal CoS)* / **EXISTS** *(Integration Receptacle)* | Negative grep across codebase for CoS internal code: `grep -ri "chief_of_staff" .` (0 hits), `grep -ri "chief-of-staff" .` (only in parent README), `grep -rn "orchestrator" .` (only in comments). Receptacle verified: `server/src/entrypoints/api.ts#L91-L97` (OAuth, API-key, and session identity composition). |
| **2** | **Independent Specialized Agents** | Complete double-entry accounting engine (`OpenBooks`) with agent-proposals review loop and agent work queue. | `server/src/modules/agents/review.service.ts`, `server/src/transport/routes/agent-proposals.ts`, `web/src/screens/agent-proposals/*`, `server/src/modules/automations/queue.service.ts` | **EXISTS** | `server/src/modules/agents/review.service.ts#L48-L89` (`listProposals`, `approveProposal`, `rejectProposal`); `server/src/transport/routes/agent-proposals.ts#L61-L151` (`GET /v1/agent-proposals`, `POST /v1/agent-proposals/:draftId/approve`, `POST /v1/agent-proposals/:draftId/reject`); `server/src/modules/automations/queue.service.ts#L67-L305` (`pollWorkQueue`, `submitWorkItemProposal`). |
| **3** | **Internal Orchestrators** | Background worker, queue providers (in-process/SQS), scheduled daily tick sweeps, Pay Bills disbursement pipeline, recurring sweeps, and bank feed sync. | `server/src/entrypoints/worker.ts`, `server/src/modules/scheduling/*` (`startDailyTick`, `runAsAutomation`), `server/src/modules/automations/*` (`engine.ts`, `job.ts`, `queue.service.ts`), `server/src/modules/pay-bills/*` (`queue.service.ts`, `issue.service.ts`), `server/src/modules/invoicing/*` (`recurring.ts`, `dunning.ts`), `server/src/modules/banking/*` (`statement-import.job.ts`) | **EXISTS** | `server/src/entrypoints/worker.ts#L50-L140` (registers statement import, recurring, dunning, recurring journals, fixed assets, document extraction, processor poll, bank feeds, and automations jobs); `server/src/modules/scheduling/tick.ts#L25-L65` (`startDailyTick`); `server/src/modules/automations/engine.ts#L31-L75` (`executeAutomation`). |
| **4** | **Individual UI per Agent** | Standalone Vite + React single-page application with full financial screens, review dialogs, and reporting views. | `packages/web/src/screens/*` (40 screen modules including `accounts`, `agent-proposals`, `automations`, `budgets`, `journals`, `pay-bills`, `processing`, `reports`, `roles`, `work-items`), `packages/web/src/shell/*` (`app-shell.tsx`, `nav.ts`, `org-switcher.tsx`) | **EXISTS** | `packages/web/src/screens/agent-proposals/review-dialog.tsx#L39-L181` (Approve & Post / Reject proposal dialog); `packages/web/src/screens/automations/automations.tsx#L1-L120` (builder UI); `packages/web/src/screens/work-items/work-items.tsx#L1-L150`; `packages/web/src/shell/nav.ts#L1-L180`. |
| **5** | **Integration Layer (APIs, MCP, Webhooks, Adapters)** | Multi-channel integration layer: 48 REST route files, in-process MCP server (8 tools), transactional change feed, inbound payment/bill webhooks, swappable provider adapters. | REST: `server/src/transport/routes/*` (48 files); MCP: `server/src/modules/mcp/{host.ts,tools.ts}`; Events: `server/src/transport/routes/change-feed.ts`, `server/src/modules/events/outbox.ts`; Webhooks: `server/src/transport/routes/processing-webhook.ts`; Plugin SDK: `packages/plugin-api/src/*` | **PARTIAL** | REST and MCP are **Ready/Extensible** (`server/src/modules/mcp/tools.ts#L312-L321`). However, Webhooks are **Inbound-Only** (`processing-webhook.ts#L1-L60`, `bill-inbound.ts#L1-L50`); outbound event publishing to external systems (e.g. Redis, webhooks) is **ABSENT** (only pull-based `GET /v1/change-feed` exists: `server/src/transport/routes/change-feed.ts#L23-L41`). |
| **6** | **Shared Intelligence** | Authoritative financial source of truth: ledger kernel, trial balance calculation, balance sheet, P&L, aging reports, audit trail, and export adapters (CSV, XLSX). | `server/src/modules/ledger/{posting.service.ts,trial-balance.service.ts,posting.repository.ts}`, `server/src/modules/reports/{aging.service.ts,balance-sheet.service.ts,profit-and-loss.service.ts,audit.service.ts,export/adapters.ts}` | **PARTIAL** | Core double-entry ledger and comprehensive analytical reports **EXIST** (`server/src/modules/ledger/posting.service.ts#L115-L153`; `server/src/modules/reports/audit.service.ts#L34-L60`). However, direct integration with central semantic/vector stores (PostgreSQL + Qdrant RAG) is **ABSENT** (negative grep for `qdrant`: 0 hits; negative grep for `pgvector`: 0 hits). OpenBooks serves as the upstream authoritative truth. |
| **7** | **Controlled Data Access** | Hardened multi-tenant isolation, database-level append-only grants (`0999_app_grants`), ESLint AST rule enforcement, 78-key permission catalog, AES-256-GCM encryption, mandatory idempotency keys. | Tenancy: `server/src/db/{tenant.ts,org-scope.ts,tenant-tables.ts}`; Grants: `server/src/db/migrations/0999_app_grants.ts`; ESLint: `packages/eslint-plugin/src/rules/no-journal-writes.js`; Permissions: `server/src/modules/permissions/{catalog.ts,permissions.service.ts}`; Crypto: `server/src/crypto/field-encryption.ts`; Idempotency: `server/src/transport/idempotency.ts` | **EXISTS** | Immutability: `0999_app_grants.ts#L17-L22` (no UPDATE/DELETE on journals); `packages/eslint-plugin/src/rules/no-journal-writes.js#L18-L76` (AST check); Permissions: `server/src/modules/permissions/catalog.ts#L36-L171` (78 pinned codes); Idempotency: `server/src/transport/idempotency.ts#L58-L80` (`Idempotency-Key` required on every write). |

---

## 2. Narrative Assessments per Architectural Element

### 2.1 Chief of Staff Agent (`ABSENT` in Repo / `EXISTS` as Integration Receptacle)
There is no Chief of Staff agent implementation inside OpenBooks. Thorough codebase searches confirmed zero internal orchestration of external agents (`grep -rn "chief_of_staff" .` produced 0 hits; `grep -ri "of-staff" .` produced 0 hits in `packages/`). However, OpenBooks provides a sophisticated **integration receptacle**: external agents can authenticate via OAuth 2.1 PKCE bearer tokens (`oba_...`) or org-scoped API keys (`obk_...`) and interact through the Fastify REST API (`/v1/*`) or the in-process JSON-RPC 2.0 MCP server (`POST /mcp`). Under Initiative Q (OB-200…210), OpenBooks specifically anticipates external autonomous agents connecting over MCP to poll leased work items (`work_queue.poll`) and submit structured proposals (`work_queue.submit_proposal`).

### 2.2 Independent Specialized Agents (`EXISTS`)
OpenBooks fully realizes the independent specialized agent boundary. It encapsulates complete financial domain logic: double-entry bookkeeping, AR/AP lifecycles, cash application, bank reconciliation, tax reporting, and asset depreciation. Critically, OpenBooks incorporates an **agent-native interaction model**:
1. `modules/agents/review.service.ts` manages pending journal proposals produced by autonomous models.
2. An external agent submits proposals via MCP (`journal.propose` or `work_queue.submit_proposal`), which land as mutable drafts in `journal_drafts`.
3. An authorized human holding `agents.review` and `journals.post` inspects the lines in the UI and clicks "Approve and post", which atomically executes `postDraft` into the append-only ledger (`server/src/modules/agents/review.service.ts#L70-L76`).

### 2.3 Internal Orchestrators (`EXISTS`)
OpenBooks implements a multi-tier internal orchestration engine rather than relying on external workflow runners:
- **Worker Process:** The `worker` role (`entrypoints/worker.ts#L50-L80`) consumes background queues and processes statement parsing, OCR bill extraction, bank feed sync, and automated journal sweeps.
- **Queue Seam:** A pluggable `queueProvider()` supporting `in-process` for local single-container deployments and AWS `sqs` for distributed production (`server/src/providers/queue/sqs.ts`).
- **Scheduling Runtime:** `modules/scheduling/tick.ts` executes daily tick fan-outs (`startDailyTick`), while `automation.ts` provides `runAsAutomation` to execute jobs with an automation actor context.
- **Automation Engine:** `modules/automations/engine.ts` sequences actions (`annotate`, `agent_task`) for event-driven or scheduled automations.
- **Pay Bills Orchestrator:** `modules/pay-bills/issue.service.ts` batches payable releases across disbursement rails with per-payment atomicity.

### 2.4 Individual UI (`EXISTS`)
The frontend is a dedicated, production-grade Vite + React SPA (`packages/web`) comprising 40 distinct screen modules. It maintains complete human-in-the-loop operational surfaces:
- Interactive Chart of Accounts and Journal Entry editors.
- Dedicated Agent Proposals review queue (`screens/agent-proposals/`) featuring line-by-line inspection and single-click approval/rejection.
- Work Items oversight screen (`screens/work-items/`) tracking queued, leased, and proposed agent tasks.
- Dedicated screens for Automations builder, Role builder, Bank reconciliation, Pay Bills, and Connected OAuth Apps.
- Responsive mobile layout validated via Playwright in `packages/e2e/tests/mobile-smoke.spec.ts` at 390px viewport.

### 2.5 Integration Layer (`PARTIAL`)
The integration layer is well-structured for REST and MCP, but incomplete for event-driven push:
- **REST & OpenAPI:** 48 route modules in `server/src/transport/routes/` with schema-driven validation (Zod v4) and byte-stable OpenAPI 3.1 generation (`packages/server/src/transport/openapi.ts`). Every write endpoint mandates an `Idempotency-Key` header (`server/src/transport/idempotency.ts`).
- **MCP Server:** Fastify route `POST /mcp` hosts an in-process JSON-RPC 2.0 server without third-party SDK dependencies (`server/src/modules/mcp/host.ts`). It exposes 8 typed tools with strict permission checks (`server/src/modules/mcp/tools.ts#L312-L321`).
- **Gaps:** Webhook capabilities are exclusively **inbound** (`processing-webhook.ts` and `bill-inbound.ts`). Outbound notification relies on clients polling `GET /v1/change-feed` (`server/src/transport/routes/change-feed.ts`). There is no outbound webhook dispatcher and no native Redis event publishing mechanism.

### 2.6 Shared Intelligence (`PARTIAL`)
OpenBooks serves as an authoritative financial source of truth rather than a consumer of external embeddings. It provides deterministic, audit-grade financial data:
- **Ledger Kernel:** The immutable double-entry ledger (`modules/ledger/posting.service.ts`), where debits equal credits in exact integer cents (`bigint`).
- **Reporting Engine:** Real-time calculation of Trial Balance, Balance Sheet, P&L, AR/AP Aging, and Cash Flow Projections (`modules/reports/*`), exportable to CSV/XLSX.
- **Audit Provenance:** `modules/reports/audit.service.ts` surfaces actor provenance across all posted journals.
- **Gaps:** OpenBooks has no direct knowledge layer integration (zero references to PostgreSQL vector extensions or Qdrant). Sharing business intelligence with CoS must occur through CoS querying OpenBooks reporting APIs or change feeds.

### 2.7 Controlled Data Access (`EXISTS`)
Data access control is exceptionally rigorous, with defenses implemented across three independent layers:
1. **Database Grant Boundary:** `0999_app_grants.ts` configures MySQL users such that `openbooks_app` holds only `SELECT, INSERT` on `journals` and `journal_lines`, preventing `UPDATE` and `DELETE` at the database engine level.
2. **Static Code Analysis (AST):** ESLint rule `openbooks/no-journal-writes` fails the build if any file outside `posting.repository.ts`, migrations, or test factories attempts to write to journal tables.
3. **Application & Tenancy Logic:** `tenantDb(orgId)` enforces composite-key tenancy `(org_id, id)`. `requirePermission` enforces access against a pinned 78-key catalog (`catalog.ts#L205`). Fiscal period locks (`assertPostable`) prevent postings into closed calendar periods. `field-encryption.ts` encrypts sensitive PII at rest using AES-256-GCM.

