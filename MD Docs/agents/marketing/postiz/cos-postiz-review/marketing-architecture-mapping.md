# Marketing-Context Architecture Mapping: Postiz Review

This document maps the seven foundational architectural elements of the **Local-First Federated Multi-Agent Business OS** onto the Postiz marketing agent domain (`business-os/agents/marketing/postiz-app`), citing verified code anchors and establishing status (`EXISTS`, `PARTIAL`, `ABSENT`).

---

## 1. Architectural Element Mapping Table

| # | Architecture Element | Marketing-Domain Counterpart | Candidate Code Anchors Verified in Repo | Status | Code Evidence & Concrete Citations |
|---|---|---|---|---|---|
| **1** | **Chief of Staff (CoS) Agent** | External command & orchestration consumer.<br>Postiz hosts *other* external AI agents and an in-app Copilot, but contains no internal CoS. | • External Agent Program: `.github/agents/*` (claude, codex, cursor, grok, hermes, mcp-server, muse, nanoclaw, openclaw, paperclip)<br>• ChatGPT App: `chatgpt-app-submission.json`<br>• Copilot Controller: `apps/backend/src/api/routes/copilot.controller.ts:42`<br>• Mastra Agent: `libraries/nestjs-libraries/src/chat/load.tools.service.ts:62` | **PARTIAL (As Host)** / **ABSENT (No Internal CoS)** (`FACT`) | Postiz contains **no internal Chief of Staff agent** (negative search for `chief`, `of-staff`, `chief-of-staff` yields 0 files in repo). However, Postiz possesses an advanced external agent onboarding infrastructure: RFC 7591 Dynamic Client Registration (`oauth.controller.ts:42`), RFC 8414 OAuth Authorization Servers (`start.mcp.ts:205`), and a 23-tool MCP registry (`tool.list.ts:25`). A future CoS agent will connect as an external machine principal. |
| **2** | **Independent Specialized Agents** | Postiz itself (social publishing brain) + Chopify (video editing brain).<br>Scope arbitration between Postiz internal clipping and Chopify. | • Postiz Scope: `apps/backend/src/api/routes/posts.controller.ts:1`, `public.integrations.controller.ts:147`<br>• Postiz Cloud Clipping: `apps/orchestrator/src/workflows/clipping.workflow.ts:1`, `clipping.tool.ts:11`, `upload.factory.ts:56`<br>• Chopify Scope: `business-os/agents/marketing/chopify/chopify.py`, `render_clips.py`, `score_clips.py` | **EXISTS** (`FACT`) | Postiz operates autonomously with its own database (`Organization`, `Post`, `Integration`), its own Temporal job queues, and independent runtime. Scope arbitration finding: Postiz contains internal video clipping and generation (`seedance`/EvoLink, `heygen`, `reelfarm`), but these require paid external cloud GPU/AI services (`UploadFactory.clippingEnabled()`). Chopify is the designated local-first video editor; Postiz is the social distribution engine. |
| **3** | **Internal Orchestrators** | Temporal workflow and activity application coordinating post scheduling, retries, media processing, token refreshes, and video generation. | • Temporal Orchestrator App: `apps/orchestrator/src/main.ts:1`, `app.module.ts:1`<br>• 12 Post Workflow Versions: `apps/orchestrator/src/workflows/post-workflows/post.workflow.v1.0.1.ts` through `post.workflow.v1.1.2.ts`<br>• Specialized Workflows: `autopost.workflow.ts`, `clipping.workflow.ts`, `generate.video.workflow.ts`, `process.media.workflow.ts`, `refresh.token.workflow.ts`, `digest.email.workflow.ts`<br>• Publishing Activities: `apps/orchestrator/src/activities/post.activity.ts:515` (`sendWebhooks`), `apps/orchestrator/src/activities/media.activity.ts`<br>• Commands App: `apps/commands/src/tasks/{agent.run.ts, refresh.tokens.ts}` | **EXISTS** (`FACT`) | Postiz features a production-grade, fault-tolerant orchestration layer powered by Temporal. The presence of 12 immutable workflow versions (`post.workflow.v1.0.1` … `v1.1.2`) enforces Temporal determinism rules (`CLAUDE.md:73`). Retries, heartbeats (`HEARTBEAT_TIMEOUT = 3 * 60 * 1000`), and failure classification are strictly implemented (`post.workflow.v1.1.2.ts:27-92`). |
| **4** | **Individual UI** | Next.js App Router frontend for calendar scheduling, analytics inspection, channel connections, webhook settings, and agent chat. | • Frontend Root: `apps/frontend/src/app/(app)/`<br>• Planner / Launches: `(site)/launches/page.tsx`<br>• Analytics: `(site)/analytics/page.tsx`<br>• Agent Chat UI: `(site)/agents/[id]/page.tsx` (`AgentChat`)<br>• Channel Connect: `integrations/connect/[token]/` & `integrations/social/[provider]/`<br>• Webhook Management: `apps/frontend/src/components/webhooks/webhooks.tsx:20`<br>• MCP Client Indicators: `components/public-api/mcp.client.icons.tsx:8` | **EXISTS** (`FACT`) | Complete React/Next.js dashboard (`apps/frontend/`) with independent UX for human marketing managers. Provides direct manual control, calendar visualization, and configuration for integrations, media, webhooks, and billing. |
| **5** | **Integration Layer** | Programmatic interfaces for external machine access: REST API, Model Context Protocol (MCP) server, Mastra agent tools, webhooks, and SDK. | • REST Public API: `apps/backend/src/public-api/routes/v1/public.integrations.controller.ts` (34 endpoints)<br>• MCP Server: `libraries/nestjs-libraries/src/chat/start.mcp.ts:50` (HTTP `/mcp`, `/mcp/:id`, SSE `/sse/:id`, OAuth `/mcp-oauth-*`)<br>• Agent Tools: `libraries/nestjs-libraries/src/chat/tools/tool.list.ts:25` (23 tools)<br>• Outbound Webhooks: `apps/orchestrator/src/activities/post.activity.ts:515`<br>• Inbound Webhook Config: `apps/backend/src/api/routes/webhooks.controller.ts:22`<br>• Social Platform Adapters: `libraries/nestjs-libraries/src/integrations/social/*` (28+ platforms)<br>• Published SDK: `apps/sdk/src/index.ts:15` (`Postiz` class) | **EXISTS / EXTENSIBLE** (`FACT`) | Highly capable integration layer. Postiz supports non-interactive machine execution via both direct API keys (`PublicAuthMiddleware`) and OAuth 2.0 with PKCE (`OAuthController`). It exposes 23 granular Mastra tools over MCP protocol version `2026-07-28` (`start.mcp.ts:150`). Outbound webhooks exist but are currently limited to post-publish events. |
| **6** | **Shared Intelligence** | Central business context, brand voice guidelines, product knowledge, and shared RAG. | • Prisma Models: `libraries/nestjs-libraries/src/database/prisma/schema.prisma` (`Organization`, `Customer`, `Integration`, `Post`)<br>• Mastra Agent Memory: `libraries/nestjs-libraries/src/chat/mastra.store.ts:3` (`PostgresStore`)<br>• LangGraph State Graph: `libraries/nestjs-libraries/src/agent/agent.graph.service.ts:112`<br>• Redis Store: `libraries/nestjs-libraries/src/redis/redis.service.ts`<br>• Qdrant Vector Store: **ABSENT** (`FACT`) | **PARTIAL** (`FACT`) | Postiz possesses local transactional and agent memory storage (PostgreSQL via Prisma, Mastra memory tables `mastra_threads`, `mastra_messages`), and internet RAG via Tavily/LangGraph (`agent.graph.service.ts:20`). However, the shared intelligence layer mandated by the Recommended Architecture (Qdrant vector store + Redis shared event bus) is absent from the repository. |
| **7** | **Controlled Data Access** | Multi-tenancy isolation, permission checks, API authentication, SSRF prevention, and rate limits. | • Organization Scoping: `schema.prisma:11`, `OrganizationService.getOrgByApiKey`<br>• CASL Permissions: `services/auth/permissions/permissions.service.ts:39`, `permissions.guard.ts:16`<br>• SSRF URL Validator: `libraries/nestjs-libraries/src/dtos/webhooks/webhook.url.validator.ts:65`<br>• Throttling & Rate Limits: `ThrottlerRealIpGuard`, `API_LIMIT = 30`<br>• Secret Protection: `CLAUDE.md:79` (credentials never returned in raw Prisma rows) | **EXISTS** (`FACT`) | Multi-tenancy is strongly enforced at the database level by `organizationId` foreign keys across `Post`, `Integration`, `Media`, and `Webhooks`. The `PublicAuthMiddleware` authenticates machine principals and scopes every request to the target organization. SSRF protection is rigorous, though strict HTTPS rules impact local inter-agent networking. |

