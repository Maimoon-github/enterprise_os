Errored check directory contents
Errored check directory contents

# Architecture Blueprint & Directory Specification: Self-Hosted Agentic Brand Marketing Platform

This document defines the production blueprint, monorepo directory hierarchy, and module-level responsibilities for the self-hosted Agentic Brand Marketing Platform.

---

## 1. System Architecture & Component Interaction Topology

### 1.1 Architectural Reconciliation: Observability & Telemetry

The attached specification describes an OpenInference span model typically paired with Arize Phoenix, while the selected target stack standardizes on **OpenTelemetry** as the instrumentation layer with **Langfuse** as the primary observability backend:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      APPLICATION EXECUTION LAYER                       │
│  FastAPI (BFF) ──► LangGraph (StateGraph) ──► Celery ──► MCP Servers   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   OPENTELEMETRY INSTRUMENTATION LAYER                  │
│       TracerProvider with OpenInference Semantic Attributes:           │
│  - openinference.span.kind (AGENT, CHAIN, LLM, TOOL, RETRIEVER, etc.)  │
│  - graph.node.id, graph.node.parent_id, session.id, user.id            │
│  - Trace-level evaluations: trace.evaluations.0.evaluation.*           │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   ▼ (Primary Exporter)              ▼ (Optional Local Debug)
┌─────────────────────────────────────┐  ┌───────────────────────────────┐
│              LANGFUSE               │  │         ARIZE PHOENIX         │
│  - Distributed Traces & Spans       │  │  - Local evaluation testing   │
│  - Token / Cost Analytics (Ollama)  │  │  - Trajectory graph debugging │
│  - Rubric Scores & Prompt Registry  │  │  - Interactive span inspector │
└─────────────────────────────────────┘  └───────────────────────────────┘
```

1. **Instrumentation Engine:** `opentelemetry-sdk` paired with custom OpenTelemetry Processors and OpenInference semantic attributes (`openinference.semconv.trace.SpanAttributes`).
2. **Primary Observability Backend:** Traces, token metrics, generation parameters, and rubric eval scores export via OTLP (`/v1/traces`) directly to **Langfuse** (self-hosted).
3. **Optional Local Evaluation / Debugger:** Phoenix can run as an optional OTLP receiver during local development or offline golden dataset benchmarking without changing application instrumentation.

---

### 1.2 End-to-End Primary Runtime Flow

```
 ┌──────────────────────┐
 │ Next.js Frontend UI  │
 └──────────┬───────────┘
            │ 1. HTTP / SSE / WebSocket (Campaign Blueprint / Approval Resume)
            ▼
 ┌──────────────────────┐
 │   FastAPI Gateway    │ ◄── Authlib OAuth / RBAC / Pydantic Validation
 └──────────┬───────────┘
            │ 2. Dispatches Graph Execution / Resumes Interrupt
            ▼
 ┌───────────────────────────────────────────────────────────────────────┐
 │                   MasterOrchestratorGraph (LangGraph)                 │
 │                                                                       │
 │  ┌───────────────────────┐   PostgresSaver   ┌─────────────────────┐  │
 │  │ Research & Strategy   ├──► Checkpointer ◄─┤ Campaign & Creative │  │
 │  │ Subgraph (ReAct)      │    (PostgreSQL)   │ Subgraph (Plan-Solve│  │
 │  └───────────────────────┘                   └──────────┬──────────┘  │
 │                                                         │             │
 │                                                         ▼             │
 │                                              ┌─────────────────────┐  │
 │                                              │ Human Approval Gate │  │
 │                                              │  interrupt() Node   │  │
 │                                              └──────────┬──────────┘  │
 │                                                         │             │
 │  ┌───────────────────────┐                   ┌──────────▼──────────┐  │
 │  │ Closed-Loop Eval      │                   │ Multi-Platform      │  │
 │  │ Subgraph (ReWOO)      │                   │ Fan-Out (Send() Map)│  │
 │  └───────────────────────┘                   └──────────┬──────────┘  │
 └─────────────────────────────────────────────────────────┼─────────────┘
                                                           │
                      ┌────────────────────────────────────┴──────────────────────────────────┐
                      ▼                                                                       ▼
       ┌──────────────────────────────┐                                        ┌──────────────────────────────┐
       │   FastMCP Toolset Servers    │                                        │  Async Background Execution  │
       │  (Streamable HTTP / stdio)   │                                        │  (Celery + Redis + Podman)   │
       ├──────────────────────────────┤                                        ├──────────────────────────────┤
       │ • BrandRAG (Qdrant+FastEmbed)│                                        │ • Long-running media jobs    │
       │ • SocialGateway (8 Platforms)│                                        │ • Playwright browser tasks   │
       │ • MediaStudio (MinIO Assets) │                                        │ • Sandboxed code/skill runs  │
       │ • Analytics (PostgreSQL/Polars)                                      │ • Celery Beat scheduled runs │
       └──────────────┬───────────────┘                                        └──────────────┬───────────────┘
                      │                                                                       │
                      └───────────────────────────────────┬───────────────────────────────────┘
                                                          ▼
                                       ┌─────────────────────────────────────┐
                                       │    OpenTelemetry + Langfuse OTLP    │
                                       │  (Traces, Spans, Tokens, Evals)     │
                                       └─────────────────────────────────────┘
```

---

## 2. Complete Monorepo Directory Hierarchy

```text
agentic-brand-marketing-os/
├── README.md
├── Makefile
├── .env.example
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── docs/
│   ├── architecture.md
│   ├── agent-graphs.md
│   ├── mcp-and-skills.md
│   ├── api-contracts.md
│   ├── security-and-secrets.md
│   ├── observability.md
│   └── runbooks/
│       ├── local-dev.md
│       ├── worker-sandbox.md
│       └── incident-response.md
│
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── brands.py
│   │   │       ├── campaigns.py
│   │   │       ├── runs.py
│   │   │       ├── approvals.py
│   │   │       ├── agents.py
│   │   │       ├── skills.py
│   │   │       ├── mcp_servers.py
│   │   │       ├── media.py
│   │   │       ├── analytics.py
│   │   │       ├── schedules.py
│   │   │       ├── settings.py
│   │   │       └── observability.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── rbac.py
│   │   │   ├── logging.py
│   │   │   ├── telemetry.py
│   │   │   ├── idempotency.py
│   │   │   └── exceptions.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   ├── base.py
│   │   │   ├── models/
│   │   │   │   ├── user.py
│   │   │   │   ├── brand.py
│   │   │   │   ├── campaign.py
│   │   │   │   ├── run.py
│   │   │   │   ├── approval.py
│   │   │   │   ├── media_asset.py
│   │   │   │   ├── schedule.py
│   │   │   │   └── analytics_event.py
│   │   │   └── repositories/
│   │   │       ├── base_repo.py
│   │   │       ├── brand_repo.py
│   │   │       ├── campaign_repo.py
│   │   │       ├── run_repo.py
│   │   │       ├── approval_repo.py
│   │   │       └── media_repo.py
│   │   ├── schemas/
│   │   │   ├── common.py
│   │   │   ├── auth.py
│   │   │   ├── brand.py
│   │   │   ├── campaign.py
│   │   │   ├── run.py
│   │   │   ├── approval.py
│   │   │   ├── agent.py
│   │   │   ├── skill.py
│   │   │   ├── mcp.py
│   │   │   ├── media.py
│   │   │   ├── analytics.py
│   │   │   └── schedule.py
│   │   ├── orchestrator/
│   │   │   ├── graph.py
│   │   │   ├── state.py
│   │   │   ├── checkpointer.py
│   │   │   ├── routing.py
│   │   │   ├── handoffs.py
│   │   │   ├── subgraphs/
│   │   │   │   ├── research_strategy.py
│   │   │   │   ├── campaign_creative.py
│   │   │   │   ├── publishing_fanout.py
│   │   │   │   └── closed_loop_eval.py
│   │   │   └── workers/
│   │   │       ├── agent_worker_factory.py
│   │   │       ├── tool_registry.py
│   │   │       └── retry_policies.py
│   │   ├── agents/
│   │   │   ├── prompts/
│   │   │   │   ├── supervisor_prompt.py
│   │   │   │   ├── strategist_prompt.py
│   │   │   │   ├── copywriter_prompt.py
│   │   │   │   ├── compliance_prompt.py
│   │   │   │   └── analytics_prompt.py
│   │   │   ├── rubrics/
│   │   │   │   ├── voice_fidelity.py
│   │   │   │   ├── platform_hook.py
│   │   │   │   └── compliance_rubric.py
│   │   │   └── validators/
│   │   │       ├── campaign_schema.py
│   │   │       └── platform_limits.py
│   │   ├── integrations/
│   │   │   ├── llm/
│   │   │   │   ├── ollama_client.py
│   │   │   │   └── model_router.py
│   │   │   ├── social/
│   │   │   │   ├── base_adapter.py
│   │   │   │   ├── linkedin.py
│   │   │   │   ├── youtube.py
│   │   │   │   ├── instagram.py
│   │   │   │   ├── threads.py
│   │   │   │   ├── facebook.py
│   │   │   │   ├── x_twitter.py
│   │   │   │   ├── pinterest.py
│   │   │   │   └── google_business_profile.py
│   │   │   ├── media/
│   │   │   │   ├── providers/
│   │   │   │   │   ├── image_provider.py
│   │   │   │   │   └── video_provider.py
│   │   │   │   └── ffmpeg.py
│   │   │   ├── storage/
│   │   │   │   └── minio.py
│   │   │   ├── browser/
│   │   │   │   └── playwright.py
│   │   │   └── auth/
│   │   │       └── authlib_oauth.py
│   │   ├── mcp/
│   │   │   ├── host.py
│   │   │   ├── client.py
│   │   │   ├── discovery.py
│   │   │   └── registries/
│   │   │       └── toolset_registry.py
│   │   ├── services/
│   │   │   ├── campaign_service.py
│   │   │   ├── run_service.py
│   │   │   ├── approval_service.py
│   │   │   ├── publishing_service.py
│   │   │   ├── media_service.py
│   │   │   ├── analytics_service.py
│   │   │   ├── skill_service.py
│   │   │   ├── schedule_service.py
│   │   │   ├── sandbox_service.py
│   │   │   └── secret_service.py
│   │   ├── tasks/
│   │   │   ├── celery_app.py
│   │   │   ├── orchestrator_tasks.py
│   │   │   ├── publishing_tasks.py
│   │   │   ├── media_tasks.py
│   │   │   ├── analytics_tasks.py
│   │   │   └── beat_schedule.py
│   │   └── observability/
│   │       ├── otel.py
│   │       ├── langfuse.py
│   │       └── evals/
│   │           ├── trajectory_evals.py
│   │           ├── rubric_judges.py
│   │           └── golden_suite.py
│   ├── mcp_servers/
│   │   ├── brand_rag_server/
│   │   │   ├── main.py
│   │   │   ├── tools.py
│   │   │   └── resources.py
│   │   ├── social_gateway_server/
│   │   │   ├── main.py
│   │   │   ├── tools.py
│   │   │   └── adapters/
│   │   ├── media_studio_server/
│   │   │   ├── main.py
│   │   │   └── tasks_extension.py
│   │   └── analytics_server/
│   │       ├── main.py
│   │       └── tools.py
│   ├── skills/
│   │   ├── brand-voice-audit/
│   │   │   ├── SKILL.md
│   │   │   └── scripts/check_tone.py
│   │   ├── multi-platform-copy/
│   │   │   ├── SKILL.md
│   │   │   └── references/PLATFORM_LIMITS.md
│   │   ├── competitor-recon/
│   │   │   ├── SKILL.md
│   │   │   └── scripts/parse_serp.py
│   │   └── media-compliance/
│   │       ├── SKILL.md
│   │       └── assets/aspect_ratio_rules.json
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── evals/
│   │   └── fixtures/
│   └── scripts/
│       ├── seed_db.py
│       ├── validate_skills.py
│       └── run_local_worker.py
│
├── frontend/
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── (auth)/
│   │   │   │   └── login/page.tsx
│   │   │   └── (dashboard)/
│   │   │       ├── layout.tsx
│   │   │       ├── dashboard/page.tsx
│   │   │       ├── campaigns/
│   │   │       │   ├── page.tsx
│   │   │       │   ├── new/page.tsx
│   │   │       │   └── [campaignId]/page.tsx
│   │   │       ├── runs/
│   │   │       │   └── [runId]/page.tsx
│   │   │       ├── approvals/page.tsx
│   │   │       ├── agents/page.tsx
│   │   │       ├── skills/page.tsx
│   │   │       ├── mcp-servers/page.tsx
│   │   │       ├── media/page.tsx
│   │   │       ├── analytics/page.tsx
│   │   │       ├── schedules/page.tsx
│   │   │       ├── brands/page.tsx
│   │   │       ├── observability/page.tsx
│   │   │       └── settings/page.tsx
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   ├── layout/
│   │   │   │   ├── sidebar.tsx
│   │   │   │   ├── header.tsx
│   │   │   │   └── user-nav.tsx
│   │   │   ├── campaigns/
│   │   │   │   ├── campaign-form.tsx
│   │   │   │   ├── campaign-list.tsx
│   │   │   │   └── blueprint-viewer.tsx
│   │   │   ├── runs/
│   │   │   │   ├── graph-visualizer.tsx
│   │   │   │   ├── node-timeline.tsx
│   │   │   │   └── tool-call-inspector.tsx
│   │   │   ├── approvals/
│   │   │   │   ├── approval-card.tsx
│   │   │   │   ├── diff-viewer.tsx
│   │   │   │   └── resume-dialog.tsx
│   │   │   ├── agents/
│   │   │   ├── skills/
│   │   │   │   ├── skill-card.tsx
│   │   │   │   └── skill-editor.tsx
│   │   │   ├── media/
│   │   │   │   ├── asset-grid.tsx
│   │   │   │   └── upload-zone.tsx
│   │   │   ├── analytics/
│   │   │   │   ├── kpi-charts.tsx
│   │   │   │   └── anomaly-alert.tsx
│   │   │   └── common/
│   │   │       ├── status-badge.tsx
│   │   │       └── json-schema-form.tsx
│   │   ├── lib/
│   │   │   ├── api/
│   │   │   │   ├── client.ts
│   │   │   │   └── endpoints/
│   │   │   │       ├── campaigns.ts
│   │   │   │       ├── runs.ts
│   │   │   │       ├── approvals.ts
│   │   │   │       ├── skills.ts
│   │   │   │       ├── mcp.ts
│   │   │   │       ├── media.ts
│   │   │   │       ├── analytics.ts
│   │   │   │       └── schedules.ts
│   │   │   ├── auth/
│   │   │   │   ├── session.ts
│   │   │   │   └── token.ts
│   │   │   ├── sse/
│   │   │   │   └── run-stream.ts
│   │   │   └── utils.ts
│   │   ├── hooks/
│   │   │   ├── use-run-stream.ts
│   │   │   ├── use-approvals.ts
│   │   │   └── use-campaigns.ts
│   │   ├── stores/
│   │   │   ├── run-store.ts
│   │   │   └── ui-store.ts
│   │   ├── types/
│   │   │   ├── api.ts
│   │   │   ├── graph.ts
│   │   │   └── models.ts
│   │   └── styles/
│   │       └── globals.css
│   └── public/
│
├── packages/
│   └── contracts/
│       ├── openapi.json
│       ├── package.json
│       └── generated/
│           └── schema.ts
│
├── infra/
│   ├── podman/
│   │   ├── worker.Containerfile
│   │   ├── mcp.Containerfile
│   │   └── frontend.Containerfile
│   ├── compose/
│   │   ├── docker-compose.dev.yml
│   │   └── docker-compose.prod.yml
│   ├── postgres/
│   │   └── init.sql
│   ├── qdrant/
│   ├── minio/
│   ├── redis/
│   └── ollama/
│
├── observability/
│   ├── otel-collector/
│   │   └── config.yaml
│   ├── langfuse/
│   └── dashboards/
│
└── .github/
    └── workflows/
        ├── ci.yml
        └── eval-regression.yml
```

---

## 3. Backend Subsystem Blueprint & Module Responsibilities

The Python backend owns orchestration, state management, tool proxies, scheduling, database persistence, and observability telemetry. The Next.js frontend interacts exclusively through the FastAPI control boundary.

### 3.1 `backend/app/api/v1/` — FastAPI BFF Control Plane

All frontend UI capabilities route through validated, authenticated endpoints. Frontend code never connects directly to Qdrant, MinIO, MCP servers, or social network APIs.

| File Path | HTTP Method & Route Pattern | Responsibility & Integration Boundary |
| :--- | :--- | :--- |
| `router.py` | `APIRouter()` aggregation | Mounts all v1 sub-routers under `/api/v1`. |
| `deps.py` | `Depends()` providers | Database session (`get_db`), current user + RBAC context (`get_current_user`, `require_role`), Redis client, OTel tracer. |
| `auth.py` | `POST /auth/login`, `POST /auth/refresh` | Issues JWT access and refresh tokens, validates local user credentials against argon2id hashes. |
| `brands.py` | `GET/POST /brands`, `GET /brands/{id}` | Manages brand workspaces, guidelines, tone definitions, and default platform targets. |
| `campaigns.py` | `GET/POST /campaigns`, `GET/PATCH /campaigns/{id}` | Campaign CRUD, target objectives, audience profiles, and high-level strategy specifications. |
| `runs.py` | `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/stream` | Dispatches LangGraph thread runs, exposes real-time state transitions via Server-Sent Events (SSE). |
| `approvals.py` | `GET /approvals`, `POST /approvals/{id}/resume` | Human-in-the-loop review queue. Resumes interrupted LangGraph runs via `Command(resume=payload)`. |
| `agents.py` | `GET /agents`, `PATCH /agents/{id}/config` | Inspects agent personas, model configurations (Ollama model tag assignment), and token budgets. |
| `skills.py` | `GET /skills`, `POST /skills/validate` | Lists available progressive-disclosure `SKILL.md` packages; triggers server-side syntax and token budget validation. |
| `mcp_servers.py` | `GET /mcp-servers`, `POST /mcp-servers/{id}/sync` | Discovers registered FastMCP servers, tools, and resources; triggers `server/discover` sync. |
| `media.py` | `POST /media/upload`, `GET /media/{id}`, `GET /media/presigned` | Uploads raw assets to MinIO, generates presigned S3 URLs, records metadata in PostgreSQL. |
| `analytics.py` | `GET /analytics/kpis`, `GET /analytics/anomalies` | Returns cross-platform performance metrics, z-score alerts, and automated optimization history. |
| `schedules.py` | `GET/POST /schedules`, `DELETE /schedules/{id}` | Configures recurring Celery Beat cron tasks for content publishing, analytics ingestion, and brand audits. |
| `observability.py` | `GET /observability/traces`, `GET /observability/stats` | Surfaces Langfuse trace deep-links, Ollama inference token usage, and trajectory evaluation pass rates. |

---

### 3.2 `backend/app/orchestrator/` — LangGraph Graph Engine

This directory contains the state management, checkpointing, and execution topology of the multi-agent system.

```
                           ┌────────────────────────┐
                           │ MasterOrchestratorGraph │
                           └───────────┬────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
 ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
 │  Research & Strategy │   │ Campaign & Creative  │   │ Closed-Loop Eval     │
 │  Subgraph (ReAct)    │   │ Subgraph (Plan-Solve)│   │ Subgraph (ReWOO)     │
 └──────────────────────┘   └──────────┬───────────┘   └──────────────────────┘
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │ human_approval_gate │
                            │     interrupt()     │
                            └──────────┬──────────┘
                                       │ (Command.resume)
                                       ▼
                            ┌─────────────────────┐
                            │ Multi-Platform      │
                            │ Fan-Out Subgraph    │
                            │ (Send() Map-Reduce) │
                            └─────────────────────┘
```

#### File-by-File Responsibilities

- **`graph.py` (`MasterOrchestratorGraph`):**
  - Defines the root `StateGraph(MarketingOSState)` compiled with `PostgresSaver`.
  - Implements the supervisor routing logic, dispatching to domain subgraphs and handling global error states.
  - Enforces the hard recursion guardrail (`recursion_limit: 25`).

- **`state.py` (`MarketingOSState` & Reducers):**
  - Declares the core `TypedDict` and Pydantic schemas:
    ```python
    class MarketingOSState(TypedDict):
        thread_id: str
        campaign_id: str
        active_skills: list[str]
        research_dossier: dict
        campaign_blueprint: dict
        platform_publish_results: Annotated[list[dict], merge_platform_results]
        critique_history: Annotated[list[str], operator.add]
        revision_count: int
        approval_status: Literal["pending", "approved", "rejected"]
        analytics_anomalies: list[dict]
    ```
  - Houses the `merge_platform_results` reducer that deduplicates fan-out results using SHA-256 idempotency keys.

- **`checkpointer.py` (`PostgresSaver` Setup):**
  - Configures the asynchronous `PostgresSaver` connection pool.
  - Manages database schemas for LangGraph thread persistence (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`).

