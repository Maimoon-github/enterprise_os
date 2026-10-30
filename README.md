# Agentic Brand Marketing OS

A self-hosted, production-grade agentic brand marketing platform.
The Python backend owns the entire control plane: orchestration, LangGraph agent graphs, Model Context Protocol (MCP) servers, Agent Skills (`SKILL.md`), Celery scheduling, MinIO media assets, analytics, human approvals, and external platform integrations. The Next.js + TypeScript frontend is the management control UI that interfaces exclusively with the FastAPI backend.

---

## Architecture Blueprint

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NEXT.JS MANAGEMENT UI                           │
│  Campaigns, Real-Time Runs (SSE), HITL Approvals, Skills, MCP, Media   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ HTTP / SSE / WebSocket
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI CONTROL PLANE (BFF)                       │
│  Authlib OAuth, RBAC, Pydantic Schema Validation, Run Lifecycle        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  LANGGRAPH ORCHESTRATION ENGINE                        │
│  MasterOrchestratorGraph ◄─► PostgresSaver Checkpoints (PostgreSQL)    │
│  ├── Research & Strategy Subgraph (ReAct + Peer Handoffs)             │
│  ├── Campaign & Creative Subgraph (Plan-and-Solve + Reflexion)         │
│  ├── Human Approval Gate (Durable 3-Node interrupt())                 │
│  ├── Multi-Platform Fan-Out Subgraph (Send() Map-Reduce, 8 Platforms)  │
│  └── Closed-Loop Analytics Subgraph (ReWOO + Polars Z-Score Engine)    │
└──────────────────┬─────────────────────────────────┬───────────────────┘
                   │                                 │
                   ▼                                 ▼
┌─────────────────────────────────────┐  ┌───────────────────────────────┐
│       FASTMCP CAPABILITY SERVERS    │  │   ASYNC WORKER INFRASTRUCTURE │
│  (Streamable HTTP / stdio)          │  │   (Celery + Redis + Podman)   │
│  • BrandRAG (Qdrant + FastEmbed)    │  │  • Media processing (FFmpeg)  │
│  • SocialGateway (8 Platforms API)  │  │  • Playwright web scraping    │
│  • MediaStudio (MinIO Storage)      │  │  • Rootless Podman sandboxes  │
│  • Analytics (Polars / Postgres)    │  │  • Celery Beat scheduler      │
└──────────────────┬──────────────────┘  └───────────────┬───────────────┘
                   │                                     │
                   └──────────────────┬──────────────────┘
                                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 OPENTELEMETRY & LANGFUSE OBSERVABILITY                 │
│  OTel SDK + OpenInference Semantic Conventions ──► Langfuse (Primary)  │
│  Tracing, Token Velocity, Trajectory Gates, LLM-as-a-Judge Rubrics    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Organization

```text
.
├── backend/            # FastAPI, LangGraph, MCP Servers, Celery, Skills, DB
├── frontend/           # Next.js App Router, TypeScript, Tailwind, Zustand, SSE
├── packages/contracts/ # Shared OpenAPI specs and generated TypeScript types
├── infra/              # Containerfiles, docker-compose profiles, init SQL
├── docs/               # Architecture specifications and operational runbooks
└── observability/      # OpenTelemetry collector config and dashboard specs
```

---

## Quickstart

### 1. Prerequisites
- Docker & Docker Compose (or Podman)
- Python 3.12+ and `uv`
- Node.js 20+ and `pnpm` (or `npm`)
- Ollama running locally (`llama3.3:70b`, `qwen2.5:14b`, `nomic-embed-text`)

### 2. Environment Setup
```bash
cp .env.example .env
make setup
```

### 3. Spin up Infrastructure
```bash
make infra-up
```

### 4. Run Migrations & Seed Data
```bash
make migrate
make seed
```

### 5. Launch Development Servers
```bash
make dev
```
- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **FastAPI API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Langfuse Observability:** [http://localhost:3001](http://localhost:3001)
- **MinIO Console:** [http://localhost:9001](http://localhost:9001)
- **Qdrant Dashboard:** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
