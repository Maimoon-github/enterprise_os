# Project Inspection: Marketing/Postiz Codebase Deep-Dive

This document details the exhaustive, prioritized-deep inspection of the active Postiz codebase (`business-os/agents/marketing/postiz-app`), establishing concrete code citations, architecture mechanics, interface inventories, and verified absences.

---

## 1. Project Self-Description & Operational Identity

Postiz presents dual identities across its source documentation:
1. **Public/Open-Source Identity:** *"Postiz, a tool to schedule social media and chat posts to 28+ channels... You can add posts to the calendar, they will be added into a workflow and posted at the right time"* (`CLAUDE.md:1-2`, `README.md:1-20`).
2. **Federated Business OS Marketing Identity:** *"Independent environment for the marketing business agent. Exposes capabilities only via API / MCP / webhook / adapter. Orchestrated exclusively by chief-of-staff/"* (`business-os/agents/marketing/README.md:1-5`).

### Operational Context & Deployment Posture
- **Runtime Topology:** Monorepo using PNPM workspaces (`pnpm-workspace.yaml:1`) with Node 22 (`package.json:10`). Divided into `apps/backend` (NestJS REST API), `apps/orchestrator` (NestJS Temporal worker), `apps/frontend` (Next.js 14 App Router), `apps/sdk` (Node programmatic client), `apps/extension` (Chrome MV3 extension), `apps/commands` (CLI tasks), and shared packages in `libraries/` (`nestjs-libraries`, `react-shared-libraries`, `helpers`).
- **Persistence & Services:** Primary database is PostgreSQL 17 (`docker-compose.yaml:137`), caching/ephemeral state in Redis 7.2 (`docker-compose.yaml:154`), workflow coordination via Temporal server with PostgreSQL/Elasticsearch backend (`docker-compose.yaml:180-270`), Sentry Spotlight for tracing (`docker-compose.yaml:168`), and storage via local disk or Cloudflare R2 (`.env.example:16-22, 62`).
- **Multi-Tenancy Posture:** Strict multi-tenant schema anchored by the `Organization` model (`libraries/nestjs-libraries/src/database/prisma/schema.prisma:11`). All core domain entities (`Post`, `Integration`, `Media`, `Webhooks`, `OAuthApp`, `Tags`) enforce `organizationId` foreign key relations. An agency directory feature (`socialMediaAgency`, `agencies.repository.ts:14`) provides a marketplace catalog but does not weaken org-level data isolation.

---

## 2. Agent & MCP Infrastructure Deep-Dive

Postiz possesses an advanced, agent-native integration surface built on Mastra, Model Context Protocol (MCP), and OAuth 2.0.

### 2.1 Agent Tool Interface & Registry
Every agent capability is encapsulated as an `AgentToolInterface` (`libraries/nestjs-libraries/src/chat/agent.tool.interface.ts:5`):
```typescript
export interface AgentToolInterface {
  name: string;
  mcpOnly?: boolean;               // Requires MCP host (e.g. ui:// widget)
  available?(): boolean;           // Omitted if underlying service unconfigured
  optionalOnSelfHosted?: boolean;  // Relayable from cloud
  run(): ToolReturn;               // Returns Mastra ToolAction
}
```
All tools are centrally registered in `libraries/nestjs-libraries/src/chat/tools/tool.list.ts:25`.

### 2.2 Complete 23-Tool Registry Inventory

