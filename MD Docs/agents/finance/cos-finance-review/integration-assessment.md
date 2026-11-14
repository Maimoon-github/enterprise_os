# Phase 4: Integration-Layer Assessment Plan (Chief-of-Staff Lenses)

**Review Target:** Finance Agent (`business-os/agents/finance`)  
**Project Base:** `OpenBooks/` monorepo  
**Evaluation Standard:** Ability to support future Chief of Staff (CoS) **command, delegation, orchestration, monitoring, and reporting**.

---

## 1. Readiness Rating System

- **0 – Absent:** No programmatic surface found (verified by negative searches).
- **1 – Partial:** Surface exists but is incomplete, requires human browser session, lacks machine identity, or has unbridged gaps for agent consumption.
- **2 – Ready:** Fully documented contract, non-interactive authn/authz, scoped machine access, and automated test coverage.
- **3 – Extensible:** Ready *and* architecturally designed for third-party machine consumers (versioned schemas, permission catalog integration, idempotency keys, extension SDK).

---

## 2. 4×5 Integration Readiness Matrix

| Integration Channel \ CoS Lens | Command (Issue / Authorize) | Delegation (Hand off & Track) | Orchestration (Multi-step & Idempotent) | Monitoring (Events & State) | Reporting (Stats & Audit) |
|---|---|---|---|---|---|
| **REST + API Keys** (`transport/routes/*`, `modules/api-keys`, `openapi.json`) | **2 – Ready**<br>`api-keys.ts#L46`<br>`api-key-identity.ts#L60` | **2 – Ready**<br>`automations.ts#L99`<br>`agent-proposals.ts#L61` | **3 – Extensible**<br>`transport/idempotency.ts#L1`<br>`external-refs.ts#L20` | **2 – Ready**<br>`change-feed.ts#L23`<br>`health.ts#L1` | **3 – Extensible**<br>`reports.ts#L1`<br>`export/adapters.ts#L1` |
| **MCP Server** (`modules/mcp/{host.ts,tools.ts}`) | **1 – Partial**<br>`tools.ts#L175`<br>`host.ts#L354` | **3 – Extensible**<br>`tools.ts#L255`<br>`tools.ts#L281` | **1 – Partial**<br>`tools.ts#L195`<br>`host.ts#L1` | **1 – Partial**<br>`tools.ts#L117` | **2 – Ready**<br>`tools.ts#L117`<br>`tools.ts#L83` |
| **Webhooks / Events** (`processing-webhook.ts`, `change-feed.ts`, `outbox.ts`) | **0 – Absent**<br>(Inbound only;<br>no command hook) | **0 – Absent**<br>(No webhook-driven<br>delegation) | **1 – Partial**<br>`processing-webhook.ts#L1`<br>`outbox.ts#L61` | **2 – Ready**<br>`change-feed.ts#L23`<br>`outbox.ts#L61` | **1 – Partial**<br>`outbox.ts#L61` |
| **Plugin API SDK** (`packages/plugin-api/src/*`) | **3 – Extensible**<br>`posting.ts#L1`<br>`actor.ts#L1` | **2 – Ready**<br>`mcp.ts#L1`<br>`events.ts#L1` | **2 – Ready**<br>`providers.ts#L1`<br>`context.ts#L1` | **2 – Ready**<br>`events.ts#L1`<br>`actor.ts#L24` | **1 – Partial**<br>`primitives.ts#L1` |

---

## 3. Detailed Assessment per Cell

### 3.1 REST + API Keys Channel
- **Command [Rating 2 – Ready]:** CoS authenticates non-interactively using an API key (`Authorization: Bearer obk_...`). The resolver (`modules/auth/api-key-identity.ts#L60-L79`) binds the request to the key's assigned `roleId` with `actorType = 'automation'` and `userId = null`. CoS can execute any REST action allowed by the key's role (e.g. creating invoices, recording payments, queuing bills). Money-moving commands (such as releasing disbursements via `POST /v1/pending-payments/issue`) can be authorized if the key's role holds `disbursements.issue`.
- **Delegation [Rating 2 – Ready]:** CoS can delegate batch jobs and automations via `POST /v1/automations/:id/run` (`transport/routes/automations.ts#L99-L150`) or trigger scheduled due work via `POST /v1/scheduling/run-due-work`. Work items and agent proposals can be tracked via `GET /v1/work-items` and `GET /v1/agent-proposals`.
- **Orchestration [Rating 3 – Extensible]:** Outstanding multi-step support. Every mutating route mandates an `Idempotency-Key` header (`transport/idempotency.ts#L58-L80`). Transaction boundaries are preserved ambiently via `tenantDb()` (`db/transaction-scope.ts`). Correlation across systems is maintained via bidirectional external ID mappings (`POST /v1/external-refs`, `transport/routes/external-refs.ts#L20-L80`). Tasks can be explicitly cancelled via `POST /v1/work-items/:id/cancel`.
- **Monitoring [Rating 2 – Ready]:** CoS monitors state changes by pulling the transactional change feed (`GET /v1/change-feed`, `transport/routes/change-feed.ts#L23-L41`) using keyset cursors. Application liveness is monitored via `GET /health` (`transport/health.ts`).
- **Reporting [Rating 3 – Extensible]:** Comprehensive programmatic reporting. CoS can fetch real-time financial data via `GET /v1/reports/*` (Trial Balance, P&L, Balance Sheet, Aging, Cash Flow). All reports can be streamed as CSV or XLSX via `GET /v1/reports/export` (`modules/reports/export/export.service.ts`). Machine/human action provenance is retrievable via `GET /v1/reports/audit` (`modules/reports/audit.service.ts`).

