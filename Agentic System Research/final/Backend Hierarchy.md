### 1. Backend Hierarchy

```text
backend/
├── pyproject.toml
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── router.py
│   │   └── routes/
│   │       ├── directives.py
│   │       ├── tasks.py
│   │       ├── approvals.py
│   │       └── telemetry.py
│   ├── core/
│   │   ├── settings.py
│   │   └── logging.py
│   ├── schemas/
│   │   ├── governance.py
│   │   ├── task_state.py
│   │   ├── agent_contracts.py
│   │   ├── sandbox.py
│   │   ├── action_preview.py
│   │   ├── dispatch.py
│   │   ├── telemetry.py
│   │   ├── artifact.py
│   │   └── provenance.py
│   ├── orchestration/
│   │   ├── intelligence_engine.py
│   │   ├── context_assembly.py
│   │   ├── brand_persona.py
│   │   ├── dag_scheduler.py
│   │   ├── task_state_machine.py
│   │   ├── policy_evaluator.py
│   │   ├── rag_query_dispatch.py
│   │   ├── evidence_synthesis.py
│   │   ├── hitl_preview_generator.py
│   │   └── governance_milestone.py
│   ├── agents/
│   │   ├── development.py
│   │   ├── strategy.py
│   │   ├── creative_content.py
│   │   ├── product_evidence.py
│   │   ├── competitor_intel.py
│   │   ├── customer_voice.py
│   │   └── learning_performance.py
│   ├── services/
│   │   ├── policy_engine.py
│   │   ├── hitl.py
│   │   ├── task_state.py
│   │   ├── rag/
│   │   │   ├── controller.py
│   │   │   ├── hybrid_retriever.py
│   │   │   ├── freshness.py
│   │   │   └── schema_validator.py
│   │   ├── telemetry.py
│   │   ├── memory_promotion.py
│   │   └── provenance.py
│   ├── security/
│   │   ├── authorization_boundary.py
│   │   ├── cryptographic_validator.py
│   │   └── scope_evaluator.py
│   ├── mcp/
│   │   ├── host.py
│   │   ├── data_gateway.py
│   │   └── outbound_gateway.py
│   ├── integrations/
│   │   ├── llm/
│   │   │   └── client.py
│   │   ├── sandbox/
│   │   │   ├── client.py
│   │   │   └── capabilities.py
│   │   ├── cms/
│   │   │   └── client.py
│   │   ├── ads/
│   │   │   ├── meta.py
│   │   │   ├── google.py
│   │   │   ├── tiktok.py
│   │   │   └── linkedin.py
│   │   └── social/
│   │       ├── instagram.py
│   │       ├── x.py
│   │       ├── tiktok.py
│   │       └── youtube.py
│   └── persistence/
│       ├── database.py
│       └── repositories/
│           ├── operational.py
│           ├── task_state.py
│           ├── vector.py
│           ├── telemetry.py
│           ├── memory.py
│           ├── artifact.py
│           └── provenance.py
└── tests/
    ├── unit/
    │   ├── test_policy_authorization.py
    │   ├── test_task_state_machine.py
    │   ├── test_rag_governance.py
    │   ├── test_evidence_synthesis.py
    │   └── test_hitl_gate.py
    ├── integration/
    │   ├── test_worker_sandbox_boundary.py
    │   ├── test_model_a_data_access.py
    │   ├── test_outbound_after_approval.py
    │   ├── test_telemetry_learning_loop.py
    │   └── test_provenance_persistence.py
    └── acceptance/
        └── test_governed_end_to_end_flow.py
```

  

### 2. Hierarchy With Briefs