| Tool Class | MCP Tool Name | Primary Purpose | Side Effects / Destruction | Authn Context Required | Code Citation |
|---|---|---|---|---|---|
| `IntegrationListTool` | `integrationList` | List connected social channels for organization | Read-only | Organization (`AsyncLocalStorage`) | `chat/tools/integration.list.tool.ts:1` |
| `GroupListTool` | `groupList` | List customer groups in organization | Read-only | Organization | `chat/tools/group.list.tool.ts:1` |
| `IntegrationConnectTool` | `integrationConnectTool` | Generate 1-hour connection link for a new social network | Mutates DB (creates connect token) | Organization | `chat/tools/integration.connect.tool.ts:1` |
| `IntegrationValidationTool` | `integrationSchema` | Returns platform rules, character limits, settings schemas | Read-only | Organization | `chat/tools/integration.validation.tool.ts:1` |
| `IntegrationTriggerTool` | `triggerTool` | Execute platform-specific queries (search subreddits, boards) | External API read/write | Organization | `chat/tools/integration.trigger.tool.ts:1` |
| `IntegrationSchedulePostTool` | `schedulePostTool` | Draft, schedule, or immediately publish social posts | **HIGH MUTATION / PUBLISH** (`destructiveHint: true`) | Organization | `chat/tools/integration.schedule.post.ts:62` |
| `PostsListTool` | `postsListTool` | List scheduled or published posts within date window | Read-only | Organization | `chat/tools/posts.list.tool.ts:1` |
| `PostSettingsTool` | `postSettingsTool` | Update channel-specific settings of draft/scheduled post | Mutates post settings | Organization | `chat/tools/post.settings.tool.ts:1` |
| `DeletePostTool` | `deletePostTool` | Delete scheduled, draft, or published post and comments | **DESTRUCTIVE** (`destructiveHint: true`, irreversible) | Organization | `chat/tools/delete.post.tool.ts:9` |
| `GenerateVideoOptionsTool` | `generateVideoOptions` | Inspect video generator options and parameters | Read-only | Organization | `chat/tools/generate.video.options.tool.ts:1` |
| `VideoFunctionTool` | `videoFunctionTool` | Fetch dynamic provider options (e.g., ElevenLabs voices) | Read-only | Organization | `chat/tools/video.function.tool.ts:1` |
| `GenerateVideoTool` | `generateVideoTool` | Start AI video generation job (`seedance`, `images-slides`) | Triggers job, spends credits | Organization | `chat/tools/generate.video.tool.ts:18` |
| `VideoStatusTool` | `videoStatusTool` | Poll status of running video generation job | Read-only | Organization | `chat/tools/video.status.tool.ts:1` |
| `ClippingTool` | `clippingTool` | Cut YouTube video into vertical clips via RunPod GPU | Triggers cloud job, spends minutes | Organization (requires Cloudflare/RunPod) | `chat/tools/clipping.tool.ts:11` |
| `ClippingStatusTool` | `clippingStatusTool` | Poll progress of video clipping job | Read-only | Organization | `chat/tools/clipping.status.tool.ts:1` |
| `ClippingWidgetTicketTool` | `clippingWidgetTicketTool` | Issue iframe ticket for MCP App clipping widget | Mutates ticket store | Organization | `chat/tools/clipping.widget.ticket.tool.ts:1` |
| `GenerateImageTool` | `generateImageTool` | Generate image using DALL-E wrapper | Generates asset, saves to Media | Organization | `chat/tools/generate.image.tool.ts:1` |
| `UploadFromUrlTool` | `uploadFromUrlTool` | Ingest external image/video from URL into media library | Downloads & saves media | Organization | `chat/tools/upload.from.url.tool.ts:1` |
| `MediaListTool` | `mediaListTool` | Query stored organization media library | Read-only | Organization | `chat/tools/media.list.tool.ts:1` |
| `MediaStatusTool` | `mediaStatusTool` | Check upload transcoding/normalization status | Read-only | Organization | `chat/tools/media.status.tool.ts:1` |
| `UploadWidgetTool` | `uploadWidget` | MCP resource widget providing upload iframe | UI resource | Organization | `chat/tools/upload.widget.tool.ts:1` |
| `UploadWidgetTicketTool` | `uploadWidgetTicketTool` | Generate temporary ticket for upload widget | Mutates ticket store | Organization | `chat/tools/upload.widget.ticket.tool.ts:1` |
| `UploadWidgetStatusTool` | `uploadWidgetStatusTool` | Inspect progress of upload initiated in widget | Read-only | Organization | `chat/tools/upload.widget.status.tool.ts:1` |

### 2.3 Critical Agent Verification Verdicts
1. **Destructive Actions & Missing Human Approval Gate:**
   - In `IntegrationSchedulePostTool` (`integration.schedule.post.ts:76`), the tool metadata declares `destructiveHint: true` and `openWorldHint: true`.
   - Line 258 accepts parameter `type: 'now' | 'schedule' | 'draft'`. If an automated agent passes `type: 'now'`, the post is submitted directly to the Temporal queue and published to production social networks without any human confirmation prompt.
   - While the interactive chat agent prompt in `LoadToolsService` (`load.tools.service.ts:100`) advises the LLM *"Before scheduling a post, always make sure you ask the user confirmation"*, this is purely a soft prompt instruction. The tool's execution handler (`execute`) has **no programmatic approval barrier**.