- **`routing.py` & `handoffs.py`:**
  - Implements custom handoff tools using `InjectedState`, `InjectedToolCallId`, and `Command(goto=subgraph, graph=Command.PARENT, update=...)`.
  - Configures `output_mode="last_message"` and `create_forward_message_tool` to return only verified structured summaries to the master graph, keeping the supervisor context clean.

- **`subgraphs/research_strategy.py`:**
  - **Pattern:** ReAct loop with scoped peer handoffs.
  - Coordinates exploratory market intelligence, web research via Playwright, and dense/sparse Brand RAG retrieval.

- **`subgraphs/campaign_creative.py`:**
  - **Pattern:** Plan-and-Solve with Reflexion revision loop.
  - Compiles the master `campaign.json` blueprint, generates cross-platform copy, triggers media generation handles, and evaluates drafts against tone/limit rubrics before requesting approval.

- **`subgraphs/publishing_fanout.py`:**
  - **Pattern:** Map-Reduce parallel execution using LangGraph `Send(node, payload)`.
  - Fans out publishing payloads simultaneously to all 8 platforms (LinkedIn, YouTube, Instagram, Threads, Facebook, X, Pinterest, Google Business Profile) via the `SocialGateway` MCP toolset.

- **`subgraphs/closed_loop_eval.py`:**
  - **Pattern:** ReWOO (Reasoning Without Observation) pipeline.
  - Gathers 7-day and 28-day cross-platform metrics without intermediate LLM roundtrips, computes Polars z-scores, and triggers autonomous creative adjustments.

