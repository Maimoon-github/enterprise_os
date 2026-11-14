# Integration-Layer Assessment: Chief-of-Staff Readiness Matrix

This document provides the rigorous evaluation of Postiz's four integration channels against the five Chief-of-Staff (CoS) operational lenses. Every cell is assigned an evidence-backed readiness rating based on actual code inspection.

---

## 1. Readiness Rating Scale Definition

- **0 – Absent:** No programmatic surface found; verified by negative code searches.
- **1 – Partial:** Surface exists but is not machine-consumable as-is (e.g. interactive-only auth, unhandled errors, missing contracts, missing status).
- **2 – Ready:** Documented contract, non-interactive machine authentication, tenant-scoped access, verified operational.
- **3 – Extensible:** Ready *and* architecturally designed for external machine consumers (versioned contracts, registry patterns, per-org tool scoping, outbound events, client SDK).

---

## 2. Filled 4 × 5 Integration Readiness Matrix

| Integration Channel \ CoS Lens | Command<br>(Issue/Authorize Actions) | Delegation<br>(Hand off Task, Track Status) | Orchestration<br>(Multi-step, Idempotent, Cancel) | Monitoring<br>(Events, State Changes, Health) | Reporting<br>(Metrics, Audit Trails) |
|---|---|---|---|---|---|
| **Channel 1: REST API + SDK**<br>(`public.integrations.controller.ts`, `apps/sdk`) | **Rating: 2 (Ready)**<br>• Code: `public.integrations.controller.ts:147` (`POST /public/v1/posts`), `:81` (`POST /public/v1/upload`)<br>• Auth: API key or `pos_` OAuth via `PublicAuthMiddleware:24`<br>• SDK: `apps/sdk/src/index.ts:21` (`post()`) | **Rating: 2 (Ready)**<br>• Code: `GET /public/v1/posts` (`:134`), `GET /public/v1/media/:id/status` (`:283`), `GET /public/v1/clipping/:id` (`:578`)<br>• Returns post arrays, upload transcoding status, and video clipping job state | **Rating: 1 (Partial)**<br>• Multi-step: Upload → Create Post supported<br>• Cancellation: `DELETE /public/v1/posts/:id` (`:234`) and `/group/:group` (`:244`)<br>• **Gap:** Zero idempotency key support on `POST /posts` (negative search `idempotency-key`) | **Rating: 1 (Partial)**<br>• Health: `GET /is-connected` (`:253`)<br>• Notifications: `GET /public/v1/notifications` (`:528`)<br>• **Gap:** Polling-only; no streaming REST events | **Rating: 2 (Ready)**<br>• Code: `GET /public/v1/analytics/:integration` (`:700`), `GET /public/v1/analytics/post/:postId` (`:710`)<br>• Provenance: Coarse `creationMethod: API` recorded (`schema.prisma:364`), but missing specific agent principal ID |
| **Channel 2: Model Context Protocol (MCP)**<br>(`start.mcp.ts`, `chat/tools/*`) | **Rating: 3 (Extensible)**<br>• Code: `start.mcp.ts:150` (MCPServer protocol `2026-07-28`), `chat/tools/tool.list.ts:25` (23 tools)<br>• Direct command: `schedulePostTool`, `deletePostTool`<br>• Auth: Bearer API key or OAuth via `createOAuthMiddleware` (`oauth-middleware.ts:25`) | **Rating: 2 (Ready)**<br>• Code: `postsListTool`, `mediaStatusTool`, `videoStatusTool`, `clippingStatusTool`<br>• Tools accept job/post IDs and return structured execution progress to LLM caller | **Rating: 1 (Partial)**<br>• Composition: Rich tool schema allows chained invocations<br>• Cancellation: `deletePostTool` (`idempotentHint: true`)<br>• **Gap:** `schedulePostTool` declares `idempotentHint: false` (`integration.schedule.post.ts:77`), risk of double-posting | **Rating: 1 (Partial)**<br>• Tool inspection: Tools can query current resource state<br>• **Gap:** No push event streaming over MCP; client must actively query status tools | **Rating: 1 (Partial)**<br>• Code: Analytics query tools exist in agent prompt (`load.tools.service.ts:81`), but dedicated analytics MCP tool is missing from `tool.list.ts:25`<br>• Audit: Stores `creationMethod: MCP` (`integration.schedule.post.ts:285`) |
| **Channel 3: Webhooks & Events**<br>(`post.activity.ts:515`, `webhooks.controller.ts`, Redis) | **Rating: 1 (Partial)**<br>• Inbound: `POST /webhooks` configures outbound endpoints (`webhooks.controller.ts:31`)<br>• Inbound command: No generic inbound webhook receiver to trigger actions (only payment webhooks at `payment.controller.ts`) | **Rating: 1 (Partial)**<br>• Dispatches post status to registered URLs upon publishing<br>• **Gap:** One-way notification; no task delegation contract or async callback handshake | **Rating: 0 (Absent)**<br>• Negative search: `redis.publish`, `redis.subscribe`, `eventBus`<br>• No event-driven workflow chaining or choreography over webhooks or Redis bus | **Rating: 1 (Partial)**<br>• Code: `PostActivity.sendWebhooks` (`post.activity.ts:515`) dispatches JSON payload on post publish<br>• **Gap:** Only on publish success; no webhooks for scheduled, failed, or canceled posts; no HMAC signature | **Rating: 0 (Absent)**<br>• Negative search: `webhook.analytics`, `metrics.event`<br>• Webhooks carry no engagement metrics or audit trails; only raw post JSON (`post.activity.ts:547`) |
| **Channel 4: Temporal / Orchestrator Surface**<br>(`apps/orchestrator`, `monitor.controller`) | **Rating: 1 (Partial)**<br>• Workflows can only be started internally by backend services (`posts.service.ts:createPost`)<br>• **Gap:** No external Temporal gRPC client exposed to CoS; all commands must transit REST or MCP | **Rating: 2 (Ready)**<br>• Internal Temporal workflows (`post.workflow.v1.1.2.ts`, `clipping.workflow.ts`) manage long-running tasks, retries, and sleep intervals<br>• External CoS cannot query Temporal directly | **Rating: 3 (Extensible - Internal)** / **Rating: 1 (As CoS Surface)**<br>• Production-grade internal resilience: 12 immutable workflow versions, heartbeat timeouts (`HEARTBEAT_TIMEOUT = 3min`), maxAttempts: 1 on mutations<br>• **Gap:** CoS cannot inject signals or co-orchestrate | **Rating: 1 (Partial)**<br>• Health: `HealthController` (`apps/orchestrator/src/health.controller.ts:7`) validates Temporal connection<br>• **Gap:** `MonitorController` (`apps/backend/src/api/routes/monitor.controller.ts:6`) is an empty stub returning hardcoded string | **Rating: 1 (Partial)**<br>• Temporal records full execution history internally<br>• `digest.email.workflow.ts` compiles post digests<br>• **Gap:** Temporal execution histories are not exposed to external machine consumers |

