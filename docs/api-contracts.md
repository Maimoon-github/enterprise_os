# API Contracts & Control Plane Communication

## FastAPI Control Boundary
The Next.js management frontend communicates exclusively with FastAPI v1 endpoints under `/api/v1/`:

```
POST   /api/v1/auth/login               Issue JWT access and refresh tokens
GET    /api/v1/brands                   List brand workspaces
POST   /api/v1/brands                   Create new brand workspace
GET    /api/v1/campaigns                List campaigns with filter by brand/status
POST   /api/v1/campaigns                Create campaign blueprint
POST   /api/v1/runs                     Dispatch a new LangGraph orchestrator run
GET    /api/v1/runs/{id}                Inspect run state and thread status
GET    /api/v1/runs/{id}/stream         SSE stream of real-time node transitions
GET    /api/v1/approvals                List pending HITL approval requests
POST   /api/v1/approvals/{id}/resume    Resume interrupted graph run with decision
GET    /api/v1/skills                   List registered Agent Skills with verification status
GET    /api/v1/mcp-servers              List registered MCP servers, resources, and tools
POST   /api/v1/media/upload             Upload raw media asset to MinIO
GET    /api/v1/analytics/kpis           Retrieve aggregated cross-platform performance
GET    /api/v1/schedules                Manage Celery Beat publishing and audit schedules
GET    /api/v1/observability/traces     Retrieve Langfuse trace deep-links and evaluations
```

## SSE Streaming Event Protocol
The `GET /api/v1/runs/{id}/stream` endpoint emits structured Server-Sent Events consumed by `useRunStream` in the frontend:

```text
event: node_start
data: {"run_id": "...", "node": "campaign_creative", "step": 2, "timestamp": "2026-10-30T16:00:00Z"}

event: tool_call
data: {"tool": "search_brand_knowledge", "arguments": {"query": "Q4 tone of voice"}}

event: interrupt
data: {"interrupt_id": "appr_98234", "step_name": "human_approval_gate", "payload": {...}}

event: node_finish
data: {"node": "campaign_creative", "status": "completed", "duration_ms": 3410}
```
