# Phase 3: Current-Project Inspection Plan

**Review Target:** Finance Agent (`business-os/agents/finance`)  
**Project Base:** `OpenBooks/` monorepo  
**Inspection Date:** 2026-11-14  
**Methodology:** ReAct (Reason, Act, Observe, Refine) grounded in verified source-code citations.

---

## 1. Self-Description and Architectural Documentation

### 1.1 Repository-Level Declarations
- **Agent Root README** (`business-os/agents/finance/README.md#L1-L5`): Declares the finance agent as an "Independent environment for the finance business agent. Exposes capabilities only via API / MCP / webhook / adapter. Orchestrated exclusively by `chief-of-staff/`."
- **Root `prompt.md` Status** (`business-os/agents/finance/prompt.md`): **ABSENT** (`FACT`). Search executed: `ls business-os/agents/finance/prompt.md` returned `No such file or directory`. The agent-level boundary is defined entirely by `README.md` and `OpenBooks/` internal documentation.
- **Working Notes & Non-Negotiables** (`OpenBooks/CLAUDE.md#L96-L144`): Defines non-negotiable architectural invariants:
  - Journals are append-only at MySQL grant level (`CLAUDE.md#L101-L107`).
  - Two database users: `openbooks_migrator` (DDL + grant option) and `openbooks_app` (DML without `UPDATE`/`DELETE` on journals, `CLAUDE.md#L109-L115`).
  - Money is `bigint` minor units end-to-end; wire format is cents-string (`"150000"`), never float or JSON number (`CLAUDE.md#L116-L120`).
  - Tenant tables are reachable only via `tenantDb(orgId)` (`CLAUDE.md#L121-L126`).
  - Transactions propagate ambiently via AsyncLocalStorage (`CLAUDE.md#L127-L131`).
  - Cross-tenant requests return 404, never 403 (`CLAUDE.md#L132-L136`).
  - Only `posting.repository.ts` may write journal tables (`CLAUDE.md#L137-L140`).
  - Transport holds no business logic (`CLAUDE.md#L141-L143`).
- **Roadmap & Gate State** (`OpenBooks/ROADMAP.md#L89-L100`):
  - Current milestone progress: M1 (Skeleton), M2 (Books), M3 (AR/AP), M4 (Banking), M5 (Platform), PB (Pay Bills), CA (Cash App), PAY (Payments), L (Fixed Assets), M (P2P), N (Budgets), P (Accountant & Close), Q (Automations / Work Queue), FEEDS (Bank Feeds), and ROLES (Role Builder) are **BUILT**.
  - Test suite baseline: **2,859 automated tests across 280 files** (`yarn check` passing).
  - CI status: `.github/workflows/ci.yml` is renamed to `ci.yml.disabled` (`ROADMAP.md#L98`), indicating that all verification is currently executed locally via `yarn check`.
- **Platform & AI Architecture** (`OpenBooks/docs/features/platform-and-ai.md#L1-L194`):
  - In-house OAuth 2.1 Authorization Server with live scope narrowing per request against granting user's current role (`platform-and-ai.md#L40-L56`).
  - First-party API keys carrying their own dedicated `role_id` (`platform-and-ai.md#L62-L69`).
  - In-process JSON-RPC 2.0 MCP server (`POST /mcp`) with propose-only writes (`platform-and-ai.md#L73-L100`).
  - The `agents.review` queue gating autonomous journal drafts (`platform-and-ai.md#L104-L110`).
  - Transactional outbox `event_log` with per-org ordered positions (`platform-and-ai.md#L124-L140`).
  - Polled agent work queue (Initiative Q / Milestone 6) where OpenBooks holds **no LLM credentials** and delegates reasoning to external agent runtimes (`platform-and-ai.md#L163-L176`).

---

## 2. Runtime Topology and Infrastructure

