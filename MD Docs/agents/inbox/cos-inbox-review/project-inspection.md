# Phase 3: Current-Project Inspection Plan (FACT Harvest)

**Review Target:** Inbox Agent (`business-os/agents/inbox/inbox-zero`)  
**Evidence Baseline:** Codebase inspection of `apps/*`, `packages/*`, `plugins/*`, `docs/*`, and `prisma/schema.prisma`.

---

## 1. Structure & Runtime Topology

### 1.1 Monorepo Layout
The project is organized as a pnpm + Turborepo monorepo configured via `pnpm-workspace.yaml` and `turbo.json`.

```text
inbox-zero/
├── apps/
│   ├── web/                  # Next.js 15 (App Router) full-stack web application & primary API host
│   ├── desktop/              # Electron application (Main process + utility host + React renderer)
│   ├── worker/               # BullMQ background job worker connecting to Redis
│   ├── image-proxy/          # Cloudflare / Node image proxy caching and sanitizing remote images
│   ├── image-proxy-aws/      # AWS Lambda version of the image proxy
│   └── unsubscribe-worker/   # Autonomous browser sub-agent service running Playwright in Docker
├── packages/
│   ├── api/                  # Node/TS typed API client (@inbox-zero/api) and CLI wrapper
│   ├── cli/                  # Setup CLI for AWS, GCP, Vercel, and Terraform deployment
│   ├── mail-core/            # Core mail engine, operation executor, sync state machine, protocol
│   ├── mail-react/           # React hooks and context providers for mail-core
│   ├── mail-sqlite/          # Local SQLite storage adapter for desktop mail-core
│   ├── mail-ui/              # Headless/styled mail UI components shared across web and desktop
│   ├── scheduling/           # Calendar scheduling and slot finding engine
│   ├── network/              # Safe URL parsing and SSRF protection utilities
│   ├── tinybird/             # Analytics ingestion client for Tinybird
│   ├── tinybird-ai-analytics/# Analytics schemas for AI token and cost tracking
│   ├── transactional-email/  # React-email templates for notification and verification emails
│   ├── loops/                # Loops.so customer email marketing integration
│   └── email-editor/         # TipTap-based rich text email composition editor
├── plugins/
│   └── inbox-zero-mcp/       # MCP plugin specification (mcp.json, plugin.json, SKILL.md)
├── docs/                     # Mintlify documentation and public openapi.json
└── charts/                   # Helm charts for Kubernetes deployment (web, worker, cronjobs, redis, postgres)
```

### 1.2 Applications Runtime Inventory

| Application | Runtime & Entry Point | Primary Responsibility | Reached By |
|---|---|---|---|
| `apps/web` | Node.js / Next.js 15 App Router (`apps/web/package.json#L1-L120`, `apps/web/app/api/`) | Primary web UI, user authentication, public REST API, MCP server, and database ORM layer. | Browser users, HTTP API clients, OAuth clients, Webhook providers. |
| `apps/desktop` | Electron / Node.js (`apps/desktop/src/main.ts#L1-L150`) | Cross-platform desktop email client with offline SQLite cache and local search. | Human end-users; communicates with `apps/web` via HTTP and local engine via IPC. |
| `apps/worker` | Node.js ESM (`apps/worker/src/index.mjs#L1-L11`, `apps/worker/src/runtime.mjs#L15-L60`) | Background job processor consuming Redis BullMQ queues (`automation-jobs`, `draft-cleanup`). | Redis BullMQ events; forwards processed jobs to `apps/web/api/*` via internal API key (`x-api-key`). |
| `apps/unsubscribe-worker` | Node.js / Fastify (`apps/unsubscribe-worker/src/server.ts#L1-L80`, `apps/unsubscribe-worker/src/runner.ts#L1-L70`) | Autonomous headless browser agent that executes web unsubscribe flows via Playwright. | Reached via HTTP POST from `apps/web` when processing unsubscribe actions. |
| `apps/image-proxy` | Node.js / Cloudflare Workers (`apps/image-proxy/package.json`) | Proxy and sanitize tracking pixels and remote email images to protect user IP. | Reached by web and desktop renderers loading HTML email bodies. |
| `apps/image-proxy-aws` | AWS Lambda (`apps/image-proxy-aws/package.json`) | AWS Lambda packaging of the image sanitization proxy. | CloudFront / API Gateway. |

