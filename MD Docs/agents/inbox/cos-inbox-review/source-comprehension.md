# Phase 1: Source-Comprehension Plan (Agent Info & Recommended Architecture)

**Review Target:** Inbox Agent (`business-os/agents/inbox`)  
**Project Base:** `inbox-zero/` monorepo  
**Baseline Documents:** 
- `/enterprise_os/MD Docs/Agents info.md`
- `/enterprise_os/MD Docs/Recommended architecture.md`
- `/enterprise_os/MD Docs/agents/inbox/prompt.md`

---

## 1. Baseline Extraction: Seven Architecture Elements

The foundational documents establish a **Local-First Federated Multi-Agent Business OS** governed by five architectural layers and seven core elements. Below is the normative extraction from the baseline sources.

| # | Architecture Element | Intent & Responsibilities (Verbatim & Normative) | Boundaries (What it may / may not do) | Interface Expectations (Exposes / Consumes) | Dependencies |
|---|---|---|---|---|---|
| **1** | **Chief of Staff (CoS) Agent** | "runs your other agents, briefs you daily" (`Agents info.md`). Responsibilities: Send CEO brief, delegate to agents (marketing, sales, finance, inbox), track open loops, build scorecard (`Agents info.md`). "Command, delegation, orchestration, monitoring and reporting" (`Recommended architecture.md`). | Coordinates agent workflows; does not replace specialized domain execution. Must operate across federated repos without merging codebases. | Exposes: Daily executive brief, task status, KPI dashboard. Consumes: Domain APIs, MCP servers, webhooks, Redis events from independent agents. | Python + LangGraph + FastAPI (`Recommended architecture.md`), Redis event bus, Shared Knowledge (Postgres + Qdrant). |
| **2** | **Independent Specialized Agents** | "Specialized execution, internal orchestrators and individual UIs" (`Recommended architecture.md`). Inbox Agent specific: "Sorts email, drafts replies, books meetings. Triages your inbox... Drafts replies... Schedules meetings... Sends a morning brief" (`Agents info.md`). | "Agents don't need to know each other" (`Recommended architecture.md`). Each agent retains autonomy, private DB, and distinct domain logic. | Exposes: Domain integration surfaces (REST APIs, MCP server, webhooks, adapters). Consumes: Domain triggers, user prompts, external provider APIs (Google/Microsoft). | Agent-specific tech stack (Inbox: TypeScript/Next.js/Node/pnpm/Turbo), provider mail protocols. |
| **3** | **Internal Orchestrators** | Execution engines internal to each specialized agent that coordinate multi-step sub-tasks, local tool calls, or background loops. | Scoped strictly inside the agent's boundary. CoS does not micromanage the internal sub-steps; it delegates tasks and tracks status. | Exposes: Job submission/polling or agent loop invocation. Consumes: Internal domain tools, database models, internal workers. | Local database, local worker runtimes (e.g., BullMQ, Next.js server actions). |
| **4** | **Individual UI per Agent** | Standalone visual management surface dedicated to each agent's configuration, human-in-the-loop approvals, and detailed audit trails. | Retained alongside the central dashboard: "Each application retains its own environment, database, UI and internal orchestration" (`Recommended architecture.md`). | Exposes: Web/desktop client UI for human operators. Consumes: Agent internal APIs, server actions, local store. | Frontend frameworks (Next.js App Router, TailwindCSS, Electron, shadcn/ui). |
| **5** | **Integration Layer** | "APIs, MCP, webhooks and adapters for communication" (`Recommended architecture.md`). Receptacle enabling CoS to command, delegate, orchestrate, monitor, and report. | Must not blur domain boundaries. Must provide secure machine access without relying on interactive human browser sessions. | Exposes: HTTP REST endpoints, Streamable HTTP MCP tools, signed outbound/inbound webhooks, client adapters. Consumes: Machine tokens / API keys, standard payloads. | Network transport, OAuth 2.0 / API key authentication, serialization (JSON/Zod). |
| **6** | **Shared Intelligence** | "Central knowledge, business context, RAG and controlled data access... PostgreSQL + Qdrant: Shared business data and knowledge" (`Recommended architecture.md`). | Cross-agent business context (e.g. brand voice, customer records, company policies). Must not leak raw private mailbox data across agents. | Exposes: Semantic search, vector embeddings, shared context queries. Consumes: Curated knowledge extracted or synchronized from agents. | PostgreSQL, Qdrant vector database, embedding pipelines. |
| **7** | **Controlled Data Access** | Security, scope governance, and policy enforcement preventing unauthorized data leakage or over-privileged agent actions. | Strictly bounds what external agents (including CoS) can view or execute. Gated by explicit permission scopes and confirmation tiers. | Exposes: Scopes query (`/scopes`), capabilities query (`/capabilities`), consent tiers. Consumes: Authenticated principal tokens, actor audit context. | Better-Auth, API Key validation, Zod request validators, encryption salts. |

---

## 2. Inbox-Domain Interpretation

