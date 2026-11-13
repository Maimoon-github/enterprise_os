# business-os

Self-hosted Brand Operations OS.

| Path | Responsibility |
|------|----------------|
| `chief-of-staff/` | Python + LangGraph + FastAPI orchestrator (command, delegate, monitor, report) |
| `agents/` | Eight isolated business agents, each with its own environment and internal orchestrator |
| `shared/` | Central knowledge (PostgreSQL + Qdrant), event bus (Redis), integrations (API / MCP / adapters) |
| `dashboard/` | Next.js + TypeScript control surface |
| `infrastructure/` | Docker Compose stack |
