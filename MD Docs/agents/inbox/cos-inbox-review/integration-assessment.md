# Phase 4: Integration-Layer Assessment Plan (CoS Lenses)

**Review Target:** Inbox Agent (`business-os/agents/inbox/inbox-zero`)  
**Evaluation Criteria:** Ability to support future Chief of Staff (CoS) **command, delegation, orchestration, monitoring, and reporting**.

---

## 1. 5×5 Integration Readiness Matrix

### Rating Definitions:
- **0 – Absent:** No surface found in codebase (supported by negative searches).
- **1 – Partial:** Surface exists but is not agent-consumable as-is (e.g., restricted to interactive human session cookies, lacks machine authn, or lacks documented contract).
- **2 – Ready:** Documented contract, non-interactive machine authentication, scoped access control, and comprehensive test coverage.
- **3 – Extensible:** Ready *and* designed for third-party/machine consumers (pluggable registry, versioned contracts, consent tiers, idempotency keys).

| Channel \ Capability Lens | Command (Issue & Authorize Actions) | Delegation (Hand off Tasks & Track Status) | Orchestration (Multi-step, Idempotent, Cancellable) | Monitoring (Events, State Changes, Health) | Reporting (Stats, Audit Trails, Analytics) |
|---|---|---|---|---|---|
| **REST + API Keys** (`app/api/v1/*`, `packages/api`, `openapi.json`) | **1 (Partial)** <br>Rules & unsubscribe actions supported via API Key; core mail commands (`archive`, `send`, `trash`) are locked behind session cookies. | **0 (Absent)** <br>No API-key accessible job submission or task polling endpoints. | **1 (Partial)** <br>Rules can be composed/updated atomically; no multi-step mail transaction semantics exposed via API key. | **1 (Partial)** <br>`/api/health` exists (no auth); no event streams or state change endpoints accessible via API key. | **2 (Ready)** <br>`/api/v1/stats/by-period` and `/api/v1/stats/response-time` accept `STATS_READ` API keys with full types. |
| **MCP Server** (`app/api/mcp-server`, `plugins/inbox-zero-mcp`) | **2 (Ready)** <br>Exposes 11 tools (`search_inbox`, `create_draft`, `create_rule`, `get_stats_by_period`, etc.) with `mcp:read`/`write`/`send` scopes. | **1 (Partial)** <br>CoS can execute tools synchronously; no asynchronous task handoff or job queueing tools exist in MCP. | **2 (Ready)** <br>LLM agent loops can compose multiple tool calls sequentially; tools return structured errors on failure. | **1 (Partial)** <br>Streamable HTTP transport supported; no push event subscription or webhook notification mechanisms over MCP. | **2 (Ready)** <br>`get_stats_by_period` and `get_response_time_stats` exposed as first-class tools. |
| **Outbound Webhooks** (`utils/outbound-webhook/call-webhook.ts`) | **0 (Absent)** <br>Outbound webhooks cannot issue commands (push-only egress). | **1 (Partial)** <br>Can notify external receiver when a rule fires on an email; no return task status handshake. | **1 (Partial)** <br>Executes HTTP POST on rule match; timeout is fixed at 1,000ms (`call-webhook.ts#L18`); no retry/orchestration bus. | **2 (Ready)** <br>Pushes structured event on rule match signed with Standard Webhook HMAC headers. | **1 (Partial)** <br>Payload includes executed rule metadata (`ExecutedRule`), but does not provide aggregate statistics or audit logs. |
| **Adapters & Protocols** (`mail-core/src/protocol/mail-http.ts`, desktop IPC) | **1 (Partial)** <br>`operations/[commandId]` PUT executes arbitrary mail actions, but requires session cookie auth. | **2 (Ready)** <br>`operationAdmitRequest` admits operations with `attemptId`; inspect/cancel endpoints exist. | **3 (Extensible)** <br>Full idempotency, `status: confirmed/accepted/rejected`, cancel semantics (`cancelled/too_late`), versioned schemas. | **1 (Partial)** <br>Polling inspection (`POST operations/[commandId]`); no outbound machine event push. | **1 (Partial)** <br>`assistant-state` route tracks state; no aggregate analytics surface in mail-http. |
| **Messaging Channels** (Slack, Teams, Telegram) | **1 (Partial)** <br>Interactive chat bot actions; requires user channel binding and OAuth app setup. | **1 (Partial)** <br>Automation check-ins post messages to channels; no machine delegation API. | **0 (Absent)** <br>No multi-step programmatic orchestration surface over chat platforms. | **2 (Ready)** <br>Delivers automated morning briefs and check-ins directly into Slack/Teams channels. | **1 (Partial)** <br>Summaries posted into chat; no structured machine-readable reporting API. |

---

## 2. In-Depth Cell Evaluation by Capability Lens