1. **Chief of Staff (Inbox Domain Sense):** An external supervisory principal that does not live inside `inbox-zero`. It issues high-level directives to the inbox agent (e.g., "Summarize unread high-priority emails from investor X", "Apply triage rule for client refunds", "Prepare morning executive brief"), monitors execution progress, and collects inbox analytics for the daily CEO brief.
2. **Independent Specialized Agent (Inbox Domain Sense):** The autonomous `inbox-zero` application itself, encompassing mail ingestion, synchronization, classification, automated rules evaluation, draft generation, calendar scheduling, and automated unsubscribe workflows.
3. **Internal Orchestrator (Inbox Domain Sense):** The internal execution loops that coordinate multi-step inbox workflows: (a) the conversational assistant chat loop (`utils/actions/assistant-chat.ts` and `utils/ai/assistant/chat.ts`), (b) the background automation job executor (`app/api/automation-jobs/execute` + `utils/automation-jobs/execute.ts`), (c) the rules engine (`utils/actions/ai-rule.ts` + webhook processing), (d) the bulk inbox action worker (`utils/bulk-inbox-action/process-job.ts`), and (e) the mail core operational state machine (`packages/mail-core/src/engine.ts`).
4. **Individual UI (Inbox Domain Sense):** The Next.js web application (`apps/web/app/(app)/[emailAccountId]/*`), the Electron desktop application (`apps/desktop`), mobile routes, and messaging channel bots (Slack, Teams, Telegram) through which human users read email, inspect rules, view analytics, and interact with the AI assistant.
5. **Integration Layer (Inbox Domain Sense):** The collective programmatic surfaces of `inbox-zero`: (a) Public REST API (`apps/web/app/api/v1/*` guarded by `API-Key`), (b) Streamable HTTP MCP Server (`apps/web/app/api/mcp-server/route.ts` guarded by OAuth 2.0 PKCE Bearer tokens), (c) Webhook system (inbound provider webhooks from Google/Microsoft/Slack and outbound Standard Webhook rule-actions in `utils/outbound-webhook/call-webhook.ts`), and (d) Client packages (`packages/api` typed SDK and `packages/mail-core/src/protocol/mail-http.ts`).
6. **Shared Intelligence (Inbox Domain Sense):** The inbox agent's knowledge base (`apps/web/app/api/knowledge`), persistent user memories (`prisma.memory`), learned triage patterns (`prisma.learnedPattern`), and sender categorization metadata (`prisma.senderCategory`), which feed context to the LLM and can be synchronized with the enterprise-wide PostgreSQL + Qdrant layers.
7. **Controlled Data Access (Inbox Domain Sense):** The defensive boundaries governing mail operations: granular API key scopes (`ApiKeyScope` enum: `RULES_READ`, `RULES_WRITE`, `STATS_READ`, etc.), MCP OAuth scopes (`mcp:read`, `mcp:write`, `mcp:send`), phishing-hardening guards (`chat-response-guard.ts`), human-in-the-loop action confirmation gates (`chat/confirm-email-action`), and Standard Webhook HMAC signature verification (`verify-standard-webhook.ts`).

---

## 3. Project Glossary (Normalized Architecture Terms)

- **Agent (Specialized):** A self-contained, domain-specific autonomous software system possessing its own runtime, persistent storage, internal orchestration, and dedicated UI.
- **Chief of Staff (CoS):** The federated coordinator agent running in Python/FastAPI/LangGraph responsible for command dispatch, cross-agent workflow sequencing, operational monitoring, and aggregate reporting.
- **Internal Orchestrator:** A component within an agent that plans and coordinates local sub-tasks (e.g., LLM tool execution, background chunk processing, batch rule evaluation).
- **Integration Layer:** The boundary interfaces (REST APIs, MCP endpoints, webhooks, adapters) exposed by an agent to allow programmatic machine interaction without human browser sessions.
- **Shared Intelligence:** The shared enterprise context (business rules, brand persona, customer CRM state, shared embeddings) maintained across agents via central PostgreSQL + Qdrant.
- **Controlled Data Access:** The authorization and validation mechanisms enforcing principle of least privilege, preventing unauthorized privilege escalation or unrestricted mailbox exfiltration.

---

## 4. Open Questions & Baseline Ambiguities (`OPEN`)

1. **`OPEN-01` (CoS Machine Identity Model):** The baseline sources specify that CoS delegates to agents via "APIs, MCP, or lightweight adapters", but do not specify whether the CoS authenticates as a system-level machine tenant, an impersonated human user, or via service-to-service mTLS / signed JWTs.
2. **`OPEN-02` (Event Bus Protocol & Ownership):** `Recommended architecture.md` specifies "Redis: Events and asynchronous communication", but `inbox-zero` currently uses BullMQ internally with private job queues (`automation-jobs`, `email-digest-all`). Does CoS subscribe directly to a shared Redis pub/sub channel, or does Inbox Zero publish events outward via webhook?
3. **`OPEN-03` (Delegation Job Lifecycle):** What is the exact contract for CoS delegating a long-running batch inbox task (e.g., "Clean and label last month's cold pitches")? Currently, bulk actions exist as `BulkInboxActionJob`, but they are initiated only via human assistant chat tool calls or server actions.