### 2.1 Process Roles (One Container Image, Three Roles)
OpenBooks builds a single Docker image (`OpenBooks/Dockerfile#L1-L60`) that dispatches based on the `OPENBOOKS_ROLE` environment variable (`OpenBooks/packages/server/src/entrypoints/main.ts#L1-L35`):
1. **`api` Role** (`packages/server/src/entrypoints/api.ts#L1-L206`):
   - Initializes MySQL connection pool and verifies reachability before listening (`api.ts#L50-L66`).
   - Composes identity resolvers: OAuth bearer (`oba_...`), API key (`obk_...`), and session cookie (`api.ts#L91-L97`).
   - Starts Fastify HTTP server binding REST routes, MCP host (`POST /mcp`), and OpenAPI swagger docs (`api.ts#L99`).
   - When running with `QUEUE_PROVIDER=in-process`, also executes scheduled ticks and job consumers (`api.ts#L113-L140`).
2. **`worker` Role** (`packages/server/src/entrypoints/worker.ts#L1-L142`):
   - Idles until jobs are enqueued; connects to queue provider (in-process or AWS SQS).
   - Consumes and executes background jobs:
     - Statement import parsing (`worker.ts#L67`).
     - Recurring invoices and dunning cycles (`worker.ts#L68-L69`).
     - Recurring GL journal sweeps (`worker.ts#L72`).
     - Fixed-asset depreciation sweeps (`worker.ts#L75`).
     - Asynchronous OCR document extraction (`worker.ts#L79`).
     - Payment processor balance polling backstop (`worker.ts#L82`).
     - Live bank feed synchronization (`worker.ts#L85`).
     - Automations agent work queue sweeps (`worker.ts#L88`).
     - Database log retention pruner (`worker.ts#L91`).
   - Runs `startDailyTick` to drive 24-hour maintenance schedules (`worker.ts#L96`).
3. **`migrate` Role** (`packages/server/src/entrypoints/migrate.ts#L1-L70`):
   - Executes Kysely database migrations in alphabetical order (`0001_tenancy.ts` through `0999_app_grants.ts`) using migrator credentials (`DATABASE_MIGRATOR_USER`).

### 2.2 Local Container and Cloud Infrastructure
- **Local Dev Stack** (`OpenBooks/docker-compose.yml#L1-L150`): Provisions MySQL 8.4 with init scripts (`docker/mysql-init/01-users.sql` and `02-grants.sql`), LocalStack for SQS/S3, and mounts ephemeral volumes.
- **Production Terraform Topology** (`OpenBooks/infra/terraform/`):
  - Compute: ECS Fargate cluster with tasks for `api` and `worker` (`infra/terraform/modules/compute/tasks.tf#L1-L120`).
  - Edge: Application Load Balancer and CloudFront CDN (`infra/terraform/modules/edge/alb.tf#L1-L80`).
  - Messaging: AWS SQS queues for durable background jobs, SES for invoice delivery, and S3 for document storage (`infra/terraform/modules/messaging/sqs.tf#L1-L60`).
  - Data: AWS RDS MySQL 8.4 with KMS encryption (`infra/terraform/modules/data/main.tf#L1-L75`).

---

## 3. Interfaces and Contracts Inventory

### 3.1 REST API Surface (48 Route Modules)
All REST routes are defined under `packages/server/src/transport/routes/` and mounted onto the Fastify instance in `packages/server/src/transport/app.ts#L120-L195`. All endpoints enforce tenant isolation (`requireOrgScope`) and require the `Idempotency-Key` header on mutating methods.