- **`workers/`:**
  - `agent_worker_factory.py`: Instantiates ephemeral Pydantic AI `Agent` workers bound to local Ollama models (`llama3.3:70b`, `qwen2.5:14b`).
  - `retry_policies.py`: Enforces read/write retry policies (read/RAG: `retries=3`; mutating publishing: `retries=1`).

---

### 3.3 Interrupt & Checkpoint Safety Architecture

LangGraph snapshots state at **super-step boundaries** rather than inside node functions. When `Command(resume=...)` resumes execution, the interrupted node re-executes from its first line.

To avoid duplicate side effects (e.g., duplicate media generation or double API charges), approval workflows use a strict **3-Node Separation Pattern**:

```
[ prepare_publish_payload_node ] ──► (Pure transformation, writes to state)
               │
               ▼
 [ human_approval_gate_node ]   ──► (Calls interrupt(); NO external calls or mutations)
               │
               ├────────────────────────────────────────┐
               │ Resumed with Approval                  │ Resumed with Rejection
               ▼                                        ▼
[ execute_platform_publish_node ]        [ campaign_creative_revision_node ]
  (Idempotent mutations using              (Appends critique to history,
   SHA-256 idempotency_key)                 routes to Plan-and-Solve)
```

---

### 3.4 `backend/mcp_servers/` — FastMCP Capabilities (2026-07-28 Spec)