```text
backend/                                        — Python backend development root
├── pyproject.toml                              — Python project metadata and backend dependency declarations
├── app/                                        — Main backend application package
│   ├── main.py                                 — Application entrypoint and backend composition root
│   ├── api/                                    — Transport/API boundary only
│   │   ├── router.py                           — Aggregates backend API routes
│   │   └── routes/                             — Human and external-event API endpoints
│   │       ├── directives.py                   — Accepts owner objectives, scopes, budgets, and risk directives
│   │       ├── tasks.py                        — Exposes canonical task-state and workflow status operations
│   │       ├── approvals.py                    — Receives HITL decisions (approve, reject, revise, hold)
│   │       └── telemetry.py                    — Receives webhook, conversion, pixel, and event telemetry
│   ├── core/                                   — Shared backend runtime concerns
│   │   ├── settings.py                         — Runtime settings and external credential/reference configuration
│   │   └── logging.py                          — Application logging configuration
│   ├── schemas/                                — Cross-layer Python data contracts
│   │   ├── governance.py                       — Directives, policy envelopes, tenant scopes, budgets, and risk data
│   │   ├── task_state.py                       — CTS lifecycle, checkpoints, dependencies, holds, and state deltas
│   │   ├── agent_contracts.py                  — Bounded task grants, context requests, evidence envelopes, and confidence data
│   │   ├── sandbox.py                          — Backend-to-sandbox invocation and sanitized-result contracts
│   │   ├── action_preview.py                   — Spend, claims, copy, and code-diff review dossiers
│   │   ├── dispatch.py                         — Signed post-HITL execution directives
│   │   ├── telemetry.py                        — Normalized traffic, conversion, ad, social, and ROAS events
│   │   ├── artifact.py                         — UUID/hash-addressed deliverable and evidence references
│   │   └── provenance.py                       — W3C PROV audit-event contracts
│   ├── orchestration/                          — Transport-independent Intelligence Engine logic
│   │   ├── intelligence_engine.py              — Central Model-A orchestrator and multi-brand execution coordinator
│   │   ├── context_assembly.py                 — Builds policy-screened context slices for workers
│   │   ├── brand_persona.py                    — Applies tenant-specific brand rules and institutional context
│   │   ├── dag_scheduler.py                    — Schedules work according to the canonical dependency DAG
│   │   ├── task_state_machine.py               — Enforces authoritative task lifecycle transitions
│   │   ├── policy_evaluator.py                 — Applies policy decisions before delegation and execution
│   │   ├── rag_query_dispatch.py               — Provides the IE-exclusive bridge to Agentic RAG
│   │   ├── evidence_synthesis.py               — Consolidates worker evidence and confidence intervals
│   │   └── hitl_preview_generator.py           — Builds mandatory human-review action previews
│   ├── agents/                                 — Seven bounded worker-agent definitions with no direct data-store access
│   │   ├── development.py                      — W_DEV: CMS schemas, UI layouts, code diffs, and web-development work
│   │   ├── strategy.py                         — W_STRAT: omnichannel roadmaps, funnels, media mix, and budgets
│   │   ├── creative_content.py                 — W_CREAT: copy variants, hooks, visual briefs, and social schedules
│   │   ├── product_evidence.py                 — W_PROD: product specifications, evidence, claims, and compliance dossiers
│   │   ├── competitor_intel.py                 — W_COMP: pricing, ad-library, SERP, trend, and positioning intelligence
│   │   ├── customer_voice.py                   — W_VOICE: tickets, reviews, sentiment, and objection analysis
│   │   └── learning_performance.py             — W_LEARN: attribution, fatigue, decay, ROAS, and validated learning deltas
│   ├── services/                               — Application services supporting orchestration
│   │   ├── policy_engine.py                    — Produces and validates machine-readable policy and compliance envelopes
│   │   ├── hitl.py                             — Coordinates mandatory human decisions (approve, reject, revise, hold) and clearance revocation
│   │   ├── task_state.py                       — Coordinates CTS persistence, checkpoints, locks, and exceptions
│   │   ├── rag/                                — Governed Agentic RAG service
│   │   │   ├── controller.py                   — Coordinates authorized retrieval and ingestion requests
│   │   │   ├── hybrid_retriever.py             — Performs required vector/BM25 hybrid retrieval
│   │   │   ├── freshness.py                    — Enforces evidence freshness requirements
│   │   │   └── schema_validator.py             — Validates retrieved and ingested knowledge structures
│   │   ├── telemetry.py                        — Normalizes and persists omnichannel performance events
│   │   ├── memory_promotion.py                 — Promotes validated learning deltas into institutional memory
│   │   └── provenance.py                       — Records immutable entity/activity/agent audit lineage
│   ├── security/                               — Policy and authorization enforcement boundary
│   │   ├── authorization_boundary.py           — Enforces caller identity, delegation, tenant scope, risk, and attenuation
│   │   ├── cryptographic_validator.py          — Validates signed caller, approval, and execution authorization
│   │   └── scope_evaluator.py                  — Evaluates tenant scope and delegated authority
│   ├── mcp/                                    — MCP boundaries defined by the architecture
│   │   ├── host.py                             — MCP host surface owned by the Intelligence Engine
│   │   ├── data_gateway.py                     — Governed CRUD facade between Agentic RAG and systems of record
│   │   └── outbound_gateway.py                 — Post-HITL signed, rate-limited actuation boundary with final TOCTOU screening
│   ├── integrations/                           — Adapters for dependencies outside core domain logic
│   │   ├── llm/                                — Provider-neutral AI model boundary
│   │   │   └── client.py                       — Invokes the configured model/provider without coupling agents to a vendor
│   │   ├── sandbox/                            — Thin boundary around the existing agent_sandbox Python SDK
│   │   │   ├── client.py                       — Invokes existing sandbox capabilities and returns sanitized results
│   │   │   └── capabilities.py                 — Maps W_DEV–W_LEARN to S_CODE–S_ATTR sandbox capabilities
│   │   ├── cms/                                — Headless CMS integration boundary
│   │   │   └── client.py                       — Reads staged CMS data and applies approved content/schema changes
│   │   ├── ads/                                — Paid-media platform adapters
│   │   │   ├── meta.py                         — Meta campaign, targeting, bid, and telemetry adapter
│   │   │   ├── google.py                       — Google campaign, targeting, bid, and telemetry adapter
│   │   │   ├── tiktok.py                       — TikTok campaign, targeting, bid, and telemetry adapter
│   │   │   └── linkedin.py                     — LinkedIn paid-media adapter defined by the architecture
│   │   └── social/                             — Organic social-channel adapters
│   │       ├── instagram.py                    — Instagram publishing and engagement adapter
│   │       ├── x.py                            — X publishing and engagement adapter
│   │       ├── tiktok.py                       — TikTok social publishing and engagement adapter
│   │       └── youtube.py                      — YouTube publishing and engagement adapter
│   └── persistence/                            — Backend persistence boundary and repositories
│       ├── database.py                         — PostgreSQL/pgvector/TimescaleDB connection boundary
│       └── repositories/                       — Governed system-of-record access implementations
│           ├── operational.py                  — Persists enterprise directives and generated operational records
│           ├── task_state.py                   — Persists canonical task-state and dependency records
│           ├── vector.py                       — Persists and retrieves vector namespaces and embeddings
│           ├── telemetry.py                    — Persists normalized timeseries and conversion records
│           ├── memory.py                       — Persists promoted brand knowledge, heuristics, and model deltas
│           ├── artifact.py                     — Resolves immutable deliverables by UUID/hash
│           └── provenance.py                   — Appends W3C PROV audit records
└── tests/                                      — Development verification suite
    ├── unit/                                   — Isolated domain and service tests
    │   ├── test_policy_authorization.py        — Verifies policy decisions and monotonic attenuation
    │   ├── test_task_state_machine.py          — Verifies CTS transitions, holds, checkpoints, and DAG rules
    │   ├── test_rag_governance.py              — Verifies IE-only RAG access, tenant isolation, freshness, and validation
    │   ├── test_evidence_synthesis.py          — Verifies evidence-envelope consolidation and confidence handling
    │   └── test_hitl_gate.py                   — Verifies mandatory approval for spend, claims, code, and dispatch
    ├── integration/                            — Cross-boundary backend integration tests
    │   ├── test_worker_sandbox_boundary.py     — Verifies all seven workers use only the sandbox adapter
    │   ├── test_model_a_data_access.py         — Verifies workers cannot directly access RAG or persistence
    │   ├── test_outbound_after_approval.py     — Verifies external writes require signed HITL clearance
    │   ├── test_telemetry_learning_loop.py     — Verifies telemetry feeds W_LEARN and validated memory promotion
    │   └── test_provenance_persistence.py      — Verifies required control-plane and execution audit lineage
    └── acceptance/                             — Complete architecture-level validation
        └── test_governed_end_to_end_flow.py    — Verifies directive → workers → HITL → actuation → telemetry → learning flow
```

  