| Route Group / File | HTTP Method & Path | Auth Requirement | Permission Key (`catalog.ts`) | Idempotency / Guarantees | CoS Capability Relevance |
|---|---|---|---|---|---|
| **Agent Proposals** (`agent-proposals.ts#L61-L151`) | `GET /v1/agent-proposals`<br>`POST /v1/agent-proposals/:id/approve`<br>`POST /v1/agent-proposals/:id/reject` | Bearer (API Key / OAuth) or Session | `agents.review`<br>`agents.review` + `journals.post`<br>`agents.review` | Lists pending drafts.<br>`approve` posts draft atomically via `postDraft` with `Idempotency-Key`.<br>`reject` discards draft. | **Delegation & Command**: Primary human-in-the-loop review queue for CoS/agent proposals. |
| **Automations & Work Items** (`automations.ts#L99-L359`) | `POST /v1/automations`<br>`GET /v1/automations`<br>`POST /v1/automations/:id/run`<br>`GET /v1/work-items`<br>`POST /v1/work-items/:id/cancel` | Bearer (API Key / OAuth) or Session | `workflows.write`<br>`workflows.read`<br>`workflows.activate`<br>`workflows.read`<br>`workflows.write` | `POST` routes enforce `Idempotency-Key`. Double-clicked `run` replays `AutomationRunResult`. | **Delegation & Orchestration**: External scheduling and work-item lifecycle management. |
| **Pay Bills** (`pay-bills.ts#L98-L428`) | `GET /v1/pay-bills/payable-bills`<br>`POST /v1/pending-payments`<br>`POST /v1/pending-payments/issue`<br>`POST /v1/pending-payments/batch-issue` | Bearer (API Key / OAuth) or Session | `pending_payments.read`<br>`pending_payments.write`<br>`disbursements.issue`<br>`disbursements.issue` | Separation of duties (building queue vs releasing funds). Issue posts journals via `recordPayment` with mandatory idempotency. | **Command & Orchestration**: Automated bill settlement and rail disbursement. |
| **API Keys** (`api-keys.ts#L46-L124`) | `POST /v1/api-keys`<br>`GET /v1/api-keys`<br>`DELETE /v1/api-keys/:id` | Bearer (API Key / OAuth) or Session | `api_keys.write`<br>`api_keys.read`<br>`api_keys.write` | Generates `obk_...` key bound to role. Secret returned once. Revocation takes effect on immediate next request. | **Command**: CoS machine credential provisioning. |
| **OAuth 2.1 AS** (`oauth-clients.ts`, `oauth-flow.ts`) | `POST /v1/oauth-clients`<br>`GET /oauth/authorize`<br>`POST /oauth/token`<br>`POST /oauth/revoke` | Admin session / Basic / PKCE | `integrations.write` (client registration) | Mandatory PKCE code exchange. Opaque bearer tokens (`oba_...`). Scopes recomputed live. | **Command**: Scoped third-party application authorization. |
| **Change Feed** (`change-feed.ts#L23-L41`) | `GET /v1/change-feed` | Bearer (API Key / OAuth) or Session | Org-scoped read | Keyset cursor pagination over `event_log`. Total order per org. Resumable. | **Monitoring**: Event log stream for CoS state tracking. |
| **External Refs** (`external-refs.ts#L20-L80`) | `POST /v1/external-refs`<br>`GET /v1/external-refs/:system/:id` | Bearer (API Key / OAuth) or Session | `integrations.write`<br>`integrations.read` | Bidirectional mapping between external IDs (e.g. Shopify/Stripe) and internal OpenBooks UUIDs. | **Orchestration**: Cross-system correlation. |
| **Reports** (`reports.ts#L1-L150`, `report-export.ts`) | `GET /v1/reports/trial-balance`<br>`GET /v1/reports/aging`<br>`GET /v1/reports/balance-sheet`<br>`GET /v1/reports/profit-and-loss`<br>`GET /v1/reports/export` | Bearer (API Key / OAuth) or Session | `reports.read` | Point-in-time and range calculations. Real-time ledger aggregation. CSV/XLSX export. | **Reporting**: Financial data extraction for CEO brief and KPI scorecards. |
| **Audit Trail** (`reports.ts#L160-L195`) | `GET /v1/reports/audit` | Bearer (API Key / OAuth) or Session | `audit.read` | Keyset-paginated timeline of actor provenance and fiscal period close events. | **Reporting & Monitoring**: Complete machine/human action auditability. |
| **Scheduling** (`scheduling.ts#L1-L50`) | `POST /v1/scheduling/run-due-work` | Bearer (API Key / OAuth) or Session | `workflows.activate` | Triggers immediate execution of due automated tasks (dunning, recurring journals, etc.). | **Orchestration**: CoS on-demand sweep trigger. |
| **Inbound Webhooks** (`processing-webhook.ts#L1-L60`, `bill-inbound.ts`) | `POST /public/processing/:connectionId/webhook`<br>`POST /v1/bills/inbound/:token` | Public / Signature Header / Capability Token | None (Signature or Token verified in service) | Inbound HMAC verification. Two-level idempotency (`processor_events` + `external_refs`). | **Monitoring (Inbound only)**: Ingests external bank/processor events. |

