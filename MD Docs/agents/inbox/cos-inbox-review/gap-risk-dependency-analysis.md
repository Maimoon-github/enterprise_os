# Phase 5: Gap, Risk, Dependency & Modification-Point Analysis

**Review Target:** Inbox Agent (`business-os/agents/inbox/inbox-zero`)  
**Evaluation Criteria:** Minimal-touch architecture preserving agent autonomy and data boundaries.

---

## 1. Gap Register (CoS Capability Lenses)

| # | CoS Capability Lens | Identified Gap Description | Evidence Class | Code Citation & Evidence Justification |
|---|---|---|---|---|
| **GAP-01** | **Command** | **Session-Gated Mail Command Execution:** Direct mail actions (`archive`, `trash`, `mark_read`, `snooze`, `send`) are implemented in `mail/v1/accounts/[accountId]/operations/[commandId]` and `threads/*`, but are guarded by `withEmailProvider` / `withEmailAccount`, requiring human cookie sessions. Machine API keys cannot invoke them. | `FACT` | `apps/web/app/api/mail/v1/accounts/[accountId]/operations/[commandId]/route.ts#L23-L25` (`export const PUT = withEmailProvider(...)`); `apps/web/utils/middleware.ts#L350-L415`. |
| **GAP-02** | **Command** | **Interactive OAuth Constraint on MCP:** The Streamable HTTP MCP server requires OAuth 2.0 PKCE browser redirection and user consent. It explicitly rejects static API keys and opaque tokens, preventing zero-touch headless CoS initialization. | `FACT` | `apps/web/utils/mcp/http.ts#L37-L51` (`verifyMcpToken` via JWKS); `docs/api-reference/mcp.mdx#L30-L33`. |
| **GAP-03** | **Delegation** | **Absence of Machine Task Submission API:** While `BulkInboxActionJob` exists in Prisma and is executed in leased chunks by workers, there is no public API endpoint allowing an external machine principal to create or schedule a bulk job. | `FACT` | `apps/web/prisma/schema.prisma#L1304-L1340`; negative search: `grep -rn "withAccountApiKey" apps/web/app/api/bulk-inbox-action/` yielded 0 hits. |
| **GAP-04** | **Delegation** | **Single Automation Job Schema Constraint:** The `AutomationJob` database model has an explicit unique constraint `@@unique([emailAccountId])`, restricting the account to at most one scheduled automation job (such as the morning brief). | `FACT` | `apps/web/prisma/schema.prisma#L1969-L1971` (`// Current product behavior is one automation job per account. @@unique([emailAccountId])`). |
| **GAP-05** | **Monitoring** | **Rule-Constrained Outbound Event Egress:** Outbound webhook notifications are only dispatched when an incoming email matches an explicit user rule configured with a `CALL_WEBHOOK` action. There is no typed event subscription API or Redis pub/sub feed for general mailbox state changes. | `FACT` | `apps/web/utils/outbound-webhook/call-webhook.ts#L36-L70`; `apps/web/utils/webhook/process-history.ts#L1-L100`. |
| **GAP-06** | **Reporting** | **Audit Trail Surface Inaccessible via API Key:** Detailed execution audit logs (`ExecutedRule`, `ClassificationFeedback`, and `AuditContext`) are stored in Postgres, but the public API only exposes high-level aggregated counts (`/api/v1/stats/by-period`). Per-action audit logs cannot be retrieved by CoS via API. | `FACT` | `apps/web/prisma/schema.prisma#L836-L865`; `docs/openapi.json#L75-L486`. |

---

## 2. Risk Register

