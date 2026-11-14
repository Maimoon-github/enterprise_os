# Phase 2: Inbox-Context Architecture Mapping

**Review Target:** Inbox Agent (`business-os/agents/inbox/inbox-zero`)  
**Methodology:** Grounded code inspection and negative search verification.

---

## 1. Architecture Mapping Table

| # | Architecture Element | Inbox-Domain Counterpart | Candidate Code Anchors | Status | Code Citations & Verification Evidence |
|---|---|---|---|---|---|
| **1** | **Chief of Staff (CoS) Agent** | External supervisor / orchestrator consumer. | None in codebase (receptacle inspection only). | `ABSENT` | Grep verification: `grep -rn -i "chief.*staff" apps/ packages/` yielded 0 hits; `grep -rn "orchestrat" apps/web/app/api/` yielded 0 hits. The agent has no internal awareness of a CoS principal. |
| **2** | **Independent Specialized Agents** | Primary Inbox Agent (`inbox-zero`), plus specialized autonomous sub-agents (`unsubscribe-worker`, MCP AI agent). | `apps/unsubscribe-worker`, `apps/web/utils/mcp/mcp-agent.ts`, `apps/worker`. | `EXISTS` | `apps/unsubscribe-worker/src/server.ts#L1-L150`, `apps/unsubscribe-worker/src/contracts.ts#L6-L50` (Playwright headless browser unsubscribe service); `apps/web/utils/mcp/mcp-agent.ts#L1-L80` (autonomous tool-calling agent for external integrations). |
| **3** | **Internal Orchestrators** | Assistant chat loop, automation job executor, rules evaluation engine, bulk action processor, and mail core engine. | `apps/web/utils/actions/assistant-chat.ts`, `apps/web/utils/ai/assistant/chat.ts`, `apps/web/app/api/automation-jobs/execute/route.ts`, `apps/web/utils/bulk-inbox-action/process-job.ts`, `packages/mail-core/src/engine.ts`. | `EXISTS` | `apps/web/utils/ai/assistant/chat.ts#L452-L478` (multi-turn tool-calling loop); `apps/web/app/api/automation-jobs/execute/route.ts#L10-L29` (QStash/BullMQ cron job dispatcher); `apps/web/utils/bulk-inbox-action/process-job.ts#L1-L120` (batched leased execution); `packages/mail-core/src/engine.ts#L1-L100` (state synchronization engine). |
| **4** | **Individual UI per Agent** | Standalone web dashboard, Electron desktop client, mobile interfaces, and messaging channel bots. | `apps/web/app/(app)/[emailAccountId]/*`, `apps/desktop/src/main.ts`, `apps/desktop/src/renderer/desktop-api.ts`, `apps/web/app/api/slack/*`. | `EXISTS` | `apps/web/app/(app)/[emailAccountId]/layout.tsx#L1-L80` (Next.js multi-tenant account layout); `apps/desktop/src/main.ts#L1-L120` (Electron desktop harness); `apps/desktop/src/mail-engine/ipc.ts#L1-L90` (IPC boundary between UI and engine); `apps/web/app/api/slack/events/route.ts#L1-L60` (Slack interactive bot UI). |
| **5** | **Integration Layer** | REST API with API Keys, Streamable HTTP MCP Server, Inbound/Outbound Webhooks, Mail Protocol Adapters, and `@inbox-zero/api` client. | `apps/web/app/api/v1/*`, `apps/web/app/api/mcp-server/route.ts`, `apps/web/utils/outbound-webhook/call-webhook.ts`, `packages/mail-core/src/protocol/mail-http.ts`, `packages/api/src/client.ts`. | `PARTIAL` | **Exists:** `apps/web/app/api/v1/rules/route.ts#L18-L45` (REST rules CRUD), `apps/web/app/api/mcp-server/route.ts#L8-L18` (MCP Streamable HTTP), `packages/mail-core/src/protocol/mail-http.ts#L266-L311` (`operations/[commandId]` admit/cancel protocol). <br>**Missing:** Public machine API keys cannot authenticate to `mail/v1/operations`, `chat`, or `automation-jobs` (session cookie restricted); MCP requires interactive OAuth 2.0 PKCE browser login (no static machine credentials); outbound webhooks only fire on rule matches, not on general mailbox events. |
| **6** | **Shared Intelligence** | Local knowledge base, user memories, learned sender patterns, and assistant state sync. | `apps/web/app/api/knowledge/route.ts`, `apps/web/prisma/schema.prisma` (`Memory`, `LearnedPattern`, `SenderCategory`), `apps/web/app/api/mail/v1/accounts/[accountId]/assistant-state/route.ts`. | `PARTIAL` | **Exists:** `apps/web/app/api/knowledge/route.ts#L1-L50` (read/write knowledge), `apps/web/utils/ai/assistant/chat-memory-tools.ts#L1-L80` (vector/text memory extraction), `apps/web/app/api/mail/v1/accounts/[accountId]/assistant-state/route.ts#L1-L60` (assistant cursor/state). <br>**Missing:** No external query API for shared intelligence (all endpoints are user-session gated); no connector to enterprise Qdrant/PostgreSQL shared bus; memories are stored locally in Prisma DB. |
| **7** | **Controlled Data Access** | Granular API Key scopes, MCP OAuth scopes, action confirmation gates, phishing hardening, and Standard Webhooks verification. | `apps/web/utils/api-key-scopes.ts`, `apps/web/utils/mcp/http.ts`, `apps/web/utils/actions/assistant-chat-confirmation.ts`, `apps/web/utils/webhooks/verify-standard-webhook.ts`. | `EXISTS` | `apps/web/utils/api-key-scopes.ts#L3-L15` (7 explicit scopes: `STATS_READ`, `RULES_READ`, `RULES_WRITE`, `SETTINGS_READ`, `SETTINGS_WRITE`, `ASSISTANT_CHAT`, `SENDERS_UNSUBSCRIBE`); `apps/web/utils/mcp/http.ts#L37-L55` (JWKS token verification & scope check); `apps/web/utils/actions/assistant-chat-confirmation.ts#L1-L110` (human confirmation gate for destructive email actions). |