### 3.2 OpenAPI Specification and Drift Guard
- `OpenBooks/openapi.json`: The complete root OpenAPI 3.1 specification (over 2.1 MB).
- **Drift Gate** (`OpenBooks/packages/server/src/entrypoints/spec.ts#L1-L111`): `yarn spec --check` boots `buildApp` with mock config, renders the OpenAPI document, canonicalizes object keys, and asserts byte-for-byte identity against `openapi.json`.
- **Client Generation**: Web client types in `packages/web/src/api/schema.d.ts` are regenerated via `fastify-type-provider-zod`, ensuring zero client drift.

### 3.3 MCP (Model Context Protocol) Specification
- **Host Architecture** (`packages/server/src/modules/mcp/host.ts#L1-L398`):
  - Mounted at `POST /mcp` in-process on the Fastify application instance (`host.ts#L354-L362`).
  - Hidden from OpenAPI schema (`{ schema: { hide: true } }`, `host.ts#L361`) because MCP publishes its own tool schema via `tools/list`.
  - Zero external SDK dependencies: parses JSON-RPC 2.0 requests (`initialize`, `tools/list`, `tools/call`).
  - Always returns HTTP 200 with structured JSON-RPC error envelopes on dispatch failures (`host.ts#L77-L90`, Decision D-118).
- **Tool Suite** (`packages/server/src/modules/mcp/tools.ts#L80-L321`):
  1. `accounts.list` (`tools.ts#L83`): Keyset-paginated CoA read (`accounts.read`).
  2. `contacts.list` (`tools.ts#L100`): Customers and vendors list (`contacts.read`).
  3. `reports.trial_balance` (`tools.ts#L117`): Real-time debit/credit verification (`reports.read`).
  4. `invoices.list` (`tools.ts#L135`): AR invoices list with status filters (`invoices.read`).
  5. `bills.list` (`tools.ts#L153`): AP bills list with vendor reference filters (`bills.read`).
  6. `journal.propose` (`tools.ts#L175`): Propose-only write (`journals.post`). Refuses `mode: "execute"` outright (`tools.ts#L195-L208`). Lands a draft in `journal_drafts` for human approval in `agents.review`.
  7. `work_queue.poll` (`tools.ts#L255`): Leases next queued task for an agent (`workflows.read`).
  8. `work_queue.submit_proposal` (`tools.ts#L281`): Submits agent reasoning as a journal draft tied to lease token (`journals.post`).

### 3.4 Extension SDK (`@openbooks/plugin-api`)
Located in `packages/plugin-api/src/`:
- `actor.ts`: Defines `ACTOR_TYPES = ['user', 'automation', 'agent']` and `INVOCATION_MODES = ['interactive', 'scheduled']`.
- `posting.ts`: Defines `PostingService`, `PostJournalInput`, `PostedJournal`, and line types.
- `permissions.ts`: Defines plugin permission models.
- `mcp.ts`: Defines `McpToolDefinition` and `ToolProposal` shapes.
- `events.ts`: Declares domain event contracts (`JournalPostedV1`, `InvoiceIssuedV1`, `PaymentRecordedV1`).
- `providers.ts`: Swappable provider interfaces for Storage, Queue, Secrets, Email, Bank Feeds, and Payment Processors.

---

## 4. Boundaries, Authn/Authz, Tenancy, and Money Safety

### 4.1 Authentication and Principal Identity Matrix
The identity dispatcher in `packages/server/src/entrypoints/api.ts#L91-L97` evaluates incoming requests across three resolvers:

| Principal Type | Credential Prefix | Resolver Location | Resulting `actorType` | `userId` | `roleId` Resolution | Scope Narrowing |
|---|---|---|---|---|---|---|
| **Human User** | Session Cookie (`obs_...`) | `modules/auth/identity.ts` | `'user'` | String UUID | Re-derived live from `org_members` | None (holds full role permissions) |
| **OAuth Application** | Bearer `oba_...` | `modules/auth/oauth-identity.ts` | `'user'` | Granting User UUID | Re-derived live from granting user's `org_members` | **Yes**: Intersected live between granted token scopes and user's role (`D-54`) |
| **API Key (Machine)** | Bearer `obk_...` | `modules/auth/api-key-identity.ts` | `'automation'` | `null` | Key's own `role_id` column (`D-55`) | None (holds full permissions granted to key's role) |
| **Native Agent** | *No direct auth credential* | `plugin-api/src/actor.ts` | `'agent'` | `null` | *Latent in schema* | Can only act via OAuth/API-key proxy or internal automation context |

