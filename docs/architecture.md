# Architectural Blueprint & Systems Design

## Overview
The **Agentic Brand Marketing Platform** is an enterprise-grade, self-hosted operational system designed to autonomously plan, create, approve, publish, and evaluate brand marketing campaigns across eight primary digital platforms:
1. LinkedIn
2. YouTube
3. Instagram
4. Threads
5. Facebook
6. X (formerly Twitter)
7. Pinterest
8. Google Business Profile

## Foundational Tenets
1. **Python Owns the Control Plane:** FastAPI, LangGraph, FastMCP, and Celery manage all execution graphs, memory checkpoints, external integrations, media transformations, and credentials.
2. **Next.js is the Pure Management UI:** The frontend never directly talks to databases, LLMs, MCP servers, or social network APIs. It accesses everything through validated FastAPI endpoints and listens to graph execution via Server-Sent Events (SSE).
3. **Deterministic Workflows vs. Open-Ended Reasoning:** High-risk mutating operations follow deterministic DAG pipelines with human review gates, while open-ended multi-turn ReAct loops are strictly confined to exploratory research and reconnaissance.
4. **Zero-Trust Capability Boundary:** External platform API keys and OAuth tokens are isolated inside the `SocialGateway` MCP server. Ephemeral agent workers only receive scoped tools that accept verified campaign IDs and idempotency keys.
5. **Human-in-the-Loop (HITL) Checkpoint Safety:** Graph interrupts (`interrupt()`) are strictly separated into dedicated checkpoint boundary nodes to eliminate duplicate side effects upon resumption.