### 2.1 Command (Issue & Authorize Actions)
- **REST + API Keys (Score: 1):** An external caller can authenticate using `API-Key: <key>` header (`utils/api-auth.ts#L38`). However, available actions are strictly limited to rules management (`/api/v1/rules`) and unsubscribe (`/api/v1/senders/unsubscribe`). All direct mail actions (`archive`, `trash`, `send`) sit under `mail/v1/` and `app/api/threads/`, which use `withEmailAccount` and `withEmailProvider` (`utils/middleware.ts#L712-L739`), requiring human user session cookies (`betterAuth`).
- **MCP Server (Score: 2):** Exposes tools for inbox searching, thread reading, draft creation, and rule manipulation (`utils/mcp/tool-specs.ts#L1-L150`). Scopes (`mcp:read`, `mcp:write`, `mcp:send`) prevent accidental sending. **Gating Barrier:** It requires an interactive OAuth 2.0 PKCE flow (`docs/api-reference/mcp.mdx#L30-L36`), rejecting static API keys.
- **Adapters & Mail Protocol (Score: 1):** The `mail-http` protocol (`packages/mail-core/src/protocol/mail-http.ts#L266-L311`) is a world-class command executor supporting `archive`, `unarchive`, `set_read`, `trash`, `snooze`, and `discard_draft`. However, its HTTP mount at `api/mail/v1/accounts/[accountId]/operations/[commandId]/route.ts` is wrapped in `withEmailProvider`, making it unreachable via machine API keys.

### 2.2 Delegation (Hand Off Tasks & Track Status)
- **REST + API Keys (Score: 0):** There is no API-key accessible endpoint to submit, track, or poll asynchronous tasks or batch operations. Negative grep: `grep -rn "withAccountApiKey" apps/web/app/api/automation-jobs/` -> **0 hits**.
- **MCP Server (Score: 1):** MCP tool execution is strictly synchronous request/response. There are no tools to submit a background delegation job (e.g., triage 200 emails) and poll for completion.
- **Adapters & Mail Protocol (Score: 2):** `packages/mail-core/src/protocol/mail-http.ts` provides explicit delegation constructs: `operationAdmitResultSchema` returns `status: "accepted"` with `receiptId` and `retryAfterMs` for asynchronous processing, and provides `operationInspectRequestSchema` for polling status.

### 2.3 Orchestration (Multi-Step, Idempotent, Cancellable)
- **Adapters & Mail Protocol (Score: 3 - Extensible):** Idempotency is enforced by design via `attemptId` and `commandId` in `operationAdmitRequestSchema` (`mail-http.ts#L266-L272`). If a network blip occurs, re-admitting the same `attemptId` returns the confirmed outcome without re-executing. Cancellation is explicitly modeled via `operationCancelRequestSchema` returning `cancelled` or `too_late` (`mail-http.ts#L321-L332`).
- **Assistant Chat (Internal):** Handles complex multi-tool sequences internally via `aiProcessAssistantChat` (`chat.ts#L450-L550`), with rollback protection on partial action failures (`assistant-chat-partial-action-failures.test.ts`).

### 2.4 Monitoring (Events, State Changes, Health)
- **Outbound Webhooks (Score: 2):** When a rule matches an incoming email, `callWebhook` (`utils/outbound-webhook/call-webhook.ts#L36-L70`) posts a structured JSON payload to the configured endpoint signed with Standard Webhook headers (`webhook-id`, `webhook-timestamp`, `webhook-signature`).
- **Absence of General Event Bus (Score: 0):** Outside of rule actions, there are no outbound event emissions for thread state changes, new email arrivals, or task completions. The system lacks a Redis Pub/Sub emitter or external webhook subscription manager.

### 2.5 Reporting (Stats, Audit Trails, Analytics)
- **REST + API Keys (Score: 2):** Endpoints `/api/v1/stats/by-period` and `/api/v1/stats/response-time` are fully operational for machine consumers holding the `STATS_READ` API key scope (`apps/web/app/api/v1/stats/by-period/route.ts#L12-L35`). They return structured metrics on email volume, read/unread ratios, sent counts, and response latency percentiles.
- **MCP Server (Score: 2):** Tools `get_stats_by_period` and `get_response_time_stats` expose these identical metrics directly into LLM assistant contexts.

---

## 3. Top-5 Findings Affecting CoS Feasibility

1. **Authentication Bifurcation (The "Session Wall"):** Public API keys authenticate only to `/api/v1/rules`, `/api/v1/stats`, and `/api/v1/senders/unsubscribe`. The rich mail operations engine (`mail/v1/accounts/*/operations/*`) and assistant chat (`api/chat`) require human user session cookies (`betterAuth`). Without an adapter or bridge, CoS cannot execute direct mail commands.
2. **Interactive-Only MCP Server:** The built-in MCP server at `/api/mcp-server` requires an interactive OAuth 2.0 PKCE browser consent flow. It has no Client Credentials grant or static machine token mechanism, preventing headless CoS daemon startup without pre-generated tokens.
3. **Idempotent Operation Architecture Already Built:** The `mail-core` package already implements a complete, idempotent command admit/inspect/cancel protocol (`operationAdmitRequestSchema`, `attemptId`, `receiptId`, `too_late`). Exposing this protocol to machine callers requires zero domain redesign—only an authentication wrapper.
4. **Outbound Push Constrained to Rules Engine:** Outbound webhooks exist exclusively as a rule action (`RuleAction.type === "CALL_WEBHOOK"`). CoS cannot subscribe to generic mailbox events (e.g. "email received") without creating a catch-all automation rule.
5. **Single Automation Job Database Constraint:** Prisma enforces `@@unique([emailAccountId])` on `AutomationJob` (`schema.prisma#L1971`). CoS cannot create multiple named background automation jobs on a single inbox account without lifting this database constraint.