### 3.2 MCP (Model Context Protocol) Channel
- **Command [Rating 1 – Partial]:** Fastify mounts `POST /mcp` in-process (`modules/mcp/host.ts#L354`). However, write commands are intentionally propose-only (`Decision D-60`): `journal.propose` explicitly throws `ValidationError` if called with `mode: "execute"` (`modules/mcp/tools.ts#L195-L208`). It lands a draft in `journal_drafts` and requires a human in `agents.review` to post. CoS cannot directly post journals or release money via MCP.
- **Delegation [Rating 3 – Extensible]:** Purpose-built for agent delegation under Milestone 6 (Initiative Q). `work_queue.poll` (`tools.ts#L255-L279`) leases pending tasks with automatic timeout/expiry. Once processed, the agent calls `work_queue.submit_proposal` (`tools.ts#L281-L305`) to return its structured proposal.
- **Orchestration [Rating 1 – Partial]:** MCP tool suite is currently limited to 8 tools (`tools.ts#L312-L321`). Multi-step business flows (e.g. invoice generation → payment application → reconciliation) cannot be orchestrated entirely within MCP and require falling back to REST.
- **Monitoring [Rating 1 – Partial]:** Only snapshot reads are supported (`trial_balance`, `accounts.list`, `invoices.list`, `bills.list`). There is no MCP tool for change feed streaming or event listening.
- **Reporting [Rating 2 – Ready]:** `reports.trial_balance` (`tools.ts#L117-L133`) returns full double-entry balance verification directly over journal lines. However, other major reports (P&L, Balance Sheet, Aging) are not yet exposed as MCP tools.

### 3.3 Webhooks / Events Channel
- **Command [Rating 0 – Absent]:** Webhooks in OpenBooks are exclusively inbound. There is no webhook listener configured to receive remote commands from CoS.
- **Delegation [Rating 0 – Absent]:** No webhook-driven task delegation interface.
- **Orchestration [Rating 1 – Partial]:** Inbound payment processor webhooks (`transport/routes/processing-webhook.ts#L1-L60`) orchestrate automatic charge recording and fee reconciliation. However, outbound event emission to drive external multi-agent choreography is absent.
- **Monitoring [Rating 2 – Ready]:** State changes write to an immutable transactional outbox (`event_log`, `modules/events/outbox.ts#L61-L80`) ordered by per-org `FOR UPDATE` position counters. CoS monitors state by polling `GET /v1/change-feed`. (Outbound push to webhooks or Redis is absent).
- **Reporting [Rating 1 – Partial]:** `event_log` stores committed domain event payloads, but structured aggregation must be fetched via REST reports.

### 3.4 Plugin API SDK Channel
- **Command [Rating 3 – Extensible]:** `@openbooks/plugin-api` exposes the formal `PostingService` interface (`plugin-api/src/posting.ts#L1-L150`) and actor models (`actor.ts#L1-L38`). Provides a clean contract for third-party extensions.
- **Delegation [Rating 2 – Ready]:** Defines `McpToolDefinition` and `ToolProposal` shapes (`mcp.ts#L1-L50`) for structured agent proposal submission.
- **Orchestration [Rating 2 – Ready]:** Declares provider contracts (`providers.ts#L1-L250`) enabling swappable infrastructure adapters (storage, queues, email).
- **Monitoring [Rating 2 – Ready]:** Declares strongly-typed domain events (`events.ts#L1-L120`) including `InvoiceIssuedV1`, `PaymentRecordedV1`, and `JournalPostedV1`.
- **Reporting [Rating 1 – Partial]:** Defines basic money and posting primitives; detailed reporting export adapters reside within the server module rather than the SDK.

---

## 4. Top-5 Findings Impacting Chief-of-Staff Feasibility

1. **Strict Propose-Only AI Gate (Decision D-60):** The MCP interface and agent queue deliberately prohibit direct posting (`tools.ts#L195-L208`). Autonomous agents cannot directly commit entries to the ledger; they can only stage mutable journal drafts for human approval in `agents.review`. If CoS requires autonomous posting capability, it must authenticate via API keys over REST holding `journals.post`, or the architecture must formalize an autonomous CoS approval tier.
2. **Pull-Only Change Feed (No Outbound Webhooks or Redis):** OpenBooks records events in a transactional outbox (`event_log`), but provides no outbound webhook dispatcher or Redis publisher (`transport/routes/change-feed.ts#L1-L41`). CoS must operate a polling worker to pull changes via `GET /v1/change-feed` rather than relying on reactive event pushes.
3. **Machine Identity Scoped as `'automation'`, Not `'agent'`:** API key authentication resolves `actorType` to `'automation'` with `userId = null` (`modules/auth/api-key-identity.ts#L76`). While `@openbooks/plugin-api/src/actor.ts` recognizes `actorType = 'agent'`, the authentication resolvers do not assign it. CoS actions via API keys will be recorded in audit logs as automated system operations rather than specialized agent operations.
4. **Comprehensive REST Surface with Strict Idempotency:** The REST surface (48 route files) provides complete coverage over all accounting operations. Every write endpoint mandates `Idempotency-Key` (`transport/idempotency.ts#L58`), preventing duplicate postings during CoS network retries or orchestration loops.
5. **Separation of Duties on Money Movement:** Releasing disbursements in Pay Bills requires `disbursements.issue`, separate from `pending_payments.write` (`transport/routes/pay-bills.ts#L59-L64`). This allows CoS to safely automate the queuing of vendor payments while reserving the final fund disbursement release for an authorized human executive.