### 1.3 Infrastructure & Deployment Topology
- **Docker Compose:** `docker-compose.yml#L1-L150` defines services for PostgreSQL (port 5432), Redis (port 6379), QStash emulation, web, and worker.
- **Helm Chart:** `charts/inbox-zero/` defines Kubernetes deployments for `web`, `worker`, `cronjobs`, `postgresql`, and `redis`.
- **AWS Copilot:** `copilot/` configures ECS Fargate manifests and webhook gateway infrastructure (`copilot/templates/webhook-gateway.yml`).

---

## 2. Interface Inventory (HTTP REST & Protocols)

The following table records the verified API surface under `apps/web/app/api/**`.

| Route Path | HTTP Methods | Auth Mechanism | Purpose & Handler Citation | Listed in `openapi.json`? |
|---|---|---|---|---|
| `api/v1/rules` | GET, POST | API Key (`withAccountApiKey`, scope: `RULES_READ` / `RULES_WRITE`) | List or create email automation rules (`apps/web/app/api/v1/rules/route.ts#L18-L45`). | **YES** (`docs/openapi.json#L487`) |
| `api/v1/rules/[id]` | GET, PUT, DELETE | API Key (`withAccountApiKey`, scope: `RULES_READ` / `RULES_WRITE`) | Get, update, or delete a specific automation rule (`apps/web/app/api/v1/rules/[id]/route.ts#L29-L110`). | **YES** (`docs/openapi.json#L1286`) |
| `api/v1/stats/by-period` | GET | API Key (`withStatsApiKey`, scope: `STATS_READ`) | Aggregated email volume stats by day/week/month (`apps/web/app/api/v1/stats/by-period/route.ts#L12-L40`). | **YES** (`docs/openapi.json#L75`) |
| `api/v1/stats/response-time` | GET | API Key (`withStatsApiKey`, scope: `STATS_READ`) | Email response time percentiles and metrics (`apps/web/app/api/v1/stats/response-time/route.ts#L12-L35`). | **YES** (`docs/openapi.json#L261`) |
| `api/v1/senders/unsubscribe` | POST | API Key (`withAccountApiKey`, scope: `SENDERS_UNSUBSCRIBE`) | Trigger unsubscribe from sender (`apps/web/app/api/v1/senders/unsubscribe/route.ts#L19-L45`). | **YES** (`docs/openapi.json#L2231`) |
| `api/mcp-server` (alias `/mcp`) | POST, OPTIONS | OAuth 2.0 PKCE Bearer JWT (`betterAuth` JWKS) | Streamable HTTP Model Context Protocol server exposing 11 tools (`apps/web/app/api/mcp-server/route.ts#L8-L18`). | NO (Documented in `docs/api-reference/mcp.mdx`) |
| `api/mail/v1/accounts/[accountId]/operations/[commandId]` | PUT, POST, DELETE | Session Cookie (`withEmailProvider`) | Core mail command execution, status inspect, and cancel protocol (`apps/web/app/api/mail/v1/accounts/[accountId]/operations/[commandId]/route.ts#L23-L90`). | NO (Internal mail-http protocol) |
| `api/mail/v1/accounts/[accountId]/capabilities` | GET | Session Cookie (`withEmailAccount`) | Inquire account capabilities and supported operations (`apps/web/app/api/mail/v1/accounts/[accountId]/capabilities/route.ts#L1-L40`). | NO (Internal mail-http protocol) |
| `api/mail/v1/accounts/[accountId]/scopes` | GET | Session Cookie (`withEmailAccount`) | Inspect provider OAuth scopes granted (`apps/web/app/api/mail/v1/accounts/[accountId]/scopes/route.ts#L1-L35`). | NO (Internal mail-http protocol) |
| `api/mail/v1/accounts/[accountId]/assistant-state` | GET, PUT | Session Cookie (`withEmailAccount`) | Get or update assistant conversation cursor/state (`apps/web/app/api/mail/v1/accounts/[accountId]/assistant-state/route.ts#L1-L50`). | NO (Internal mail-http protocol) |
| `api/chat` | POST | Session Cookie (`withEmailAccount`) | Conversational assistant streaming pipeline (`apps/web/app/api/chat/route.ts#L66-L120`). | NO (Internal Web UI only) |
| `api/chat/[id]/stream` | GET | Session Cookie (`withEmailAccount`) | Reconnect to active streaming chat SSE stream (`apps/web/app/api/chat/[id]/stream/route.ts#L1-L40`). | NO (Internal Web UI only) |
| `api/chat/[id]/stop` | POST | Session Cookie (`withEmailAccount`) | Abort an active streaming chat generation (`apps/web/app/api/chat/[id]/stop/route.ts#L1-L35`). | NO (Internal Web UI only) |
| `api/chat/confirm-email-action` | POST | Session Cookie (`withEmailAccount`) | Confirm and execute a pending email draft/send action (`apps/web/app/api/chat/confirm-email-action/route.ts#L1-L50`). | NO (Internal Web UI only) |
| `api/automation-jobs/execute` | POST | Internal API Key (`x-api-key`) / QStash HMAC | Execute scheduled morning brief or check-in run (`apps/web/app/api/automation-jobs/execute/route.ts#L10-L29`). | NO (Internal queue worker only) |
| `api/bulk-inbox-action/process` | POST | Internal API Key (`x-api-key`) / QStash HMAC | Process a chunk of a bulk inbox action (`apps/web/app/api/bulk-inbox-action/process/route.ts#L12-L55`). | NO (Internal queue worker only) |
| `api/user/bulk-inbox-action/[jobId]` | GET | Session Cookie (`withEmailAccount`) | Poll status and metrics of a running bulk action job (`apps/web/app/api/user/bulk-inbox-action/[jobId]/route.ts#L11-L42`). | NO (Internal Web UI only) |
| `api/user/api-keys` | GET, POST, DELETE | Session Cookie (`withAuth`) | User-facing management of API keys (`apps/web/app/api/user/api-keys/route.ts#L1-L50`). | NO (Internal Web UI only) |
| `api/google/webhook` | POST | Google Push Notification Verification | Handle Gmail push mailbox changes (`apps/web/app/api/google/webhook/route.ts#L1-L50`). | NO (Provider inbound) |
| `api/outlook/webhook` | POST | Microsoft Graph Client State Header | Handle Outlook push mailbox changes (`apps/web/app/api/outlook/webhook/route.ts#L1-L50`). | NO (Provider inbound) |
| `api/health` | GET | Public (No Auth) | Basic service liveness and database ping (`apps/web/app/api/health/route.ts#L1-L25`). | NO (Operational probe) |

