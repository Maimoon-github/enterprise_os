# Gap, Risk, Dependency, and Modification-Point Analysis: Postiz

This document analyzes the verified gaps, architectural risks, operational dependencies, and prioritized modification points required to enable robust Chief-of-Staff (CoS) integration with the Postiz Marketing Agent (`business-os/agents/marketing/postiz-app`).

---

## 1. Verified Gap Register

Derived directly from the Phase 4 Integration Assessment and codebase inspection:

| # | CoS Operational Lens | Verified Gap Description | Concrete Code Evidence & Baseline | Impact on CoS Command & Delegation | Feasibility Status |
|---|---|---|---|---|---|
| **G1** | **Command / Safety** | **Absence of Enforced Human Approval Barrier for Publishing** | `libraries/nestjs-libraries/src/chat/tools/integration.schedule.post.ts:258` accepts `type: 'now' \| 'schedule' \| 'draft'` and creates immediate releases without requiring approval tokens or human sign-off. | Autonomous CoS or upstream agents can inadvertently publish unvetted content to public brand channels, creating severe brand safety liability. | **VERIFIED FACT** (`FACT`) |
| **G2** | **Orchestration / Reliability** | **Absence of Idempotency Keys on Post Creation Endpoints** | Neither `POST /public/v1/posts` (`public.integrations.controller.ts:147`) nor `schedulePostTool` (`integration.schedule.post.ts:77`, `idempotentHint: false`) checks or persists idempotency keys. | Network timeouts or CoS retries cause duplicate posts to be scheduled or published across all selected social networks. | **VERIFIED FACT** (`FACT`) |
| **G3** | **Monitoring / Observability** | **Incomplete Outbound Event Lifecycle Catalog & Unsigned Webhooks** | `PostActivity.sendWebhooks` (`apps/orchestrator/src/activities/post.activity.ts:515`) only fires upon successful publishing; emits untyped, unsigned JSON payloads (`fetch(webhook.url, ...)` without HMAC header); swallows errors. | CoS cannot observe post scheduling, publishing failures, cancellations, media transcoding completions, or channel disconnections via push events; cannot cryptographically verify event authenticity. | **VERIFIED FACT** (`FACT`) |
| **G4** | **Cross-Component Orchestration** | **Absence of Automated Bridge between Chopify Outputs and Postiz Uploads** | Zero integration code or shared filesystem watcher exists between `business-os/agents/marketing/chopify` (`render_clips.py`) and `postiz-app` (`public.integrations.controller.ts:81`). | CoS cannot delegate end-to-end video marketing campaigns (long video -> cut clips -> scheduled reels) without building an external glue adapter. | **VERIFIED FACT** (`FACT`) |
| **G5** | **Security / Networking** | **Strict SSRF Rules Incompatible with Local Inter-Agent Networking** | `webhook.url.validator.ts:77, 87` strictly enforces `parsed.protocol === 'https:'` and rejects loopback/RFC 1918 private subnets. | In a local-first Docker Compose deployment, Postiz rejects webhook registrations to `http://chief-of-staff:8000` unless `DISABLE_SSRF_PROTECTION=true` is set. | **VERIFIED FACT** (`FACT`) |
| **G6** | **Reporting / Auditability** | **Missing Granular Agent Principal Attribution in Post Audit Records** | `model Post` (`libraries/nestjs-libraries/src/database/prisma/schema.prisma:364`) stores only coarse enum `creationMethod: CreationMethod` (`MCP`, `API`, `WEB`, `CLI`), lacking specific caller ID. | Scorecards and executive audits cannot attribute posts to specific agents (e.g. CoS vs Copilot vs Human Editor) or trace provenance. | **VERIFIED FACT** (`FACT`) |
| **G7** | **Command / Onboarding** | **Absence of OAuth 2.0 Machine-to-Machine Client Credentials Grant** | `apps/backend/src/api/routes/oauth.controller.ts:147` explicitly throws `unsupported_grant_type` for any grant other than `authorization_code`. | CoS cannot authenticate dynamically using standard client credentials (`POST /oauth/token` with `grant_type=client_credentials`); must rely on pre-generated organization API keys. | **VERIFIED FACT** (`FACT`) |

---

## 2. Comprehensive Risk Register