| # | Risk Description | Affected CoS Lens | Likelihood | Impact | Severity | Concrete Mitigation Strategy |
|---|---|---|---|---|---|---|
| **RSK-01** | **Accidental Email Exfiltration / Over-Privileged Sending:** An automated CoS command loop could inadvertently trigger destructive email sends or forward sensitive business data without human verification. | Command & Safety | Medium | Critical | **High** | Enforce `mcp:send` isolation and retain the `chat/confirm-email-action` human-in-the-loop barrier for high-impact outbound communications. |
| **RSK-02** | **Provider Rate Limit Starvation (Google / Microsoft):** Aggressive batch polling or bulk triage commands issued by CoS could exhaust the user's Gmail/Outlook API quotas, breaking desktop and web client sync. | Delegation & Operability | High | High | **High** | Route all CoS batch operations through the existing leased chunk engine (`processBulkInboxActionJobChunk` in `utils/bulk-inbox-action/process-job.ts`), honoring `rateLimitedUntil`. |
| **RSK-03** | **SSRF / Egress Attack via Outbound Webhook Targets:** CoS-created rules with `CALL_WEBHOOK` actions pointing to internal cluster services (e.g., Redis, internal cloud metadata) could compromise the environment. | Monitoring & Security | Low | Critical | **Medium** | Mitigated by existing production code: `utils/outbound-webhook/url-validation.ts#L1-L80` and `resolveSafeExternalHttpUrl` strictly block private and loopback IP ranges. |
| **RSK-04** | **Race Conditions with Active Rules Engine:** A CoS command modifying or archiving a thread concurrently with an incoming webhook trigger executing a rule could result in conflicting labels or duplicated replies. | Orchestration & Correctness | Medium | Medium | **Medium** | Leverage `mail-core`'s optimistic client and transaction state machine (`packages/mail-core/src/optimistic-client.ts#L1-L100`) with idempotency keys (`attemptId`). |
| **RSK-05** | **OAuth Refresh Token Expiration for Headless Daemons:** In an MCP-based integration, OAuth tokens expire and require refresh rotation. If the refresh grant is revoked or fails, CoS commands will stall. | Command & Operability | Medium | High | **High** | Configure `offline_access` scope during MCP client registration, persist refresh tokens in secure storage, and implement an automatic token refresh handler. |
| **RSK-06** | **Contract Drift between OpenApi and Implementation:** Endpoints may drift if developers add routes without updating `docs/openapi.json`. | Integration & Contract | Low | Medium | **Low** | Use `packages/api` client as the executable baseline and validate schemas against Zod models in `utils/actions/*.validation.ts`. |

---

## 3. Dependency Map

| Dependency Component | Type | Responsibility in Inbox Zero | CoS Impact & Required Changes |
|---|---|---|---|
| **PostgreSQL & Prisma** | Runtime (Database) | Relational store for users, accounts, rules, executed rules, jobs, and API keys (`apps/web/prisma/schema.prisma`). | **High:** CoS integration adds read/write query load. Future multiple-job support requires dropping `@@unique([emailAccountId])` on `AutomationJob`. |
| **Redis & BullMQ** | Runtime (Queue / Cache) | Background worker queue for `automation-jobs`, `draft-cleanup`, and rate-limiting (`apps/worker/src/runtime.mjs`). | **Medium:** CoS batch tasks will enqueue additional jobs into BullMQ. Shared Redis bus can be used for cross-agent event distribution. |
| **Better-Auth** | Runtime (Auth Engine) | User session management and OAuth 2.0 PKCE authorization server (`apps/web/utils/auth.ts`, `apps/web/utils/mcp/http.ts`). | **High:** Governs MCP token validation. CoS integration requires either pre-authenticated OAuth token storage or an extension supporting API Key bearer auth. |
| **Google & Microsoft APIs** | External Service | Inbound push notifications (Gmail PubSub, Graph Webhooks) and core email/calendar sync. | **Medium:** CoS commands trigger upstream provider API calls. Subject to upstream provider rate limits. |
| **QStash (Upstash)** | External Service / Queue | Scheduled HTTP webhook dispatcher for automation jobs and bulk chunk retries (`apps/web/utils/qstash.ts`). | **Low:** Utilized transparently by `withQstashOrInternal` middleware; local docker emulation exists for offline execution. |
| **Tinybird Analytics** | External Service | ClickHouse-backed event analytics for email counts and AI token usage (`packages/tinybird`). | **Low:** Purely observational; CoS can query aggregated metrics via existing stats APIs. |
| **Turborepo & Docker** | Build / Deploy Tooling | Monorepo pipeline (`turbo.json`) and container orchestration (`docker-compose.yml`, Helm). | **Low:** No build tooling modifications required; CoS operates as an external federated repository. |

---

## 4. Ranked Modification Points

We evaluate candidate modification points using the **minimal-touch principle**, separating **integration-only** options (zero repo change) from **extension options** (additive repo changes).