---

## 3. Boundaries & Authorization Analysis

### 3.1 Authentication Mechanisms in Code
1. **API Key Authentication (`utils/api-auth.ts#L32-L57`):**
   - Header: `API-Key: <key>`.
   - Verified via SHA-256 hash match against `prisma.apiKey.findUnique({ where: { hashedKey } })`.
   - Strictly checked for `isActive` and `expiresAt > now()`.
   - Scopes verified against `options.requiredScopes` (`api-auth.ts#L48-L55`).
   - Requires `NEXT_PUBLIC_EXTERNAL_API_ENABLED=true` (`api-middleware.ts#L35`).
2. **Session Cookie Authentication (`utils/middleware.ts#L350-L368`):**
   - Implemented via `betterAuth.api.getSession({ headers })`.
   - Enforces user tenancy. Multi-tenant email accounts are validated via `emailAccountMiddleware` (`middleware.ts#L378-L415`) by checking `prisma.emailAccount.findFirst({ where: { id: emailAccountId, userId } })`.
3. **MCP Server Authentication (`utils/mcp/http.ts#L37-L55`):**
   - Header: `Authorization: Bearer <JWT>`.
   - Verified using `betterAuthConfig.api.getJwks()`.
   - Requires OAuth 2.0 PKCE flow. **Rejects opaque tokens and API keys** (`docs/api-reference/mcp.mdx#L32`).
4. **Internal Worker Authentication (`utils/internal-api.ts#L6`, `utils/qstash.ts`):**
   - Header: `x-api-key: <INTERNAL_API_KEY>` or QStash signature validation. Used exclusively for worker-to-web callbacks (`automation-jobs/execute`, `bulk-inbox-action/process`).

