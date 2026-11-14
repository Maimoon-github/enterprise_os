# Phase 1: Source-Comprehension Plan (Agent Info & Recommended Architecture)

**Review Target:** Finance Agent (`business-os/agents/finance`)  
**Project Base:** `OpenBooks/` monorepo (Yarn 4, TypeScript, Fastify, React, MySQL 8.4)  
**Baseline Documents:** 
- `/enterprise_os/MD Docs/Agents info.md`
- `/enterprise_os/MD Docs/Recommended architecture.md`
- `/enterprise_os/MD Docs/agents/finance/File Tree - finance.md`
- `/enterprise_os/business-os/agents/finance/README.md`

---

## 1. Baseline Extraction: Seven Architecture Elements

The foundational documents establish a **Local-First Federated Multi-Agent Business OS** governed by five architectural layers and seven core elements. Below is the normative extraction from the baseline sources.

| # | Architecture Element | Intent & Responsibilities (Verbatim & Normative) | Boundaries (What it may / may not do) | Interface Expectations (Exposes / Consumes) | Dependencies |
|---|---|---|---|---|---|
| **1** | **Chief of Staff (CoS) Agent** | "runs your other agents, briefs you daily" (`Agents info.md`). Responsibilities: Send CEO brief (revenue, leads, cash, top 3), delegate to agents (marketing, sales, finance), track open loops, build scorecard (`Agents info.md`). "Command, delegation, orchestration, monitoring and reporting" (`Recommended architecture.md`). | "Agents don't need to know each other. The Chief of Staff coordinates their workflows through the integration layer" (`Recommended architecture.md`). Must operate across federated repos without merging codebases into a monolith. | Exposes: Daily executive brief, CEO scorecard, task status. Consumes: Domain APIs, MCP servers, webhooks, Redis events from independent agents. | Python + LangGraph + FastAPI (`Recommended architecture.md`), Redis event bus, Shared Knowledge (PostgreSQL + Qdrant). |
| **2** | **Independent Specialized Agents** | "Specialized execution, internal orchestrators and individual UIs" (`Recommended architecture.md`). Finance Agent specific: "Codes expenses, chases invoices, tracks cash... Categorizes expenses... Chases unpaid invoices (polite reminders at 3, 7, and 14 days late)... Reconciles accounts... Forecasts cash flow (weekly forecast and low-balance alerts)" (`Agents info.md`). | "Each application retains its own environment, database, UI and internal orchestration" (`Recommended architecture.md`). Must not be bypassed by direct database access from other agents or CoS. | Exposes: Programmatic integration layer (REST API, MCP host, webhooks, provider adapters). Consumes: Domain events, bank feeds, payment processor webhooks, user/CoS instructions. | Dedicated environment, database (MySQL 8.4 in OpenBooks), local language runtime (Node.js/TypeScript). |
| **3** | **Internal Orchestrators** | "internal orchestrators" (`Recommended architecture.md`). Specialized engines executing domain jobs, loops, and async workflows within the agent boundary. | Strictly scoped within the agent. CoS does not micromanage individual steps of internal batch jobs, reconciliation loops, or posting cascades; CoS delegates domain goals and tracks status. | Exposes: Job submission, queue polling, task status, execution triggers. Consumes: Domain entities, internal event bus/outbox, provider feeds. | Worker runtime (`entrypoints/worker.ts`), SQS or in-process queue adapter, scheduled ticks (`startDailyTick`). |
| **4** | **Individual UI per Agent** | "individual UIs" (`Recommended architecture.md`). Dedicated human-facing frontend retained alongside the central dashboard. | Retained for human operators, accountant workflows, manual reviews, and domain-specific oversight: "Keep a Next.js dashboard for unified visibility, while preserving each agent's native language... and individual UIs" (`Recommended architecture.md`). | Exposes: Web application for human clerks, accountants, and approvers. Consumes: Agent backend REST API, authenticated cookies/sessions. | Vite + React SPA (`packages/web`), TailwindCSS, React Router, TanStack Query. |
| **5** | **Integration Layer** | "APIs, MCP, webhooks and adapters for communication" (`Recommended architecture.md`). The sole communication channel connecting CoS and external systems to the agent. | "Exposes capabilities only via API / MCP / webhook / adapter. Orchestrated exclusively by `chief-of-staff/`" (`business-os/agents/finance/README.md`). Must enforce strict authentication, tenant isolation, and idempotency. | Exposes: REST API (Fastify `/v1/*`), MCP server (`POST /mcp`), change feed (`GET /v1/change-feed`), inbound webhooks. Consumes: API keys, OAuth tokens, JSON-RPC calls. | Fastify transport, `@openbooks/plugin-api` SDK, JSON-RPC 2.0 parser, OpenAPI 3.1 specification. |
| **6** | **Shared Intelligence** | "Central knowledge, business context, RAG and controlled data access... PostgreSQL + Qdrant: Shared business data and knowledge" (`Recommended architecture.md`). | Cross-agent business context (e.g. customer status, product pricing, vendor terms, financial thresholds). Must not breach tenant isolation or expose raw financial ledger entries inappropriately. | Exposes: Semantic context, shared embeddings, business summaries. Consumes: Curated financial metrics (revenue, cash, aging) published by the finance agent. | PostgreSQL, Qdrant vector database, embedding models. |
| **7** | **Controlled Data Access** | "controlled data access" (`Recommended architecture.md`). Security, tenancy, permission catalog, and auditability governance. | Prevents unauthorized mutation or exfiltration of financial records. In double-entry accounting, direct journal writes outside the kernel are strictly forbidden (`openbooks/no-journal-writes`). | Exposes: Tenant-scoped queries, role-gated endpoints, immutable audit logs (`audit.read`). Consumes: Authenticated principal credentials, live membership resolution. | MySQL app grants (`0999_app_grants`), `tenantDb()` query boundaries, Kysely transaction scopes, AES-256-GCM field encryption. |

