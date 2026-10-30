# Model Context Protocol (MCP) and Agent Skills

## Model Context Protocol (MCP 2026-07-28 Spec)

The platform implements FastMCP servers that adhere strictly to the 2026-07-28 specification:

### 1. Stateless `_meta` Per-Request Envelope
Every client request injects:
```json
{
  "_meta": {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientInfo": {
      "name": "marketing-os-worker",
      "version": "1.0.0"
    },
    "io.modelcontextprotocol/clientCapabilities": {
      "elicitation": {}
    }
  }
}
```

### 2. Transport Standards
- **Streamable HTTP:** Used for long-lived shared microservices (`BrandRAG`, `SocialGateway`, `MediaStudio`, `Analytics`). Supports HTTP POST with Server-Sent Events (SSE) notification streams.
- **stdio:** Used strictly for containerized, ephemeral CLI utilities inside isolated Podman sandbox containers (logging to `stderr` to preserve JSON-RPC framing on `stdout`).

### 3. Dynamic Tool Availability & Tasks Extension
- When an external platform API rate-limits an account, `social_gateway_server` emits `notifications/tools/list_changed` over opt-in SSE subscriptions (`subscriptions/listen`).
- For media rendering and transcoding jobs, `media_studio_server` uses the **MCP Tasks Extension** to return durable task handles immediately instead of blocking worker threads.

---

## Agent Skills Standard (`SKILL.md`)

Agent skills follow the [Agent Skills Specification](https://agentskills.io/specification) using a three-tier progressive disclosure model:

1. **Tier 1 (Catalog Metadata):** `name` and `description` (~100 tokens total) indexed at orchestrator boot.
2. **Tier 2 (Activation Body):** Full `SKILL.md` (<5,000 tokens, <500 lines) dynamically injected into the worker context upon activation.
3. **Tier 3 (Execution Scripts & Assets):** Sandboxed scripts (`scripts/check_tone.py`) and schemas (`assets/aspect_ratio_rules.json`) loaded on demand.