```
[Option A: Consume-Only (No Changes)] ───► [Option B: Additive Sockets] ───► [Option C: Deep Bus]
Lowest Touch / Immediate                High Power / Low Blast Radius        Invasive / High Touch
```

| Rank | Modification Site / Component | Proposed Modification | CoS Lens Unlocked | Blast Radius & Safety | Type |
|---|---|---|---|---|---|
| **1** | **`plugins/inbox-zero-mcp/` & `apps/web/utils/mcp/http.ts`** | **Support Machine Token Authentication in MCP:** Allow `handleMcpPostRequest` to accept hashed `API-Key` credentials directly in addition to OAuth JWTs. | Command, Monitoring, Reporting | **Minimal:** Isolated to `utils/mcp/http.ts`. Does not touch database schema or core email workflows. | **Additive** |
| **2** | **`apps/web/app/api/mail/v1/accounts/[accountId]/operations/[commandId]/route.ts`** | **Dual Authentication on Mail Operations Protocol:** Update endpoint to accept `withAccountApiKey` (requiring a new `MAIL_OPERATIONS` scope) alongside `withEmailProvider`. | Command & Orchestration | **Low:** Leverages the existing `mail-http` idempotent command executor (`createEmailProviderOperationExecutor`). Completely backwards-compatible with web/desktop. | **Additive** |
| **3** | **`apps/web/app/api/v1/jobs/` (New Route Group)** | **Expose Public Bulk Job Delegation Endpoint:** Add a thin REST API route wrapping `enqueueBulkInboxActionChunk` and exposing `BulkInboxActionJob` polling by `jobId`. | Delegation & Monitoring | **Low:** Purely additive route under `app/api/v1/`. Reuses existing background worker and lease mechanism. | **Additive** |
| **4** | **`apps/web/utils/api-key-scopes.ts` & `prisma/schema.prisma`** | **Extend API Key Scopes with Granular Machine Permissions:** Add `MAIL_EXECUTE`, `JOBS_MANAGE`, and `AUDIT_READ` to `ApiKeyScope` enum. | Controlled Data Access | **Medium:** Requires a single Prisma migration to add enum values; fully backwards-compatible. | **Additive** |
| **5** | **`apps/web/prisma/schema.prisma` (`AutomationJob`)** | **Lift Single-Job Constraint on Email Accounts:** Remove `@@unique([emailAccountId])` on `AutomationJob` to allow CoS to register distinct scheduled tasks (e.g., Morning Brief, EOD Summary, Weekly Cleanup). | Delegation & Orchestration | **Medium:** Requires updating index from `@unique` to regular index. Low blast radius on existing query paths. | **Invasive** |
| **6** | **`apps/web/utils/outbound-webhook/` & Event Bus** | **General Mailbox Event Webhook Egress:** Generalize `callWebhook` into a system-wide event dispatcher that emits typed events (e.g., `email.received`, `thread.archived`, `job.completed`) to registered subscriber URLs. | Monitoring & Orchestration | **High:** Involves hooking into mail sync pipelines (`process-history.ts`, `engine.ts`); potential latency impact on mail ingestion. | **Invasive** |

---

## 5. Integration-Only vs. Modification Options

### Approach A: Zero-Modification Integration (Immediate Feasibility)
- **Mechanism:** CoS communicates with Inbox Zero via:
  1. REST API using `API-Key: <key>` for Rules management (`/api/v1/rules`) and Stats reporting (`/api/v1/stats/by-period`).
  2. Inbound event capture by configuring an automated Rule in Inbox Zero with action `CALL_WEBHOOK` targeting the CoS FastAPI event endpoint.
  3. Pre-authorized Streamable HTTP MCP connection using a long-lived OAuth refresh token.
- **Verdict:** Fully possible today without touching a single line in the `inbox-zero` repository.

### Approach B: Contract-First Additive Extension (Recommended Strategy)
- **Mechanism:** Execute Modification Points #1 and #2:
  1. Add API-Key bearer support to the MCP endpoint (`utils/mcp/http.ts`).
  2. Allow API-Key access to `mail/v1/accounts/[accountId]/operations/[commandId]`.
- **Verdict:** Unlocks full non-interactive command execution, robust task delegation, and idempotent multi-step mail operations with zero disruption to human users or desktop clients.

