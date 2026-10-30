# Agent Graphs, Subgraphs & Multi-Agent Topologies

## Orchestrator Topology

The platform deploys a **Three-Tier Hybrid Graph Topology**:

```
 Tier 1: Master Orchestrator (Supervisor)
         │ [Command.PARENT handoffs, output_mode="last_message"]
         ▼
 Tier 2: Domain Subgraphs
   ├── Research & Strategy Subgraph (ReAct + Peer Handoffs)
   ├── Campaign & Creative Subgraph (Plan-and-Solve + Reflexion)
   ├── Human Approval Gate (interrupt() at super-step boundary)
   ├── Multi-Platform Fan-Out Subgraph (Send() Map-Reduce, 8 Platforms)
   └── Closed-Loop Analytics Subgraph (ReWOO DAG, Polars Z-Scores)
         │
         ▼
 Tier 3: Ephemeral Leaf Workers
   └── Pydantic AI Agents (Scoped tools, BaseModel output_type, strict retries)
```

## Core Subgraph Behaviors

### 1. Research & Strategy Subgraph
- Operates via an exploratory ReAct loop.
- Uses `BrandKnowledgeMCP` to query Qdrant (dense vectors) and FastEmbed (sparse BM25).
- Spawns Playwright browser tasks inside rootless Podman sandboxes to gather competitor SERP signals.
- Synthesizes findings into a verified `ResearchDossier` Pydantic payload.

### 2. Campaign & Creative Subgraph
- Implements a **Plan-and-Solve** pipeline to construct the comprehensive `campaign.json` specification.
- Generates tailored copy for each platform adhering to platform constraints (e.g. 280 chars for X, 500 for Threads, 3,000 for LinkedIn).
- Submits asynchronous image/video rendering tasks to `MediaStudioMCP`.
- Applies a **Reflexion** evaluation loop (`max_revisions: 2`) to ensure brand voice compliance and tone rubrics before presenting to humans.

### 3. Human Approval Gate
- Calls `interrupt()` to snapshot state to PostgreSQL via `PostgresSaver`.
- Exposes pending state to the Next.js approvals queue.
- Resumes cleanly via `Command(resume={"approved": true, "notes": "..."})`.

### 4. Multi-Platform Fan-Out Subgraph
- Uses LangGraph's dynamic `Send("publish_platform_worker", payload)` primitive.
- Concurrently dispatches 8 platform-specific workers.
- Each worker calls `SocialGatewayMCP.publish_to_platform(..., idempotency_key=...)`.
- Merges results into state via `merge_platform_results` reducer.

### 5. Closed-Loop Analytics Subgraph
- Implements a **ReWOO** (Reasoning Without Observation) pipeline.
- Emits symbolic variable placeholders (`#E1`, `#E2`, ...) to parallel-fetch cross-platform metrics without LLM chatter.
- Computes 7-day and 28-day z-scores using Polars.
- Automatically flags anomalies ($Z < -1.5$) to generate optimization recommendations.