---

## 2. Narrative Realization Analysis (Element-by-Element)

### 1. Chief of Staff Agent (`ABSENT`)
The inbox-zero codebase contains zero references to an external Chief of Staff agent, supervisor, or central business coordinator. Searches across filenames and source content for `chief-of-staff`, `chief_of_staff`, and generic `orchestrator` match only local test files (such as `openrouter-cost.test.ts`). The codebase is strictly built as a standalone consumer/prosumer email client and automation hub. However, it exposes structural "sockets" (the REST API, the MCP server, and the `mail-http` command protocol) that can serve as integration receptacles for an external CoS agent once machine authentication is established.

### 2. Independent Specialized Agents (`EXISTS`)
`inbox-zero` represents an independent specialized agent with high domain depth. Within its boundaries, it encapsulates secondary sub-agents:
1. `apps/unsubscribe-worker`: An independent Node.js + Playwright worker executing in a sandbox container that automates multi-step HTTP/browser unsubscribe flows using LLM decision policies (`contracts.ts#L27-L50`).
2. `apps/web/utils/mcp/mcp-agent.ts`: An autonomous multi-turn tool-calling agent executing complex workflows across connected third-party MCP servers (e.g., Notion, GitHub, Composio).

### 3. Internal Orchestrators (`EXISTS`)
The repository is rich in internal orchestration logic designed to run complex tasks without external intervention:
- **Assistant Chat Loop (`utils/ai/assistant/chat.ts`):** Orchestrates multi-turn LLM reasoning, progressive tool disclosure, memory injection, and user confirmation barriers across ~60 eval suites.
- **Automation Jobs Executor (`app/api/automation-jobs/execute/route.ts`):** Coordinates scheduled morning briefs and inbox check-ins via QStash and BullMQ.
- **Bulk Inbox Action Processor (`utils/bulk-inbox-action/process-job.ts`):** Orchestrates leased, batched background execution of bulk actions (e.g., triage 500 emails) with retry tokens and crash recovery.
- **Mail Engine (`packages/mail-core/src/engine.ts`):** Manages local mail state synchronization, optimistic mutation rollbacks, and delta streams.

### 4. Individual UI per Agent (`EXISTS`)
`inbox-zero` realizes individual UI across four distinct client form factors:
1. **Next.js Web UI (`apps/web`):** Full dashboard featuring email triage, assistant chat drawer, rules manager, knowledge base, learned patterns, and API/MCP configuration.
2. **Electron Desktop App (`apps/desktop`):** Dedicated local client communicating via typed IPC (`mail-ipc.ts`) with a background utility-host process and SQLite storage (`packages/mail-sqlite`).
3. **Mobile API Routes (`app/api/mobile/*`):** Tailored API surface supporting mobile push notifications and authentication.
4. **Messaging Channels (`apps/web/app/api/slack/*`, Teams, Telegram):** Interactive conversational surfaces allowing users to receive daily briefs and trigger commands via chat platforms.

### 5. Integration Layer (`PARTIAL`)
While an integration layer exists and is actively maintained, it is bifurcated:
- **Available for Machines:** `apps/web/app/api/v1/` exposes REST endpoints for Rules CRUD, Stats, and Senders Unsubscribe, authenticated via `API-Key` headers (`packages/api/src/client.ts`).
- **Gated Behind Human Sessions:** The core mail operations protocol (`mail/v1/accounts/[accountId]/operations/[commandId]`), assistant chat (`app/api/chat`), and automation jobs (`app/api/user/automation-jobs`) require active user session cookies (`betterAuth`) and cannot be invoked by an external machine via API Key.
- **MCP Server:** Implemented via Streamable HTTP (`app/api/mcp-server/route.ts`), but requires interactive OAuth 2.0 PKCE browser redirection; it lacks non-interactive machine-to-machine client credentials.
- **Webhooks:** Inbound provider webhooks are mature; outbound webhooks exist solely as rule actions (`callWebhook.ts`) rather than a general system event publisher.

### 6. Shared Intelligence (`PARTIAL`)
The agent manages domain-level intelligence locally:
- Knowledge base entries stored in `KnowledgeItem` (`app/api/knowledge`).
- LLM extracted user memories stored in `Memory` (`utils/ai/assistant/chat-memory-tools.ts`).
- Learned sender patterns stored in `LearnedPattern`.
However, this intelligence is isolated within the inbox agent's PostgreSQL instance. It does not export context to, nor consume context from, the federated OS's enterprise PostgreSQL + Qdrant store. Furthermore, there is no public machine API to query or synchronize this knowledge.

### 7. Controlled Data Access (`EXISTS`)
Access control and security boundaries are well-developed:
- **API Key Scopes:** 7 discrete scopes (`ApiKeyScope` in `schema.prisma#L141-L149`) validated on every public request (`api-middleware.ts#L44-L55`).
- **MCP Access Tiers:** Explicit scopes (`mcp:read`, `mcp:write`, `mcp:send`) where `mcp:send` is strictly separated from read/draft tools.
- **Confirmation Barrier:** Destructive email actions (sending emails, modifying rules, executing bulk triage) must pass an explicit user confirmation step (`assistant-chat-confirmation.ts`).
- **Webhook Security:** Outbound rule webhooks are validated against SSRF/private IPs (`resolveSafeExternalHttpUrl`) and signed with HMAC-SHA256 headers (`verify-standard-webhook.ts`).