| # | Risk Description | Affected Lens | Likelihood × Impact = Severity | Root Cause in Postiz Codebase | Concrete Mitigation Strategy |
|---|---|---|---|---|---|
| **R1** | **Rogue or Hallucinated Public Social Post Publication** | Command / Orchestration | Medium × Critical = **HIGH** | `schedulePostTool` allows `type: 'now'` without approval barrier (`integration.schedule.post.ts:258`). | Enforce an approval gate: configure CoS permissions so machine principals can only create `type: 'draft'`; require explicit human or CEO confirmation token for `schedule` or `now`. |
| **R2** | **Duplicate Posting from Retried Network Requests** | Orchestration | High × High = **HIGH** | Lack of idempotency key processing in `posts.service.ts:createPost` and `IntegrationSchedulePostTool`. | Introduce client-supplied `Idempotency-Key` header on `POST /public/v1/posts` and `clientSubmissionId` on `schedulePostTool`; store in Redis with 24h TTL. |
| **R3** | **Blind Execution Failures from Swallowed Webhook Errors** | Monitoring | High × Medium = **MEDIUM** | `PostActivity.sendWebhooks` wraps fetch in empty catch block (`post.activity.ts:552`); only publishes on success. | Introduce reliable outbound webhook dispatch with exponential retries and dead-letter queue via Temporal activity; emit explicit `post.failed` events. |
| **R4** | **Rejection of Local CoS Webhook Subscriptions (SSRF)** | Monitoring / Command | High × High = **HIGH** | `webhook.url.validator.ts:77` rejects non-HTTPS protocols and private IP subnets. | Set `DISABLE_SSRF_PROTECTION=true` in `docker-compose.yaml` for internal development, or allow HTTP for internal Docker network aliases (`*.internal`, `chief-of-staff`). |
| **R5** | **Platform API Rate-Limiting & Token Expiration Storms** | Command / Delegation | Medium × High = **MEDIUM** | 35 social platform adapters share one rate limit per integration (`ThrottlerRealIpGuard`, `API_LIMIT = 30`). | Respect platform throttling metadata returned in `validation.schemas.helper.ts`; leverage `refresh.token.workflow.ts` before burst scheduling. |
| **R6** | **Accidental Deletion of Critical Social Posts by Machine Principals** | Command | Low × High = **MEDIUM** | `DeletePostTool` (`delete.post.tool.ts:72`) executes irreversible deletions without confirmation prompt. | Scope CoS MCP credentials to read and draft tools only; restrict `deletePostTool` to human administrators. |
| **R7** | **Postiz vs Chopify Redundant Video Processing Conflict** | Orchestration | Medium × Medium = **MEDIUM** | Postiz ships its own cloud clipping (`clipping.workflow.ts`) while Chopify runs local clipping. | Establish strict architectural boundary: designate Chopify as sole video clipping engine; treat Postiz as pure distribution platform. |

---

## 3. Dependency Map & Operational Load Profile

### 3.1 Runtime & Infrastructure Dependencies

| Dependency Component | Role in Postiz Execution | Configuration / Port | Operational Load Impact under CoS | Failure Mode / Blast Radius |
|---|---|---|---|---|
| **Temporal Server** | Manages post scheduling, versioned workflows (`v1.1.2`), retries, and media jobs. | Port 7233 (`docker-compose.yaml:15`) | **HIGH.** CoS campaign delegation increases workflow execution count and timer queues. | If Temporal halts, scheduled posts are paused; publishing stops completely. |
| **PostgreSQL 17** | Stores relational entities (`Organization`, `User`, `Post`, `Integration`, `Media`, `Webhooks`). | Port 5432 (`docker-compose.yaml:143`) | **MEDIUM.** CoS post queries and status polling add read/write load. | Total system failure if primary DB becomes unreachable. |
| **Redis 7.2** | Caches tokens, manages rate-limiting keys, and stores OAuth authorization state. | Port 6379 (`docker-compose.yaml:154`) | **MEDIUM.** High API request volume increases Redis key access and throttler checks. | Auth callbacks fail; rate limiters fail closed or open. |
| **Cloud Storage** | Stores media attachments, video thumbnails, and generated clips (Local or Cloudflare R2). | Port 4007 (`/uploads`) or R2 Bucket | **HIGH.** Bulk media imports from CoS/Chopify add I/O and storage consumption. | Posts fail validation if attachment URLs cannot be read. |
| **External Social APIs** | Meta (FB/IG), X, LinkedIn, TikTok, YouTube, Reddit, Discord, Slack, etc. | HTTPS outbound | **HIGH.** Automated posting consumes social network API rate quotas. | Account suspension or post failure if platform rate limits are breached. |
| **OpenAI API** | Powering DALL-E image generation, post copy generation, and LangGraph agent graphs. | `OPENAI_API_KEY` | **MEDIUM.** Used on-demand for content generation tools. | Image and text generation fail gracefully; core publishing unaffected. |
| **RunPod / Deepgram** | Optional cloud clipping and transcription endpoints (`UploadFactory.clippingEnabled()`). | `RUNPOD_API_KEY`, `DEEPGRAM_API_KEY` | **NONE (If Chopify used).** Only active if Postiz cloud clipping is called. | Cloud clipping fails if RunPod endpoints are cold or out of credits. |