---

## 2. Per-Element Narrative Analysis

### Element 1: Chief of Staff Agent Surface
Postiz does not implement a Chief of Staff agent. Instead, Postiz is architected as an execution target for external AI agents. It exposes an external-agent program (.github/agents/ with icons for Claude, Cursor, ChatGPT, Grok, Hermes, etc.), an RFC 7591 Dynamic Client Registration endpoint (`POST /oauth/register`), an RFC 8414 Authorization Server discovery metadata endpoint (`/.well-known/oauth-authorization-server`), and an MCP server (`start.mcp.ts`). A CoS agent written in Python (FastAPI/LangGraph) can onboard either via static API key authentication (`Authorization: <api-key>` to `/public/v1/*` or `/mcp`) or via OAuth 2.0 PKCE client registration.

### Element 2: Independent Specialized Agents (Postiz & Chopify)
Postiz represents the social media publishing brain of the Marketing agent. It maintains complete autonomy with its own PostgreSQL database, Temporal task queue, and Next.js UI.
**Scope Arbitration:** Postiz contains an embedded video clipping engine (`apps/orchestrator/src/workflows/clipping.workflow.ts`, `clipping.tool.ts`, `clipping.service.ts`). However, this engine requires paid cloud infrastructure: Cloudflare R2, RunPod Serverless GPU (`postiz-uploader`), Deepgram transcription, and OpenAI (`UploadFactory.clippingEnabled()`). In contrast, Chopify (`business-os/agents/marketing/chopify`) provides a zero-SaaS, local-first Python pipeline with local Whisper and ffmpeg. Therefore, Chopify is the normative component for Capability C2 (*Edit short-form videos*), while Postiz is the normative component for C1 (*Create social posts*) and C3 (*Schedules and publishes*).