### 3.2 Licensing Boundary (`apps/web/ee/`)
- Directory: `apps/web/ee/` (`apps/web/ee/LICENSE.md#L1-L40`).
- Contains billing integrations: `ee/billing/apple/`, `ee/billing/lemon/`, `ee/billing/stripe/`.
- Governed by the **Inbox Zero Commercial License**; the rest of the repository is licensed under **AGPLv3** (`LICENSE#L1-L50`).
- **CoS Impact:** None. No core mail operations, MCP tools, rules engines, or APIs reside in `ee/`. CoS integration touches zero commercial-licensed files.

---

## 4. Internal Orchestrators & Agent Internals

### 4.1 Assistant Chat Orchestrator (`apps/web/utils/ai/assistant/chat.ts`)
- **Pipeline:** `aiProcessAssistantChat` (`chat.ts#L450-L550`) manages multi-turn tool calling using Vercel AI SDK (`ai`).
- **Tool Suite:** Includes read tools (`searchInbox`, `readThread`, `getCalendarEvents`, `getAssistantCapabilities`) and write tools (`createRule`, `updateRule`, `deleteRule`, `sendEmail`, `replyEmail`, `forwardEmail`, `bulkInboxAction`).
- **Confirmation Barrier:** Destructive email actions generate pending cards (`chat/confirm-email-action/route.ts`) requiring explicit human approval (`assistant-chat-confirmation.ts#L1-L60`) before execution.
- **Safety & Prompt Guards:** Context trimming for long contexts (`long-context-trimming.test.ts`), phishing hardening tests (`assistant-chat-phishing-hardening.test.ts`), and memory safety policies (`assistant-chat-memory-safety.test.ts`).

### 4.2 Automation Jobs Executor (`apps/web/utils/automation-jobs/execute.ts`)
- Model: `AutomationJob` in Prisma (`schema.prisma#L1950-L1975`).
- **Constraint:** Strictly enforced `@@unique([emailAccountId])`—only one automation job per email account is currently supported (`schema.prisma#L1971`).
- Runtime: Dispatched by cron (`api/cron/automation-jobs`) or Redis worker (`apps/worker`), processed in chunks with status tracking in `AutomationJobRun` (`schema.prisma#L1977`).

### 4.3 Bulk Inbox Action Executor (`apps/web/utils/bulk-inbox-action/process-job.ts`)
- Model: `BulkInboxActionJob` (`schema.prisma#L1304-L1340`).
- Architecture: Processes bulk actions in paginated chunks (up to 100 threads per chunk) with a distributed lease mechanism (`leaseExpiresAt`, `chunkToken`).
- Resilience: Recovers stalled jobs via `resumeStalledBulkInboxActionJob` (`resume-stalled-job.ts`) and limits maximum operations to prevent API quota starvation.

---

## 5. Verified Absences & Negative Search Log

To ensure zero fabrication, candidate capabilities were explicitly checked and proved absent using adversarial greps:

1. **Chief of Staff Receptacle:**
   - Search: `grep -rn -i "chief.*staff" apps/ packages/` -> **0 hits**.
   - Search: `grep -rn "orchestrator" apps/web/app/api/` -> **0 hits**.
   - Verdict: `ABSENT`. No CoS contract or supervisor adapter exists.
2. **Machine-Accessible Mail Command Endpoint:**
   - Search: `grep -rn "withAccountApiKey" apps/web/app/api/mail/` -> **0 hits**.
   - Search: `grep -rn "validateApiKey" apps/web/app/api/mail/` -> **0 hits**.
   - Verdict: `ABSENT`. The entire `mail/v1/accounts/**` tree is locked behind human session cookies (`withEmailAccount`/`withEmailProvider`).
3. **Outbound Event Bus / Subscriptions:**
   - Search: `grep -rn "redis.publish" apps/ packages/` -> **0 hits**.
   - Search: `grep -rn "EventEmitter" apps/web/app/api/` -> **0 hits**.
   - Verdict: `ABSENT`. No external event stream or subscription API exists. Outbound webhooks are triggered only by rule matches (`utils/outbound-webhook/call-webhook.ts`).