2. **Idempotency Gaps:**
   - `IntegrationSchedulePostTool` explicitly specifies `idempotentHint: false` (`integration.schedule.post.ts:77`).
   - The tool does not accept an idempotency key. A retried tool call by a CoS agent following a connection drop creates a duplicate scheduled post.
   - Conversely, `DeletePostTool` declares `idempotentHint: true` (`delete.post.tool.ts:22`) and safely handles repeated deletions.
3. **External Agent Authentication Model:**
   - Defined in `libraries/nestjs-libraries/src/chat/start.mcp.ts:57-69` and `libraries/nestjs-libraries/src/chat/oauth-middleware.ts:25`.
   - Machine agents can authenticate via two paths:
     1. Static API Key: Header `Authorization: Bearer <API_KEY>` or URL path `/mcp/:apiKey` (resolved via `OrganizationService.getOrgByApiKey`).
     2. OAuth 2.0 Bearer Token: Token prefixed with `pos_` (resolved via `OAuthService.getOrgByOAuthToken`).
   - Scopes supported: `openid`, `email`, `mcp:read`, `mcp:write` (`start.mcp.ts:46-48`).
4. **MCP Server Architecture vs Relay:**
   - `start.mcp.ts` instantiates `@mastra/mcp` `MCPServer` on protocol `2026-07-28` (`start.mcp.ts:150`).
   - `mcp.relay.service.ts` allows Postiz Cloud to act as a client proxy via `@modelcontextprotocol/sdk/client` to forward tool executions to self-hosted instances over `StreamableHTTPClientTransport` (`mcp.relay.service.ts:5`).
5. **Copilot Controller:**
   - `apps/backend/src/api/routes/copilot.controller.ts:48, 70` exposes `/copilot/chat` and `/copilot/agent` using `@copilotkit/runtime` and `@ag-ui/mastra`. It is intended for browser-based interactive chat within the Next.js UI (`apps/frontend/src/app/(app)/(site)/agents/[id]/page.tsx`), not for headless CoS inter-agent delegation.

---

## 3. Orchestrator Deep-Dive (Temporal)

### 3.1 Workflow Architecture & Determinism Versioning
The orchestrator (`apps/orchestrator/src/`) runs on Temporal. Postiz contains **12 distinct, versioned post workflow files**:
`post.workflow.v1.0.1.ts` through `post.workflow.v1.1.2.ts` (`apps/orchestrator/src/workflows/post-workflows/`).

**Why 12 versions exist:**
`CLAUDE.md:73-74` explains the core constraint:
> *"Workflows files can never be changed if they are already in origin/main, because changing a workflow will fail all its activities, instead create a new workflow with the version, and everywhere the workflow being called, change it to the new workflow version. Workflows activities parameters cannot be changed, as it will break the workflow."*

Because Temporal relies on deterministic event history replay, modifying workflow code in-place breaks in-flight executions. Postiz enforces strict version incrementation whenever workflow orchestration semantics evolve.

### 3.2 Active Post Workflow Mechanics (`post.workflow.v1.1.2.ts`)
- **Heartbeat & Failure Timeouts:**
  - `HEARTBEAT_TIMEOUT = 3 * 60 * 1000` (3 minutes, `post.workflow.v1.1.2.ts:27`).
  - Read-only activities (`getPost`, `getPostsList`, `checkPostStatus`) run with 3 retries, backoff coefficient 1, 10s interval (`post.workflow.v1.1.2.ts:63-71`).
  - Publishing mutations (`postSocialPending`, `finalizePost`) are configured with `maximumAttempts: 1` (`post.workflow.v1.1.2.ts:89`) to prevent automatic retries from double-publishing content to social networks.
- **Workflow Lifecycle Steps:**
  1. Post created with `state: QUEUE` (`schema.prisma:347`).
  2. Workflow sleeps until `publishDate` (`sleep(timeDifference)`).
  3. Pre-publish validation & media verification.
  4. Platform adapter invoked (`postSocialPending`).
  5. Async polling if platform processes media asynchronously (e.g. YouTube, TikTok).
  6. Finalize post: updates state to `POSTED` or `ERROR`.
  7. Outbound webhook dispatch: calls activity `sendWebhooks` (`post.activity.ts:515`).