### 3. Sandbox Integration Boundary

```text
Existing dependency:
agent_sandbox — Already implemented; internal implementation is excluded.

Sandbox-facing backend modules:
- pyproject.toml — Declares the existing agent_sandbox Python SDK as a backend dependency.
- app/integrations/sandbox/client.py — Single backend wrapper for invoking the existing agent_sandbox SDK.
- app/integrations/sandbox/capabilities.py — Maps each bounded worker to its existing S_CODE, S_ALLOC, S_COPY, S_VAL, S_SCRAPE, S_PARSE, or S_ATTR capability.
- app/schemas/sandbox.py — Defines invocation mandates and sanitized sandbox-result contracts without exposing sandbox internals.
- app/agents/development.py — Requests S_CODE execution through the sandbox wrapper.
- app/agents/strategy.py — Requests S_ALLOC execution through the sandbox wrapper.
- app/agents/creative_content.py — Requests S_COPY execution through the sandbox wrapper.
- app/agents/product_evidence.py — Requests S_VAL execution through the sandbox wrapper.
- app/agents/competitor_intel.py — Requests S_SCRAPE execution through the sandbox wrapper.
- app/agents/customer_voice.py — Requests S_PARSE execution through the sandbox wrapper.
- app/agents/learning_performance.py — Requests S_ATTR execution through the sandbox wrapper.
- tests/integration/test_worker_sandbox_boundary.py — Verifies workers use the wrapper and never depend on sandbox internals.
```

   

### 4. Assumptions / TBD

```text
- [TBD] The Python HTTP/API framework is not specified by the attachments.
- [TBD] The LLM/model provider and Python model SDK are not specified; app/integrations/llm/client.py must remain provider-neutral.
- [TBD] The Python PostgreSQL/pgvector/TimescaleDB driver, ORM, and migration library are not specified.
- [TBD] The Headless CMS vendor/API implementation is not specified.
- [TBD] Concrete authentication credentials and OAuth details for CMS, Meta, Google, TikTok, LinkedIn, and social platforms are not provided.
- [TBD] The concrete backing technologies for the Institutional Memory Store, Artifact Registry, and W3C PROV immutable ledger are not specified beyond their required behavior.
```

 