---

## 3. Deep Analysis per CoS Operational Lens

### 3.1 Command Lens (Issue & Authorize Actions)
- **External Principal Authentication:**
  - Machine principals can authenticate using static Organization API keys (`PublicAuthMiddleware`, `public.auth.middleware.ts:51`) or OAuth 2.0 bearer tokens (`pos_` prefix, `public.auth.middleware.ts:38`).
  - RFC 7591 Dynamic Client Registration is supported via `POST /oauth/register` (`oauth.controller.ts:42`). However, Postiz **does not support the `client_credentials` grant type** (`oauth.controller.ts:147`). Machine principals must either obtain a pre-generated API key or perform an Authorization Code flow with PKCE (`S256`).
- **Authorization & Scoping:**
  - When an API key is presented, `PublicAuthMiddleware:20` attaches a virtual role `SUPERADMIN` to `req.org`.
  - Quota enforcement is governed by CASL (`PermissionsService.check`, `permissions.service.ts:39`). If Stripe billing is disabled in self-hosted deployments, all actions are permitted by default.
- **Publishing Safeguards:**
  - There is **no mechanical approval barrier** prior to publishing. When calling `POST /public/v1/posts` or `schedulePostTool`, passing `type: 'now'` triggers immediate publishing to live social channels without human review.

### 3.2 Delegation Lens (Hand off Task, Track Status)
- **Asynchronous Task Tracking:**
  - Post creation returns `{ postId, group }` (`public.integrations.controller.ts:231`). Posts can be polled via `GET /public/v1/posts` (`:134`).
  - Media uploads return an asset `id` which can be polled for transcoding status via `GET /public/v1/media/:id/status` (`:283`) or `mediaStatusTool`.
  - Video generation returns a `jobId` which can be polled via `videoStatusTool`.
  - Video clipping returns a `clippingId` which can be polled via `GET /public/v1/clipping/:id` (`:578`) or `clippingStatusTool`.
- **Delegation Verdict:** Postiz has mature polling-based delegation endpoints over both REST and MCP. However, it lacks push-based delegation completion callbacks (webhooks do not fire on media or clipping completion).