### 4.2 Authorization & Permission Catalog
- Defined in `packages/server/src/modules/permissions/catalog.ts#L36-L171`.
- Contains exactly **78 pinned permissions** (`catalog.ts#L205`: `AssertCatalogSize<78>`).
- Enforced strictly in domain services via `requirePermission(ctx, 'resource.action')` (`modules/permissions/permissions.service.ts`).
- Transport layer holds no permission enforcement (`CLAUDE.md#L141`).
- Role assignment: 7 pre-seeded system roles (Owner, Admin, Bookkeeper, Approver, AR Clerk, AP Clerk, Viewer) in `0001_tenancy.ts`, plus user-defined custom roles created via the custom role builder (`OB-226`).

### 4.3 Tenancy Guarantees
- Multi-tenancy is enforced at the database query builder level via `tenantDb(orgId)` (`packages/server/src/db/tenant.ts#L1-L60`).
- Tenant tables require composite primary keys `(org_id, id)`.
- Dependency Cruiser rule `tenant-tables-scoped-through-tenant-db` in `.dependency-cruiser.cjs` fails the build if any code attempts to query tenant tables using an unscoped database handle.
- A cross-tenant query produces an identical 404 response to a nonexistent entity (`CLAUDE.md#L132`), preventing tenant enumeration.

### 4.4 Money Safety, Invariants, and Ledger Integrity
1. **Double-Entry Balance Verification** (`modules/ledger/posting.service.ts#L361-L373`):
   $$\sum \text{Debits} == \sum \text{Credits}$$
   Verified using exact `bigint` minor units (`packages/shared-types/src/money.ts`). Zero-value journals are explicitly rejected (`posting.service.ts#L375-L382`).
2. **Append-Only Immutability via MySQL Grants** (`db/migrations/0999_app_grants.ts#L17-L22`):
   Application user `openbooks_app` holds only `SELECT, INSERT` on `journals` and `journal_lines`. `UPDATE` and `DELETE` privileges are never granted.
3. **AST Write-Path Protection** (`packages/eslint-plugin/src/rules/no-journal-writes.js#L1-L76`):
   ESLint rule strictly forbids `insertInto`, `updateTable`, `deleteFrom`, or `replaceInto` calls on journal tables anywhere in `packages/server` except `posting.repository.ts`, migrations, and test factories.
4. **Fiscal Period Locking** (`modules/ledger/posting.service.ts#L131`):
   Posting acquires a row lock (`FOR UPDATE`) on the target fiscal period in `periods` and calls `assertPostable(input.date)`. If the period is closed, the transaction is rejected immediately.
5. **Idempotency Engine** (`packages/server/src/transport/idempotency.ts` & `modules/idempotency/service.ts`):
   - Every mutating endpoint mandates the `Idempotency-Key` header (`max-length: 255`).
   - Atomic claim row inserted in `idempotency_claims` with SHA-256 request payload fingerprint.
   - Retries with identical payload replay the stored response body and status without re-executing logic.
   - Conflicting retries return `409 Conflict` (`idempotency_key_conflict`).
6. **Field Encryption & Secrets Isolation** (`packages/server/src/crypto/field-encryption.ts#L1-L66`):
   Sensitive PII (e.g. vendor tax IDs) is encrypted at rest using AES-256-GCM with a 12-byte IV and 16-byte auth tag. External credentials (Stripe secrets, bank tokens) are isolated in `secrets_store.ts`.

---

## 5. Internal Orchestrators and Job Models

1. **Automations Engine (Initiative Q)**:
   - Configured via `modules/automations/automations.service.ts` and `engine.ts`.
   - Actions supported: `annotate` (writes audit notes) and `agent_task` (enqueues `work_items`).
   - Work items follow a state machine: `queued` → `leased` (via `work_queue.poll`) → `proposed` (via `work_queue.submit_proposal`) → `completed` (upon human approval) or `cancelled`/`expired`.