---

## 2. Finance-Domain Interpretation

1. **Chief of Staff (Finance Domain Sense):** An external supervisory orchestrator (running outside `OpenBooks/` in Python/LangGraph) that commands and monitors the finance system. It receives daily cash summaries and overdue receivables for the CEO brief, delegates high-level financial goals (e.g., "Run dunning cycle for overdue invoices", "Prepare batch bill payments for approval", "Run month-end close checklist"), and monitors ledger health and open review queues.
2. **Independent Specialized Agent (Finance Domain Sense):** The complete `OpenBooks` accounting platform. It maintains double-entry integrity, enforces accounting standards (accrual and cash-basis), tracks receivables (invoices, dunning), payables (bills, disbursements), banking reconciliations, tax compliance (1099, sales tax), and fixed assets.
3. **Internal Orchestrator (Finance Domain Sense):** The background job engines and daily tick schedulers inside OpenBooks:
   - The automations engine (`modules/automations/engine.ts`, `job.ts`, `queue.service.ts`) managing the agent work queue (Initiative Q, OB-200…210).
   - The Pay Bills pipeline (`modules/pay-bills/queue.service.ts`, `issue.service.ts`, `rail-disbursements.service.ts`).
   - The recurring document sweeps (`recurring-invoices`, `recurring-journals`, `fixed-assets`).
   - The bank feed synchronization and transaction matching pipelines (`bank-feeds`, `banking`).
   - The payment processor webhook and balance polling backstop (`modules/payments-processing`).
4. **Individual UI (Finance Domain Sense):** The React/Vite single-page application (`packages/web`) providing complete financial screens: Chart of Accounts, General Ledger, Journal Entry with draft editor, Agent Proposals Review Queue (`/agent-proposals`), Work Items (`/work-items`), Pay Bills & Disbursements, Invoicing & Dunning, Bank Reconciliation, and Financial Reports (P&L, Balance Sheet, Trial Balance, Audit Trail).
5. **Integration Layer (Finance Domain Sense):** The four programmatic channels through which CoS interacts with OpenBooks:
   - **REST API:** 48 route files in `packages/server/src/transport/routes/` covering CRUD on financial entities, authenticated via API keys (`obk_...`) or OAuth tokens (`oba_...`) with mandatory `Idempotency-Key` headers on writes.
   - **MCP Server:** In-process JSON-RPC 2.0 host at `POST /mcp` exposing 8 tools (5 reads: `accounts.list`, `contacts.list`, `invoices.list`, `bills.list`, `reports.trial_balance`; 1 propose-only write: `journal.propose`; 2 work queue tools: `work_queue.poll`, `work_queue.submit_proposal`).
   - **Events & Outbox:** Transactional outbox (`event_log`, `event_positions`) queried via `GET /v1/change-feed` using keyset cursors.
   - **Extension SDK:** `@openbooks/plugin-api` defining actors, permissions, posting primitives, and provider seams.