### Element 3: Internal Orchestrators (Temporal)
Postiz's internal orchestration is heavily developed using Temporal (`apps/orchestrator/src/`). The post lifecycle is governed by 12 immutable workflow versions (`post.workflow.v1.0.1.ts` to `post.workflow.v1.1.2.ts`). The codebase strictly obeys Temporal determinism: workflow activities cannot change signatures without creating a new workflow version (`CLAUDE.md:73-74`). Workflows manage heartbeat timeouts (3 minutes), execution retries (up to 3 attempts with 2-minute backoff), async status checks for asynchronous social networks, and outbound webhook dispatch upon publishing.

### Element 4: Individual UI
The frontend (`apps/frontend/`) is a Next.js App Router application providing complete self-service UI for human marketing teams. It includes a calendar view for scheduled posts (`(site)/launches/`), channel OAuth connection wizards (`integrations/social/[provider]`), analytics visualization (`(site)/analytics/`), media library (`(site)/media/`), webhook configuration (`components/webhooks/webhooks.tsx`), and a dedicated Copilot chat UI (`(site)/agents/[id]/`). The CoS does not need to duplicate these UI capabilities; the CoS operates headless via the integration layer.

### Element 5: Integration Layer (APIs, MCP, Webhooks, Adapters)
Postiz provides three distinct programmatic interfaces:
1. **REST Public API (`apps/backend/src/public-api/routes/v1/public.integrations.controller.ts`):** 34 endpoints covering post creation, deletion, status checks, media upload, slot discovery, channel listing, and analytics queries.
2. **MCP Server (`start.mcp.ts`):** Implements MCP protocol `2026-07-28` over HTTP POST (`/mcp`, `/mcp/:id`), SSE (`/sse/:id`, `/message/:id`), and OAuth-gated paths (`/mcp-oauth-*`). Exposes 23 tools from `libraries/nestjs-libraries/src/chat/tools/tool.list.ts`.
3. **Outbound Webhooks (`apps/orchestrator/src/activities/post.activity.ts:515`):** Dispatches JSON payloads to registered URLs when a post publishes.
4. **Node/TypeScript SDK (`apps/sdk/`):** Lightweight wrapper over `/public/v1` endpoints.

### Element 6: Shared Intelligence
Shared intelligence in Postiz is currently localized. Application models are stored in PostgreSQL (`schema.prisma`), agent conversation memory is handled by Mastra with PostgreSQL backing (`@mastra/pg`), and content generation is orchestrated with LangGraph and Tavily (`agent.graph.service.ts`). Postiz does **not** connect to a centralized Qdrant vector store or a Redis event bus.

### Element 7: Controlled Data Access
Postiz enforces strict tenant boundaries. All resources (`Post`, `Integration`, `Media`, `Webhooks`) are scoped by `organizationId`. Machine requests are authenticated via `PublicAuthMiddleware`, which rejects invalid tokens and binds the request context to the authenticated organization. `webhook.url.validator.ts` prevents SSRF by blocking loopback, private IPv4/IPv6 CIDRs, and requiring HTTPS.

---

## 3. Explicit Postiz vs Chopify Capability Ownership Statement

Based on actual source-code inspection of both `postiz-app` and `chopify`:

```
========================================================================================
MARKETING AGENT CAPABILITY DECOMPOSITION & COMPONENT OWNERSHIP
========================================================================================
Capability                                  Owner Component    Implementation & Status
----------------------------------------------------------------------------------------
C1: Create social posts (captions/carousels) Postiz             IMPLEMENTED (REST, MCP, LangGraph)
C2: Edit short-form videos (cut reels)       Chopify (Local)    IMPLEMENTED (Python, ffmpeg, local)
                                             Postiz (Cloud-alt) IMPLEMENTED (RunPod GPU/Cloudflare)
C3: Schedules and publishes (best time)      Postiz             IMPLEMENTED (Temporal, 28+ channels)
C4: Analyzes metrics (weekly reports)        Postiz (Raw data)  PARTIAL (REST analytics available;
                                             CoS (Synthesis)    weekly synthesis unbuilt)
========================================================================================
```

- **Overlap Resolution:** Postiz's cloud-clipping subsystem is classified as an optional cloud add-on requiring external SaaS API keys (`UploadFactory.clippingEnabled()`). Chopify is the primary local-first video engine.
- **Bridge Gap:** Currently, zero code exists connecting Chopify's rendered video outputs to Postiz's upload or scheduling endpoints. A bridging adapter is required.