### 3.3 Specialized Workflows
- `clipping.workflow.ts`: Coordinates YouTube video download, Whisper/Deepgram transcription, AI cut selection, RunPod GPU rendering, and post draft creation (`clipping.workflow.ts:16-100`).
- `generate.video.workflow.ts`: Coordinates AI video generation via third-party providers (EvoLink `seedance`, HeyGen, ReelFarm).
- `process.media.workflow.ts`: Normalizes uploaded media to 1080p MP4 / web formats.
- `refresh.token.workflow.ts`: Proactively refreshes expiring OAuth tokens across connected channels.
- `autopost.workflow.ts` & `streak.workflow.ts`: Recurring scheduled tasks for RSS/social feeds and user activity streaks.

### 3.4 Commands Task (`agent.run.ts`)
- `apps/commands/src/tasks/agent.run.ts:8`: CLI command `run:agent` which triggers `AgentGraphService.createGraph('hello', true)`.
- It executes a LangGraph `StateGraph` (`libraries/nestjs-libraries/src/agent/agent.graph.service.ts:113`) that searches Tavily, categorizes content, drafts copy, and generates images via DALL-E.

---

## 4. API, Authentication, and Tenancy Matrix

### 4.1 Backend Controller Inventory
The backend (`apps/backend/src/api/routes/`) exposes 33 controllers. Priority controllers evaluated:

| Controller | Route Mount | Primary Role | Guards & Authentication | Multi-Tenant Scoping |
|---|---|---|---|---|
| `PublicIntegrationsController` | `/public/v1` | External REST API: posts, upload, channels, media, analytics | `PublicAuthMiddleware` (API Key or `pos_` OAuth token) | Organization (`req.org`) |
| `PostsController` | `/posts` | Web UI post CRUD, bulk actions, preview links | `AuthMiddleware` (JWT cookie/header) | Organization (`GetOrgFromRequest()`) |
| `IntegrationsController` | `/integrations` | Social channel configuration, disconnection, settings | `AuthMiddleware` + `PoliciesGuard` | Organization (`GetOrgFromRequest()`) |
| `NoAuthIntegrationsController` | `/integrations` | Social OAuth callbacks, state exchange, provider lists | Ephemeral Redis state (`login:${state}`, `organization:${state}`) | Org resolved from Redis state key |
| `OAuthController` | `/oauth` | RFC 7591 dynamic registration, RFC 8414 authorize, token | Public DCR / PKCE validation / `ThrottlerRealIpGuard` | Scoped by `clientId` and user consent |
| `OAuthAppController` | `/oauth-app` | Manage developer OAuth applications in UI | `AuthMiddleware` | Organization (`GetOrgFromRequest()`) |
| `WebhookController` | `/webhooks` | Outbound webhook CRUD and test dispatch | `AuthMiddleware` + `CheckPolicies([Create, WEBHOOKS])` | Organization (`GetOrgFromRequest()`) |
| `MonitorController` | `/monitor` | Health checks and queue monitoring | Public (Stub implementation) | None (Returns hardcoded healthy string) |
| `CopilotController` | `/copilot` | Interactive CopilotKit chat endpoint | `AuthMiddleware` + `CheckPolicies([Create, AI])` | Organization (`GetOrgFromRequest()`) |
| `SignatureController` | `/signatures` | Post signature templates | `AuthMiddleware` | Organization (`GetOrgFromRequest()`) |
| `AnalyticsController` | `/analytics` | Historical engagement & performance charts | `AuthMiddleware` | Organization (`GetOrgFromRequest()`) |
| `ThirdPartyController` | `/third-party` | External service configurations (HubSpot, HeyGen) | `AuthMiddleware` | Organization (`GetOrgFromRequest()`) |
| `AdminController` | `/admin` | Global platform administration, user impersonation | `AuthMiddleware` + `SuperAdminGuard` | Cross-org (Admin only) |