6. **Shared Intelligence (Finance Domain Sense):** The curated metrics and financial state OpenBooks feeds to the enterprise knowledge base (PostgreSQL + Qdrant) — daily cash balance, AR aging summary, revenue velocity, low-balance warnings, and vendor terms — without exposing raw PII or unposted internal journal drafts.
7. **Controlled Data Access (Finance Domain Sense):** The strict financial security architecture:
   - Database-level immutability (`0999_app_grants.ts` grants `openbooks_app` NO `UPDATE` or `DELETE` on `journals` and `journal_lines`).
   - Code-level immutability enforced by ESLint rule `openbooks/no-journal-writes` (only `posting.repository.ts` may insert).
   - Double-entry balance invariant ($$\sum \text{Debits} == \sum \text{Credits}$$ in exact `bigint` minor units, verified in `posting.service.ts`).
   - Closed fiscal period locking (`assertPostable`, `FOR UPDATE` on `periods`).
   - Multi-tenant isolation (`tenantDb(orgId)` with composite keys `(org_id, id)`).
   - Granular 78-code permission catalog (`modules/permissions/catalog.ts`).
   - Separation of duties (e.g. `pending_payments.write` vs `disbursements.issue`).

---

## 3. Project Glossary Reconciliation

Reconciliation between the OS-wide architectural glossary and OpenBooks' own `docs/glossary.md`:

| Architecture Concept | OpenBooks Glossary Equivalent (`docs/glossary.md`) | Alignment & Reconciliation Analysis |
|---|---|---|
| **Chief of Staff (CoS)** | *Not defined in `docs/glossary.md`.* | **FINDING (ABSENT in Repo):** OpenBooks has no internal concept of a "Chief of Staff". In OpenBooks' design, third-party agents connect as external clients via OAuth 2.1 or API keys, or interact via MCP (`modules/mcp`) and the Work Queue (OB-200…210). |
| **Specialized Agent** | **MCP / Model Context Protocol** & **Draft / Agent Review Queue** | Aligned. OpenBooks models an external agent as an untrusted client that connects over MCP or API, polls work items, and submits journal drafts to the `agents.review` queue. OpenBooks holds no LLM credentials internally (Decision D-100). |
| **Internal Orchestrator** | **Provider seam**, **Role (process role)**, **Dunning**, **Reconciliation** | Aligned. Internal orchestration in OpenBooks consists of background jobs managed by the worker role (`OPENBOOKS_ROLE=worker`), the in-process/SQS queue adapter, and daily tick schedulers (`startDailyTick`). |
| **Individual UI** | **The gate**, **Drift**, Web screens (`packages/web`) | Aligned. Dedicated React SPA providing full UI for books, reconciliation, approvals, and reports, separate from any future centralized CoS dashboard. |
| **Integration Layer** | **Idempotency key**, **Capability token**, **Change feed / event log**, **External ref**, **MCP** | Highly aligned and rigorously specified. OpenBooks enforces `Idempotency-Key` headers on all write endpoints, maintains a transactional outbox (`event_log`), exposes resumable change feed, and hosts an MCP endpoint. |
| **Shared Intelligence** | **Trial balance**, **Dimension**, **Control account**, **Subledger** | Partially aligned. In OpenBooks, "intelligence" is the authoritative financial truth (the trial balance as oracle). Sharing with external vector stores/RAG is not built-in and must be bridged via the integration layer. |
| **Controlled Data Access** | **Org (tenant)**, **Tenant table**, **`tenantDb()` / `systemDb()`**, **Minor units**, **Actor provenance**, **Role (permission role)** | Exceptionally aligned. OpenBooks enforces strict tenant boundaries, append-only journals at MySQL grant level, `bigint` minor units without float rounding, and full actor provenance (`user`, `automation`, `agent`). |

---

## 4. Open Questions & Ambiguities (`OPEN`)

Where baseline sources are silent on finance-specific integration mechanisms, the following items are flagged for architecture owners:

1. **[OPEN-1] Machine Identity & Actor Type for CoS:** When CoS issues commands, does it authenticate as an API key (`actorType = 'automation'`, `userId = null`), or as an OAuth client on behalf of a specific user (`actorType = 'user'`), or should OpenBooks formalize a dedicated `actorType = 'agent'` with a CoS machine identity?
2. **[OPEN-2] Money-Moving Autonomy vs Human-in-the-Loop:** Baseline documents state CoS "delegates to agents" and "chases invoices", but in OpenBooks, money-moving operations (`disbursements.issue`, `journals.post`) require human approval (`agents.review` + `journals.post`, or Owner role). Does CoS have permission to directly issue disbursements, or must all disbursements and postings remain staged for human review?
3. **[OPEN-3] Outbound Event Push Mechanism:** OpenBooks currently provides only a pull-based change feed (`GET /v1/change-feed`). Does the target architecture require OpenBooks to push outbound webhooks or publish directly to a Redis event bus, or is CoS expected to poll the change feed?
4. **[OPEN-4] Shared Intelligence Sync Protocol:** What is the authoritative protocol for synchronizing OpenBooks financial metrics (cash position, accounts receivable aging, P&L summaries) into the centralized PostgreSQL + Qdrant shared intelligence layer? Is this scheduled via a CoS ETL job pulling from OpenBooks reporting APIs?