2. **Pay Bills Pipeline**:
   - `modules/pay-bills/queue.service.ts` builds payable queues.
   - `modules/pay-bills/issue.service.ts` executes payments across check, ACH, and manual rails.
   - Enforces separation of duties: clerks build the queue (`pending_payments.write`); only owners/authorized officers release disbursements (`disbursements.issue`).
3. **Recurring Document & Depreciation Engines**:
   - `modules/invoicing/recurring.ts` generates scheduled customer invoices.
   - `modules/recurring-journals/engine.ts` posts recurring adjusting entries.
   - `modules/fixed-assets/depreciation.service.ts` calculates and posts monthly straight-line depreciation.
4. **Bank Feeds & Reconciliation**:
   - `modules/bank-feeds/feed-sync.service.ts` executes scheduled transaction pulls from financial providers.
   - `modules/banking/statement-import.job.ts` handles bulk CSV/OFX statement parsing in the worker process.

---

## 6. Frontend UI Inventory

The single-page application (`packages/web/src/screens/`) provides 40 screens covering:
- **Core Bookkeeping**: Chart of Accounts, Journal Entry form, General Ledger, Cash Application (`/money-in`), Reconciliation (`/banking-match`).
- **Autonomous Agent Review Surface**:
  - `screens/agent-proposals/list.tsx`: Summary table of all pending agent-generated journal drafts (`screens/agent-proposals/list.tsx#L18-L65`).
  - `screens/agent-proposals/review-dialog.tsx`: Line-by-line debit/credit inspection with dedicated "Approve and post" (`useApproveProposal`) and "Reject" (`useRejectProposal`) actions (`review-dialog.tsx#L39-L181`).
- **Work Items Oversight**: `screens/work-items/work-items.tsx`: Real-time dashboard of queued, leased, and proposed agent tasks.
- **Payables & Disbursements**: `screens/pay-bills/pay-bills.tsx`, `screens/disbursements.tsx`.
- **Integrations & Governance**: `screens/api-keys/api-keys.tsx`, `screens/oauth-clients.tsx`, `screens/oauth-consent.tsx`, `screens/connected-apps.tsx`, `screens/roles.tsx`.
- **Reporting**: Trial Balance, Balance Sheet, P&L, AR/AP Aging, Customer Statement Packages.

---

## 7. Verified Absences (Negative Search Audit)

| Claimed Capability / Entity | Search Terms & Locations Covered | Result & Verification |
|---|---|---|
| **Chief of Staff (Internal Agent)** | `grep -rn "chief_of_staff" packages/`<br>`grep -rn "chief-of-staff" packages/`<br>`find . -name "*chief*"` | **ABSENT** (0 hits in codebase). CoS exists only in OS-level specifications. |
| **Outbound Webhooks / Event Push** | `grep -rn "webhook" packages/server/src/modules/`<br>`grep -rn "dispatchWebhook" packages/` | **ABSENT** for outbound events. All webhook routes are inbound receivers (`processing-webhook.ts`, `bill-inbound.ts`). Outbound notification is pull-based (`change-feed.ts`). |
| **Direct Agent Journal Posting** | `grep -rn "mode: 'execute'" packages/server/src/modules/mcp/`<br>`grep -rn "postDraft" packages/server/src/modules/mcp/` | **ABSENT**. MCP write tools (`journal.propose`, `work_queue.submit_proposal`) refuse execution mode and exclusively land drafts. Direct posting requires human approval. |
| **Vector DB / Central Knowledge Sync** | `grep -rn "qdrant" packages/`<br>`grep -rn "pgvector" packages/`<br>`grep -rn "embedding" packages/` | **ABSENT** (0 hits). OpenBooks provides no built-in sync to external vector databases. |
| **Native Machine Agent Identity in Auth** | `grep -rn "actorType = 'agent'" packages/server/src/modules/auth/` | **ABSENT** in auth resolvers. API keys resolve to `'automation'`; OAuth resolves to `'user'`. Native `'agent'` actor type is defined in SDK but unassigned by identity resolvers. |