### 4.2 Authentication Chains & CASL Permissions
- **Web App Users:** Intercepted by `AuthMiddleware` (`apps/backend/src/services/auth/auth.middleware.ts:29`). Reads `req.headers.auth` or `req.cookies.auth`. Verifies JWT signature and reloads `User` and `Organization` from database. Supports superadmin impersonation via `impersonate` cookie/header (`auth.middleware.ts:60`).
- **Machine Principals (CoS / API):** Intercepted by `PublicAuthMiddleware` (`apps/backend/src/services/auth/public.auth.middleware.ts:10`). Accepts header `Authorization: <apiKey>` or `Authorization: pos_<oauthToken>`. Validates token against database; binds `req.org` and sets virtual role `SUPERADMIN` (`public.auth.middleware.ts:20`).
- **CASL Policies:** `PermissionsService` (`apps/backend/src/services/auth/permissions/permissions.service.ts:39`) builds CASL `Ability` based on subscription quotas (`pricing[tier]`). Enforces monthly limits on `CHANNEL`, `WEBHOOKS`, `POSTS_PER_MONTH`, and `AI`. If `STRIPE_PUBLISHABLE_KEY` is unset (self-hosted mode), all permissions are granted by default (`permissions.service.ts:52`).

### 4.3 Multi-Tenancy Isolation Guarantees
- Multi-tenancy is enforced in Prisma queries by scoping on `organizationId` (`post.repository.ts`, `integration.repository.ts`).
- SuperAdmin API keys can override the target tenant by passing header `x-postiz-org: <orgId>` (`public.auth.middleware.ts:75-98`), verified via `OrganizationService.canUseSuperAdminApi(org.id)`. Non-superadmin callers attempting to pass `x-postiz-org` receive `403 Forbidden`.

---

## 5. Webhooks & Adapters Architecture

### 5.1 Outbound Webhooks (The CoS Monitoring Channel)
- Outbound webhooks are defined in `Webhooks` model (`schema.prisma:544`) and managed via `WebhookController` (`apps/backend/src/api/routes/webhooks.controller.ts`).
- **Emission Site:** Outbound events are dispatched exclusively in `apps/orchestrator/src/activities/post.activity.ts:515` (`sendWebhooks`):
  ```typescript
  @ActivityMethod()
  async sendWebhooks(postId: string, orgId: string, integrationId: string) {
    // Queries webhooks for orgId and integrationId
    // Fetches post payload via _postService.getPostByForWebhookId
    await fetch(webhook.url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(post),
      dispatcher: getSsrfSafeDispatcher(),
    });
  }
  ```
- **Critical Limitations:**
  1. **Event Types:** Only emitted upon **successful post publishing**. Zero webhooks exist for post creation, scheduling, failure, cancellation, media upload completion, or token expiration.
  2. **Signatures:** Outbound requests contain **no HMAC signature header** (no `X-Postiz-Signature`). The receiver cannot verify cryptographic authenticity.
  3. **Reliability:** Delivery is wrapped in empty catch blocks (`/**empty**/`, `post.activity.ts:552`). Delivery is best-effort with no retry queue or dead-letter storage.

### 5.2 SSRF Protection Mechanics
Outbound URLs (webhooks and self-hosted instances) are strictly validated by `webhook.url.validator.ts`:
- Rejects loopback (`127.0.0.0/8`, `::1`, `localhost`).
- Rejects RFC 1918 private IPv4 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
- Rejects link-local (`169.254.0.0/16`, `fe80::/10`).
- Rejects NAT64 (`64:ff9b::/96`) and 6to4 (`2002::/16`).
- **Mandatory HTTPS:** Line 77 explicitly checks: `if (parsed.protocol !== 'https:') return false;`.
- **Integration Impact:** In a local Docker Compose setup where the CoS agent runs on `http://chief-of-staff:8000` or `http://localhost:8000`, Postiz will refuse to register the CoS webhook URL unless `DISABLE_SSRF_PROTECTION=true` is set.

### 5.3 Social Platform Adapters
Postiz contains 35 social media platform adapters in `libraries/nestjs-libraries/src/integrations/social/`:
- Platforms: Bluesky, Dev.to, Discord, Dribbble, Facebook, Farcaster, Google My Business (GMB), Hashnode, Instagram, Kick, Lemmy, LinkedIn, Listmonk, Mastodon, Medium, MeWe, Moltbook, Nostr, Pinterest, Reddit, Skool, Slack, Telegram, Threads, TikTok, Tumblr, Twitch, VK, Whop, WordPress, X (Twitter), YouTube.
- Refresh Tokens: Managed via `RefreshToken` exception handling and `refresh.token.workflow.ts`.