### 3.3 Orchestration Lens (Multi-Step, Idempotent, Cancellable)
- **Multi-Step Pipelines:**
  - External pipelines (e.g. Ingest Asset → Transcode → Generate Copy → Schedule Post) are fully composable via sequential REST or MCP tool calls.
- **Cancellation & Teardown:**
  - Scheduled posts can be canceled before release date by calling `DELETE /public/v1/posts/:id` (`public.integrations.controller.ts:234`) or `DELETE /public/v1/posts/group/:group` (`:244`), or using `deletePostTool`.
- **Idempotency Deficit:**
  - Neither `POST /public/v1/posts` nor `schedulePostTool` accepts an `Idempotency-Key` header or payload attribute.
  - If a network error interrupts a CoS request after Postiz receives it, a CoS retry will create a second identical post. This is a high-severity operational risk.

### 3.4 Monitoring Lens (Events, State Changes, Health)
- **Outbound Webhooks Disconnect:**
  - Postiz implements an outbound webhook dispatcher (`PostActivity.sendWebhooks`, `apps/orchestrator/src/activities/post.activity.ts:515`).
  - However, webhooks are **only dispatched when a post publishes**. No webhooks are dispatched for post scheduling, post deletion, publishing failures, media upload readiness, or OAuth token refresh failures.
  - Furthermore, webhooks have **no cryptographic HMAC signature** (`X-Postiz-Signature`) and use best-effort delivery wrapped in empty catch blocks (`post.activity.ts:552`).
- **Queue & Engine Health Monitoring:**
  - `HealthController` (`apps/orchestrator/src/health.controller.ts:7`) provides an active `/health/status` endpoint that verifies connection to the Temporal cluster.
  - Conversely, `MonitorController` (`apps/backend/src/api/routes/monitor.controller.ts:6`) contains only a hardcoded mock returning `"Queue ${name} is healthy"` without querying Temporal or Redis queues.

### 3.5 Reporting Lens (Metrics & Audit Trails)
- **Platform Analytics Access:**
  - Postiz allows programmatic querying of platform engagement metrics via REST:
    - `GET /public/v1/analytics/:integration` (`public.integrations.controller.ts:700`): returns impressions, reach, and engagement across channels.
    - `GET /public/v1/analytics/post/:postId` (`public.integrations.controller.ts:710`): returns granular metrics for an individual post.
- **Audit Trails & Provenance Deficit:**
  - In `schema.prisma:364`, `model Post` records `creationMethod: CreationMethod` (`UNKNOWN`, `WEB`, `MCP`, `API`, `AUTOPOST`, `CLI`).
  - It does **not record the specific agent principal identity** (e.g., distinguishing whether an API post was created by `chief-of-staff`, a developer CLI script, or a third-party Zapier integration).

---

## 4. Top-5 Findings Impacting Chief-of-Staff Feasibility

1. **Unprotected Direct Publishing (Safety Risk):**
   - *Evidence:* `integrationSchedulePostTool` (`integration.schedule.post.ts:258`) allows immediate publishing (`type: 'now'`) without an enforced approval checkpoint. A rogue or hallucinating CoS agent can publish unvetted posts directly to brand social channels.
2. **Missing Post Idempotency (Reliability Risk):**
   - *Evidence:* `schedulePostTool` metadata declares `idempotentHint: false` (`integration.schedule.post.ts:77`) and lacks deduplication logic. CoS retry routines during network timeouts will trigger duplicate social media posts.
3. **Incomplete Outbound Event Catalog & Missing Signatures (Observability Gap):**
   - *Evidence:* `PostActivity.sendWebhooks` (`post.activity.ts:515`) only fires upon successful publishing, emits unsigned JSON, and swallows transmission errors. The CoS cannot reliably monitor campaign progress or catch post failures via webhooks.
4. **Strict SSRF Blocks Local Inter-Agent Communication (Deployment Blocker):**
   - *Evidence:* `webhook.url.validator.ts:77, 87` strictly blocks private IP ranges, `localhost`, and non-HTTPS protocols for webhook destinations. In a standard local Docker Compose environment, Postiz will reject webhook subscriptions to `http://chief-of-staff:8000` unless `DISABLE_SSRF_PROTECTION=true` is explicitly set.
5. **No Direct M2M Client Credentials OAuth Grant (Onboarding Constraint):**
   - *Evidence:* `OAuthController.token` (`oauth.controller.ts:147`) explicitly rejects grant types other than `authorization_code`. The CoS cannot authenticate autonomously via client ID and client secret alone; it must be provisioned with a pre-configured organization API key.