MCP servers act as zero-trust proxies between agent graphs and internal infrastructure. Agents never receive database connection strings, S3 master keys, or social platform OAuth secrets directly.

| Server Name | Transport | Resources (`resources/read`) | Tools (`tools/call`) |
| :--- | :--- | :--- | :--- |
| **`brand_rag_server`** | Streamable HTTP | `brand://guidelines/{brand_id}`<br>`brand://personas/{segment_id}` | `search_brand_knowledge` (Qdrant dense + FastEmbed BM25)<br>`retrieve_winning_campaigns`<br>`store_campaign_learnings` |
| **`social_gateway_server`** | Streamable HTTP | `social://platform_status`<br>`social://rate_limits` | `publish_to_platform(platform, payload, idempotency_key)`<br>`verify_platform_post(platform, post_id)`<br>`fetch_platform_metrics(platform, post_id)` |
| **`media_studio_server`** | Streamable HTTP + Tasks Extension | `media://asset_catalog/{campaign_id}` | `submit_image_generation_job(prompt, aspect_ratio)`<br>`submit_video_render_job(script, assets)`<br>`poll_media_job_status(task_id)`<br>`burn_subtitles(video_id, srt_content)` |
| **`analytics_server`** | Streamable HTTP | `analytics://schema`<br>`analytics://kpi_definitions` | `query_aggregated_kpis(start_date, end_date, platforms)`<br>`detect_metric_anomalies(lookback_days, z_threshold)`<br>`export_campaign_report(campaign_id)` |