---

## 6. Frontend UI Inventory

The frontend is a modern Next.js 14 App Router application (`apps/frontend/`):
- `(site)/launches`: Post calendar, planner grid, schedule creation modal.
- `(site)/analytics`: Channel impressions, follower growth, engagement charts.
- `(site)/media`: Uploaded image/video library, thumbnail generator.
- `(site)/plugs`: Post augmentation plugs (auto-comment, short-links, recycling).
- `(site)/settings`: Team members, organization profile, developer API keys.
- `(site)/agents/[id]`: CopilotKit interactive chat UI (`AgentChat` in `agents/[id]/page.tsx:10`).
- `components/webhooks/webhooks.tsx`: Full UI for adding, testing, and deleting outbound webhooks.
- `components/public-api/mcp.client.icons.tsx`: Visual status indicators for connected MCP clients (Claude, Codex, Cursor, Grok, etc.).

---

## 7. Quality Gates & Test Suite Findings

### 7.1 Automated Testing Status
- `package.json:40` defines `"test": "jest --coverage --detectOpenHandles --reporters=default --reporters=jest-junit"`.
- `jest.config.ts` references `@nx/jest`.
- **Inspection Finding:** A recursive search for test files (`*.spec.ts`, `*.test.ts`, `__tests__`) across the entire repository yielded **0 test files** (`FACT`).
- There are no automated unit tests, integration tests, or contract tests in the postiz-app repository.

### 7.2 CI/CD Pipelines
- `.github/workflows/build.yml:53`: Runs `pnpm install` and `pnpm run build`. Compiles frontend and backend applications; does not run tests.
- `.github/workflows/codeql.yml`: Runs GitHub CodeQL security analysis on TypeScript/JavaScript code.
- `.github/workflows/build-containers.yml`: Builds Docker container images for deployment.

---

## 8. Verified Codebase Absences & Search Records

The following candidate capabilities were thoroughly investigated and verified as **ABSENT** from the codebase:

| Claimed Absence | Search Locations Covered | Search Terms Utilized | Verified Result & Notes |
|---|---|---|---|
| Chief of Staff Implementation | Entire repository root (`apps/`, `libraries/`) | `chief`, `of-staff`, `of staff`, `chief-of-staff` | **0 files found** (`FACT`). Postiz contains no internal CoS. |
| Qdrant Vector Store | `libraries/nestjs-libraries/`, `.env.example`, `docker-compose.yaml` | `qdrant`, `vector`, `embeddings` (outside DALL-E) | **0 occurrences found** (`FACT`). Only relational PostgreSQL and Mastra PostgresStore exist. |
| Redis Cross-Agent Event Bus | `libraries/nestjs-libraries/src/redis/`, `apps/` | `redis.publish`, `redis.subscribe`, `xadd`, `xread` | **0 occurrences found** (`FACT`). Redis is used solely for caching and session state. |
| CoS ↔ Chopify Bridge | `business-os/agents/marketing/` (both postiz and chopify) | `chopify`, `postiz`, `render_clips`, `clip_bridge` | **0 occurrences found** (`FACT`). Zero inter-component communication exists. |
| Machine-Facing Approval Gate | `chat/tools/integration.schedule.post.ts`, `public-api/` | `requireApproval`, `approvalStatus`, `humanInTheLoop` | **0 occurrences found** (`FACT`). Post creation can publish immediately (`type: now`). |
| Outbound Event Catalog | `libraries/nestjs-libraries/src/dtos/webhooks/` | `webhookEvent`, `eventCatalog`, `EventType` | **0 occurrences found** (`FACT`). Webhook payload is an untyped raw post representation. |
| Machine M2M Client Credentials Grant | `apps/backend/src/api/routes/oauth.controller.ts:147` | `client_credentials` | **Rejected in code** (`FACT`). `OAuthController` explicitly rejects non-authorization_code grants. |
| Post Creator Provenance (Agent Identity) | `libraries/nestjs-libraries/src/database/prisma/schema.prisma:364` | `agentId`, `creatorAgent`, `principalId` | **0 occurrences found** (`FACT`). `CreationMethod` records only coarse enum: `MCP`, `API`, `WEB`, `CLI`. |