---

## 4. Prioritized Modification Points (Minimal-Touch Architecture)

Candidate change sites are categorized into **Integration-Only** (zero repo modifications, external CoS adaptation), **Additive** (extending existing registries without touching core logic), and **Invasive** (modifying existing workflows or database models).

```
====================================================================================================
PRIORITIZED INTEGRATION MODIFICATION ROADMAP
====================================================================================================
Rank  Site / File                                         Category          Touch Level  Blocked By
----------------------------------------------------------------------------------------------------
1     External CoS Adapter (Python FastAPI / SDK client)  Integration-Only  Zero Touch   None
2     tools/tool.list.ts + chat/tools/ (CoS Tools)        Additive          Minimal      None
3     activities/post.activity.ts (Signed Webhooks)       Additive          Low          None
4     webhook.url.validator.ts (Local SSRF Bypass)        Additive          Minimal      None
5     posts.service.ts & integration.schedule.post.ts     Additive          Medium       None
      (Idempotency Key & Approval Gate)
6     Chopify-to-Postiz Ingestion Bridge                  Additive          Medium       Chopify Adapter
7     schema.prisma (Agent Principal Audit Provenance)    Invasive          Medium       DB Migration
====================================================================================================
```

### Detailed Evaluation of Ranked Modification Points

#### 1. External CoS Adapter (Integration-Only — Zero Repo Touch)
- **Concept:** CoS interacts with Postiz purely as an external API consumer using Postiz's existing `/public/v1/*` REST endpoints and static Organization API keys (`Authorization: <api-key>`).
- **Leverage:** Requires zero changes to the `postiz-app` repository. CoS calls `POST /public/v1/upload` to upload media and `POST /public/v1/posts` with `type: 'draft'` to safely queue content.
- **Limitation:** CoS must poll for post updates since outbound webhooks only emit on publish.

#### 2. CoS-Scoped Tool Additions (`libraries/nestjs-libraries/src/chat/tools/` — Additive)
- **Concept:** Register dedicated CoS tools in `tool.list.ts:25`, such as `campaignDraftTool` and `analyticsQueryTool`, which enforce `type: 'draft'` and return structured campaign metrics.
- **Leverage:** Follows Postiz's existing Mastra tool registry pattern (`AgentToolInterface`) without altering existing tools.

#### 3. Outbound Signed Webhooks (`apps/orchestrator/src/activities/post.activity.ts` — Additive)
- **Concept:** Update `PostActivity.sendWebhooks` to dispatch an HMAC signature header (`X-Postiz-Signature: sha256=...`) and expand emission to include `post.scheduled`, `post.failed`, and `media.ready`.
- **Leverage:** Transforms Postiz from a polling target into a real-time event publisher for the CoS monitoring lens.

#### 4. SSRF Local Bypass (`libraries/nestjs-libraries/src/dtos/webhooks/webhook.url.validator.ts` — Additive)
- **Concept:** Modify `isSafePublicHttpsUrl` to allow `http://` and container hostname resolutions when running in internal Docker networks (e.g. when `NODE_ENV !== 'production'` or `ALLOW_INTERNAL_WEBHOOKS=true`).
- **Leverage:** Unblocks local webhook delivery to the CoS agent in Docker Compose without completely disabling SSRF protection for third-party URLs.

#### 5. Idempotency Key & Approval Gates (`posts.service.ts` & `integration.schedule.post.ts` — Additive)
- **Concept:** Add optional `idempotencyKey` parameter to `createPost` and `schedulePostTool`, caching the generated `postId` in Redis. Add an `isApproved` flag to prevent direct publishing when invoked by machine credentials.
- **Leverage:** Completely neutralizes Risks R1 (rogue publishing) and R2 (duplicate posting).

#### 6. Chopify-to-Postiz Ingestion Bridge (Additive / Cross-Repo)
- **Concept:** Create a lightweight Python bridge in `business-os/agents/marketing/` that watches Chopify's rendered output directory, calls Postiz's `POST /public/v1/upload-from-url` or `POST /public/v1/upload`, and creates a draft post.
- **Blocked By:** Requires CoS orchestration layer or a shared filesystem event watcher.

#### 7. Agent Provenance in Post Audit Records (`schema.prisma` — Invasive)
- **Concept:** Add `agentPrincipalId String?` and `clientMetadata Json?` to `model Post`, with a Prisma migration.
- **Leverage:** Enables full auditability and scorecard KPI attribution for agent-generated posts.
- **Invasive Penalty:** Requires altering the shared database schema and running a Prisma migration in production.