- **Stateless `_meta` Envelope:** Every request validates client protocol version `2026-07-28`.
- **Dynamic Tool Availability:** When an external social API rate-limits an account, `social_gateway_server` emits `notifications/tools/list_changed` over active SSE connections.
- **Asynchronous Tasks Extension:** Long-running media jobs return a task handle immediately, allowing worker nodes to yield or poll asynchronously via Celery.

---

### 3.5 `backend/skills/` — Progressive Disclosure Agent Skills

Skills adhere to the [Agent Skills Specification](https://agentskills.io/specification). They package domain playbooks into three tiers to manage local Ollama context budgets:

```
skills/
├── brand-voice-audit/
│   ├── SKILL.md                          # Tier 1 (Frontmatter) + Tier 2 (Core logic < 500 lines)
│   └── scripts/
│       └── check_tone.py                 # Tier 3 (Executable script loaded into sandbox on demand)
├── multi-platform-copy/
│   ├── SKILL.md
│   └── references/
│       └── PLATFORM_LIMITS.md            # Tier 3 (Platform specs read only during draft compilation)
├── competitor-recon/
│   ├── SKILL.md
│   └── scripts/
│       └── parse_serp.py                 # Tier 3 (Scraper parsing utility)
└── media-compliance/
    ├── SKILL.md
    └── assets/
        └── aspect_ratio_rules.json       # Tier 3 (Aspect ratio validation schema)
```

- **Tier 1 (Catalog Index):** Fast loading of `name` and `description` (~100 tokens total) during supervisor startup.
- **Tier 2 (Activation):** Full `SKILL.md` body (<5,000 tokens) loaded into context only when the task activates that specific skill.
- **Tier 3 (Execution):** On-demand execution of `scripts/` or lookup of `references/` inside rootless Podman sandboxes.
- **CI Validation:** `scripts/validate_skills.py` runs `skills-ref validate` during CI builds.

---

### 3.6 `backend/app/tasks/` — Celery Asynchronous Infrastructure

- **`celery_app.py`:** Initializes the Celery instance configured with Redis broker and result backend.
- **Queue Partitioning:**
  - `orchestrator_queue`: High-priority LangGraph step dispatches and approval wakeups.
  - `publishing_queue`: Outbound social API publishing tasks with exponential backoff.
  - `media_queue`: Compute-heavy FFmpeg video stitching, image re-encoding, and external API polling.
  - `analytics_queue`: Batch metric ingestion and Polars anomaly computation jobs.
- **`beat_schedule.py`:** Periodic Celery Beat schedules:
  - Every 6 hours: Ingest social platform analytics and trigger closed-loop optimization.
  - Daily at 00:00 UTC: Run brand compliance audits against active campaigns.
  - Every 5 minutes: Check database for scheduled social posts requiring publishing dispatch.

---

## 4. Frontend Subsystem Blueprint & Component Specification

The management frontend is built with **Next.js (App Router)** and **TypeScript**, communicating exclusively with FastAPI.

### 4.1 Route Hierarchy & Page Responsibilities

```text
frontend/src/app/
├── layout.tsx                              # Root layout: ThemeProvider, QueryClient, AuthProvider
├── page.tsx                                # Root redirect to /dashboard or /login
├── (auth)/
│   └── login/page.tsx                      # Login screen: email/password, JWT handling
└── (dashboard)/
    ├── layout.tsx                          # Shell layout: Sidebar, Header, Breadcrumbs, Notifications
    ├── dashboard/page.tsx                  # Executive dashboard: active campaigns, pending approvals, KPIs
    ├── campaigns/
    │   ├── page.tsx                        # Campaign list table: status, target platforms, created date
    │   ├── new/page.tsx                    # Multi-step campaign creation wizard
    │   └── [campaignId]/page.tsx           # Campaign detail: strategy brief, generated assets, run history
    ├── runs/
    │   └── [runId]/page.tsx                # Real-time LangGraph execution visualizer (SSE-backed)
    ├── approvals/page.tsx                  # Human-in-the-Loop review queue: diff inspector, approve/reject
    ├── agents/page.tsx                     # Agent fleet overview: model configs, prompts, active workers
    ├── skills/page.tsx                     # Agent skills manager: inspect SKILL.md, validation badges
    ├── mcp-servers/page.tsx                # MCP server health: connection status, exposed tools/resources
    ├── media/page.tsx                      # Media asset library: MinIO browser, aspect-ratio previews
    ├── analytics/page.tsx                  # Cross-platform analytics: engagement charts, anomaly triggers
    ├── schedules/page.tsx                  # Scheduled posts & Celery Beat periodic task manager
    ├── brands/page.tsx                     # Brand workspace settings: voice guidelines, target segments
    ├── observability/page.tsx              # Langfuse trace viewer, Ollama token metrics, eval reports
    └── settings/page.tsx                   # System configuration: API keys, RBAC roles, worker sandboxes
```

---

### 4.2 Core Frontend Component Mapping

| Component Path | Functionality & Interaction Pattern |
| :--- | :--- |
| `components/runs/graph-visualizer.tsx` | Interactive DAG visualization of LangGraph nodes (Supervisor, Subgraphs, Approval Gate). Updates in real-time via SSE from `GET /api/v1/runs/{id}/stream`. |
| `components/runs/node-timeline.tsx` | Vertical execution timeline showing super-step transitions, latency, status badges, and token counts per node. |
| `components/runs/tool-call-inspector.tsx` | Collapsible drawer inspecting tool invocations: tool name, input arguments JSON, execution latency, and return payload. |
| `components/approvals/approval-card.tsx` | Summary card showing campaign context, target platforms, copy preview, and primary CTA buttons ("Approve", "Request Revision", "Reject"). |
| `components/approvals/diff-viewer.tsx` | Side-by-side visual diff showing original draft vs. agent revisions following a Reflexion feedback loop. |
| `components/approvals/resume-dialog.tsx` | Modal dialog capturing feedback notes or revision instructions, submitting `POST /api/v1/approvals/{id}/resume` to resume the graph. |
| `components/media/asset-grid.tsx` | Responsive media gallery showing MinIO assets with aspect-ratio badges (`1:1`, `9:16`, `16:9`), file sizes, and platform compatibility tags. |
| `components/analytics/anomaly-alert.tsx` | Warning banner rendering when Polars detects a z-score anomaly ($Z < -1.5$), with an "Investigate with Agent" action button. |
| `components/skills/skill-card.tsx` | Card displaying skill name, description, validation status (`skills-ref validate`), token budget footprint, and allowed tools. |

---

### 4.3 Frontend State Management & Real-Time SSE Stream Architecture

```
FastAPI (GET /api/v1/runs/{id}/stream)
                  │
                  ▼ SSE Event Stream:
                  │ event: node_start  { node: "campaign_creative", step: 3 }
                  │ event: tool_call   { tool: "search_brand_knowledge", args: {...} }
                  │ event: interrupt   { interrupt_id: "appr_123", payload: {...} }
                  │ event: node_finish { node: "campaign_creative", state_delta: {...} }
                  ▼
   useRunStream (Custom React Hook)
                  │
                  ▼ Dispatches into Zustand Store
        run-store.ts (Zustand)
         ├── activeThreadId
         ├── nodeStates: Record<string, NodeState>
         ├── liveTimeline: TimelineEvent[]
         ├── interruptPayload: InterruptData | null
         └── graphTopology: DAGDefinition
                  │
      ┌───────────┴───────────┐
      ▼                       ▼
graph-visualizer.tsx     node-timeline.tsx
```

1. **API Client (`lib/api/client.ts`):** Lightweight `fetch` wrapper with automatic JWT injection, token refresh rotation, and uniform error translation.
2. **Type Generation:** TypeScript models in `packages/contracts/generated/` are automatically synchronized from FastAPI's OpenAPI JSON export using `openapi-typescript`.
3. **Zustand State Stores:**
   - `run-store.ts`: Maintains live graph DAG state, execution timeline events, active tool calls, and pending interrupt payloads.
   - `ui-store.ts`: Governs sidebar navigation, global notification toasts, modal drawers, and active brand workspace switching.

---

## 5. Persistence, Knowledge, and Storage Layer

### 5.1 Relational Database Schema (`PostgreSQL 16+`)

Managed via SQLAlchemy 2.0 (asyncio) and Alembic migrations:

```sql
-- Core platform entities
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    voice_guidelines TEXT,
    target_segments JSONB NOT NULL DEFAULT '[]',
    default_platforms JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    objective TEXT NOT NULL,
    blueprint JSONB,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(255) UNIQUE NOT NULL,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    trigger_type VARCHAR(50) NOT NULL DEFAULT 'manual',
    current_node VARCHAR(100),
    error_message TEXT,
    token_usage JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    thread_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    step_name VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    decision_notes TEXT,
    reviewed_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE media_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    minio_bucket VARCHAR(100) NOT NULL,
    minio_key VARCHAR(500) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    width INT,
    height INT,
    aspect_ratio VARCHAR(20),
    prompt_lineage TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    cron_expression VARCHAR(100),
    scheduled_utc TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'scheduled',
    idempotency_key VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    external_post_id VARCHAR(255) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- LangGraph PostgresSaver checkpointer tables are managed directly by PostgresSaver.setup()
```

---

### 5.2 Vector Knowledge Base (`Qdrant + FastEmbed`)

- **Collections:**
  - `brand_guidelines`: Dense vectors representing brand voice documents, messaging pillars, style rules, and do/don't guidelines.
  - `historical_campaigns`: Multi-channel campaign copy and creative assets paired with historical engagement and conversion scores.
  - `market_intelligence`: Competitor intelligence, SERP research chunks, and industry trend reports.
- **Search Topology:** Hybrid retrieval combining dense vector similarity (`FastEmbed` / `nomic-embed-text`) with sparse BM25 indices, reranked before context injection.

---

### 5.3 Object Storage (`MinIO`)

- **Buckets:**
  - `marketing-raw-assets`: User-uploaded logos, product imagery, brand guidelines (PDF/DOCX), and raw video clips.
  - `marketing-generated-assets`: Final AI-generated images, synthesized video reels, compiled PDF carousels, and burned-subtitle video outputs.
  - `marketing-exports`: Compressed campaign archives, audit logs, and analytics export bundles.

---

## 6. Worker Isolation & Container Sandboxing

To safely execute untrusted dynamic code, run Playwright web scraping, and execute Agent Skill scripts (`scripts/check_tone.py`, `scripts/parse_serp.py`), tasks execute inside **Rootless Podman** sandbox containers.

```
┌────────────────────────────────────────────────────────┐
│                   CELERY TASK WORKER                   │
│             (backend/app/tasks/orchestrator_tasks.py)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼ Invokes sandbox_service.py
┌────────────────────────────────────────────────────────┐
│             ROOTLESS PODMAN CONTAINER ENGINE           │
│                                                        │
│  podman run --rm                                       │
│    --security-opt=no-new-privileges                    │
│    --cap-drop=ALL                                      │
│    --memory=512m --cpus=1.0                            │
│    --network=none                                      │
│    -v /tmp/sandboxes/job_123:/workspace:ro             │
│    marketing-os-worker-sandbox:latest                  │
│    python3 /workspace/script.py                        │
└────────────────────────────────────────────────────────┘
```

1. **Security Isolation:** `no-new-privileges`, all Linux capabilities dropped (`--cap-drop=ALL`), non-root UID/GID inside the container.
2. **Resource Boundaries:** Hard memory (512MB) and CPU (1.0 core) quotas per execution thread.
3. **Network Isolation:** Internal sandboxes execute with `--network=none` unless explicitly flagged as requiring browser connectivity for Playwright tasks.
4. **Filesystem:** Workspaces are mounted read-only (`:ro`) with an ephemeral `/tmp` volume cleared immediately upon process termination.

---

## 7. Observability, Semantic Conventions, and Evaluation Framework

### 7.1 OpenInference Span Kinds & Attribute Mapping

All traces generated across FastAPI, LangGraph nodes, Celery tasks, and FastMCP servers emit standard OpenInference attributes exported to **Langfuse**:

| Execution Context | Span Kind | Key Semantic Attributes |
| :--- | :--- | :--- |
| **Domain Subgraph / Supervisor** | `AGENT` | `agent.name`, `session.id`, `graph.node.id`, `graph.node.name`, `graph.node.parent_id` |
| **LangGraph Super-Step Transition** | `CHAIN` | `graph.node.id`, `input.value`, `output.value` |
| **Ollama LLM Call** | `LLM` | `llm.system="ollama"`, `llm.model_name`, `llm.token_count.prompt`, `llm.token_count.completion`, `llm.token_count.total` |
| **FastMCP Tool Call** | `TOOL` | `tool.name`, `tool.parameters`, `tool_call.function.name`, `tool_call.id` |
| **Brand RAG Vector Search** | `RETRIEVER` | `retrieval.documents.0.document.id`, `retrieval.documents.0.document.score` |
| **Brand Policy / Character Limit Gate** | `GUARDRAIL` | `annotation.name="compliance_gate"`, `annotation.label`, `annotation.score` |
| **Trajectory / Rubric Verification** | `EVALUATOR` | `evaluation.name`, `evaluation.score`, `evaluation.annotator_kind` (`"CODE"` or `"LLM"`) |

---

### 7.2 Multi-Layer Evaluation Pipeline

```
┌────────────────────────────────────────────────────────┐
│ Layer 1: Deterministic Pydantic & Platform Rule Checks │
│  - X character limit <= 280, Threads <= 500            │
│  - Media aspect ratios match platform spec             │
│  - Zero unverified claims / valid URL syntax           │
└───────────────────────────┬────────────────────────────┘
                            │ PASS
                            ▼
┌────────────────────────────────────────────────────────┐
│ Layer 2: Graph Trajectory & Tool-Order Evaluation      │
│  - Asserts retrieval executes before generation        │
│  - Asserts approval interrupt precedes publishing      │
│  - Verifies required tool execution sequence           │
└───────────────────────────┬────────────────────────────┘
                            │ PASS
                            ▼
┌────────────────────────────────────────────────────────┐
│ Layer 3: LLM-as-a-Judge Rubric Evaluation              │
│  - Brand Voice Fidelity Score >= 0.85                  │
│  - Groundedness / Factual Claim Score >= 0.90          │
│  - Platform-Native Engagement Score >= 0.80            │
└───────────────────────────┬────────────────────────────┘
                            │ PASS
                            ▼
┌────────────────────────────────────────────────────────┐
│ Layer 4: Offline CI/CD Golden Suite Guardrails         │
│  - Executed on pull requests via Pydantic TestModel    │
│  - 50+ benchmark scenarios tested on Phoenix/Langfuse  │
│  - Zero LLM tokens consumed for structural wiring CI   │
└────────────────────────────────────────────────────────┘
```

---

## 8. Implementation Roadmap & Verification Milestones

The platform is constructed systematically across ten implementation phases:

```
Phase 1: Monorepo & Infra Baseline
  ├── docker-compose.yml (Postgres, Redis, MinIO, Qdrant, Ollama, Langfuse)
  └── Python uv workspace + Next.js TypeScript scaffold
        │
Phase 2: Database Schema & API Foundation
  ├── SQLAlchemy async models + Alembic migrations
  └── FastAPI v1 router skeleton with Authlib JWT/RBAC
        │
Phase 3: LangGraph State & Checkpointer Engine
  ├── MarketingOSState, reducers, and PostgresSaver setup
  └── 3-Node human approval gate (interrupt / resume)
        │
Phase 4: Async Worker & Sandbox Infrastructure
  ├── Celery app, queues (orchestrator, publishing, media, analytics)
  └── Rootless Podman execution runner (sandbox_service.py)
        │
Phase 5: FastMCP Toolset Servers
  ├── BrandRAG (Qdrant + FastEmbed)
  ├── SocialGateway (8 platform proxies with encrypted secrets)
  ├── MediaStudio (MinIO storage + Tasks extension)
  └── Analytics (PostgreSQL + Polars)
        │
Phase 6: Agent Skills Standard Implementation
  ├── progressive-disclosure SKILL.md packages
  └── scripts/validate_skills.py CI checker
        │
Phase 7: Domain Subgraphs Assembly
  ├── Research & Strategy (ReAct)
  ├── Campaign & Creative (Plan-and-Solve + Reflexion)
  ├── Multi-Platform Fan-Out (Send() Map-Reduce)
  └── Closed-Loop Analytics (ReWOO)
        │
Phase 8: OpenTelemetry & Langfuse Observability
  ├── OpenInference span exporter configuration
  └── Layers 1-4 evaluation suite (deterministic, trajectory, rubric)
        │
Phase 9: Next.js Management UI
  ├── App Router dashboard shell, campaign wizard, approvals queue
  ├── Live DAG run visualizer (SSE stream integration)
  └── OpenAPI typed client (packages/contracts)
        │
Phase 10: Seed Data, Runbooks & E2E Verification
  ├── Local dev seed scripts (demo brand, pre-indexed guidelines)
  └── Golden suite regression test runbook in CI/CD
```

This blueprint provides the complete architectural foundation, concrete directory layout, and contract-first boundaries required to build the self-hosted agentic brand marketing platform.