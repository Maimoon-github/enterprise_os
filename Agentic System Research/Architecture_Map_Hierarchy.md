### 1. Architecture-to-Django Mapping

The final logical architecture partitions the system into nine distinct planes. Below is the mapping of each architectural layer and entity to concrete Django apps and Python modules:

| Architecture Layer & Component | Django App / Module | Primary Architectural Responsibility | Key Interactions & Dependencies |
| --- | --- | --- | --- |
| **Layer 0: Governance & Human Authority Plane** (`OWNER`, `POLICY`, `HITL`) | `apps.governance` | Enforces enterprise risk tiers, multi-tenant policy rules, and human-in-the-loop (HITL) approval gates. | Intercepts task requests before orchestrator delegation; gates outbound side effects from `apps.gateways`. |
| **Layer 1: Central Control Plane** (`IE`, `REASON`, `CTS`, `PAB`) | `apps.orchestration` | Coordinates the Plan $\rightarrow$ Act $\rightarrow$ Observe $\rightarrow$ Reflect loop; maintains canonical task state; resolves brand personas; evaluates monotonic attenuation. | Interacts with `apps.governance` for policy/HITL; dispatches task grants to `apps.workers`; queries `apps.knowledge`. |
| **Layer 2: Governed Knowledge Layer** (`RAG`, `MCP_DATA`) | `apps.knowledge` | Mediates knowledge perception; handles query decomposition, vector search, freshness evaluation, and tenant filtering. | Acts as the data facade between `apps.orchestration`/`apps.workers` and the underlying persistence plane (`apps.core_data`). |
| **Layer 3: Systems of Record** (`CDB`, `CMS`, `MEM`, `ART`) | `apps.core_data` | Serves as the singular system of record for structured business records, CMS content models, vector embeddings, and immutable artifacts. | Implements the mandatory 7-tuple metadata contract; blocks direct agent mutations; commits via `apps.orchestration`. |
| **Layer 4: Bounded Worker Agent Layer** (`W_PROD`, `W_VOICE`, `W_COMP`, `W_STRAT`, `W_CREAT`, `W_DEV`, `W_PERF`) | `apps.workers` | Houses the seven domain-specific execution engines responsible for bounded workstream planning, drafting, and evidence assembly. | Receives `BoundedTaskGrant` from `apps.orchestration`; requests context from `apps.knowledge`; delegates to `apps.subagents`. |
| **Layer 5: Specialist Sub-Agents** (`S_VAL`, `S_PARSE`, `S_SCRAPE`, `S_ALLOC`, `S_COPY`, `S_CODE`, `S_ATTR`) | `apps.subagents` | Houses isolated, ephemeral micro-agents executing atomic tools (e.g., regex linters, syntax checkers, ad library scrapers). | Subordinate to `apps.workers`; operates inside an ephemeral session that terminates upon subtask completion. |
| **Layer 6: Governed Execution Gateways** (`MCP_ACT`) | `apps.gateways` | Actuation and publishing choke-point; enforces cryptographic approval token verification and schema validation before dispatch. | Authorized exclusively by `apps.orchestration` post-HITL; routes external side effects to `apps.telemetry`/external runtimes. |
| **Layer 7: External Endpoints & Telemetry** (`CH_STORE`, `CH_ADS`, `CH_SOC`, `TELEMETRY`) | `apps.telemetry` | Webhook ingestion and event stream normalization for external ad platforms, social channels, and headless storefronts. | Streams performance telemetry into `apps.core_data`; consumed by `W_PERF` in `apps.workers` for closed-loop learning. |
| **Layer 8: Audit & Lineage Ledger** (`AUDIT`) | `apps.governance.audit` | Permanent, append-only, cryptographically chained W3C PROV ledger recording all delegations, approvals, and mutations. | Subscribed to state transitions from `apps.orchestration`, `apps.core_data`, and `apps.gateways`. |

---

### 2. Final Project Folder/File Hierarchy

```text
enterprise_os/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── urls.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       ├── local.py
│       └── test.py
├── apps/
│   ├── __init__.py
│   ├── core_data/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── enterprise.py
│   │   │   ├── content.py
│   │   │   ├── vectors.py
│   │   │   ├── artifacts.py
│   │   │   └── telemetry.py
│   │   ├── managers.py
│   │   ├── services.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       └── test_anti_replication.py
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── policy.py
│   │   ├── hitl.py
│   │   ├── audit.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_hitl.py
│   │       └── test_audit_integrity.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── engine.py
│   │   ├── state_machine.py
│   │   ├── personas.py
│   │   ├── commit_gate.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_engine.py
│   │       └── test_state_machine.py
│   ├── knowledge/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── rag_controller.py
│   │   ├── retrieval_boundary.py
│   │   ├── evaluators.py
│   │   ├── memory_store.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_rag.py
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── base.py
│   │   ├── product_evidence.py
│   │   ├── customer_voice.py
│   │   ├── competitor_intel.py
│   │   ├── strategy.py
│   │   ├── creative_content.py
│   │   ├── development.py
│   │   ├── performance_learning.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_workers.py
│   ├── subagents/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── base.py
│   │   ├── micro_tools/
│   │   │   ├── __init__.py
│   │   │   ├── linters.py
│   │   │   ├── parsers.py
│   │   │   ├── scrapers.py
│   │   │   └── allocators.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_subagents.py
│   ├── gateways/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── mcp_actuation.py
│   ### 1. Architecture-to-Django Mapping

The final logical architecture partitions the system into nine distinct planes. Below is the mapping of each architectural layer and entity to concrete Django applications and Python modules:

| Architecture Component | Django App / Module | Primary Responsibility | Key Interactions & Dependencies |
| :--- | :--- | :--- | :--- |
| **Governance Plane** (`OWNER`, `POLICY`, `HITL`) | `apps.governance` | Enforces enterprise risk tiers, multi-tenant policy rules, and human-in-the-loop (HITL) approval gates. | Intercepts task requests before orchestrator delegation; gates outbound side effects from `apps.gateways`. |
| **Control Plane** (`IE`, `REASON`, `CTS`, `PAB`) | `apps.orchestration` | Coordinates the Plan $\rightarrow$ Act $\rightarrow$ Observe $\rightarrow$ Reflect loop; maintains canonical task state; resolves brand personas; evaluates monotonic attenuation. | Interacts with `apps.governance` for policy/HITL; dispatches task grants to `apps.workers`; queries `apps.knowledge`. |
| **Governed Knowledge Layer** (`RAG`, `MCP_DATA`) | `apps.knowledge` | Mediates knowledge perception; handles query decomposition, vector search, freshness evaluation, and tenant filtering. | Acts as the data facade between `apps.orchestration`/`apps.workers` and the underlying persistence plane (`apps.core_data`). |
| **Systems of Record** (`CDB`, `CMS`, `MEM`, `ART`) | `apps.core_data` | Serves as the singular system of record for structured business records, CMS content models, vector embeddings, and immutable artifacts. | Implements the mandatory 7-tuple metadata contract; blocks direct agent mutations; commits via `apps.orchestration`. |
| **Worker Agent Layer** (`W_PROD`, `W_VOICE`, `W_COMP`, `W_STRAT`, `W_CREAT`, `W_DEV`, `W_PERF`) | `apps.workers` | Houses the seven domain-specific execution engines responsible for bounded workstream planning, drafting, and evidence assembly. | Receives `BoundedTaskGrant` from `apps.orchestration`; requests context from `apps.knowledge`; delegates to `apps.subagents`. |
| **Specialist Sub-Agents** (`S_VAL`, `S_PARSE`, `S_SCRAPE`, `S_ALLOC`, `S_COPY`, `S_CODE`, `S_ATTR`) | `apps.subagents` | Houses isolated, ephemeral micro-agents executing atomic tools (e.g., regex linters, syntax checkers, ad library scrapers). | Subordinate to `apps.workers`; operates inside an ephemeral session that terminates upon subtask completion. |
| **Execution Gateways** (`MCP_ACT`) | `apps.gateways` | Actuation and publishing choke-point; enforces cryptographic approval token verification and schema validation before dispatch. | Authorized exclusively by `apps.orchestration` post-HITL; routes external side effects to `apps.telemetry`/external runtimes. |
| **External Endpoints & Telemetry** (`CH_STORE`, `CH_ADS`, `CH_SOC`, `TELEMETRY`) | `apps.telemetry` | Webhook ingestion and event stream normalization for external ad platforms, social channels, and headless storefronts. | Streams performance telemetry into `apps.core_data`; consumed by `W_PERF` in `apps.workers` for closed-loop learning. |
| **Audit Ledger** (`AUDIT`) | `apps.governance.audit` | Permanent, append-only, cryptographically chained W3C PROV ledger recording all delegations, approvals, and mutations. | Subscribed to state transitions from `apps.orchestration`, `apps.core_data`, and `apps.gateways`. |

---

### 2. Final Project Folder/File Hierarchy

```text
enterprise_os/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── urls.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       ├── local.py
│       └── test.py
├── apps/
│   ├── __init__.py
│   ├── core_data/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── enterprise.py
│   │   │   ├── content.py
│   │   │   ├── vectors.py
│   │   │   └── artifacts.py
│   │   ├── managers.py
│   │   ├── services.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_models.py
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── policy.py
│   │   ├── hitl.py
│   │   ├── audit.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_governance.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── engine.py
│   │   ├── state_machine.py
│   │   ├── personas.py
│   │   ├── commit_gate.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_orchestration.py
│   ├── knowledge/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── rag_controller.py
│   │   ├── retrieval_boundary.py
│   │   ├── evaluators.py
│   │   ├── memory_store.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_rag.py
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── base.py
│   │   ├── engines/
│   │   │   ├── __init__.py
│   │   │   ├── product_evidence.py
│   │   │   ├── customer_voice.py
│   │   │   ├── competitor_intel.py
│   │   │   ├── strategy.py
│   │   │   ├── creative_content.py
│   │   │   ├── development.py
│   │   │   └── performance_learning.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_workers.py
│   ├── subagents/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── base.py
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── claim_validator.py
│   │   │   ├── sentiment_parser.py
│   │   │   ├── price_scraper.py
│   │   │   ├── budget_allocator.py
│   │   │   ├── copy_drafter.py
│   │   │   ├── component_coder.py
│   │   │   └── attribution_modeler.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       └── test_sub### 1. Architecture-to-Django Mapping

The logical architecture organizes system responsibilities into dedicated enterprise tiers. The table below maps each component directly to its concrete Django app and Python module implementation:

| Architecture Layer & Component | Django App / Module | Primary Responsibility | Key Interactions & Dependencies |
| :--- | :--- | :--- | :--- |
| **Governance & HITL** (`OWNER`, `POLICY`, `HITL`) | `apps.governance` | Enforces enterprise risk tiers, multi-tenant rules, policy boundaries, and cryptographic HITL approval gates. | Intercepts task requests before orchestrator delegation; gates outbound side effects from `apps.gateways`. |
| **Control Plane** (`IE`, `REASON`, `CTS`, `PAB`) | `apps.orchestration` | Coordinates the Plan-Act-Observe-Reflect loop; maintains canonical task state; resolves brand personas; evaluates monotonic attenuation. | Interacts with `apps.governance` for policy/HITL; dispatches task grants to `apps.workers`; queries `apps.knowledge`. |
| **Governed Knowledge Layer** (`RAG`, `MCP_DATA`) | `apps.knowledge` | Mediates knowledge perception; handles query decomposition, vector search, freshness evaluation, and tenant-level filtering. | Serves as the data access facade between `apps.orchestration`/`apps.workers` and the underlying persistence layer (`apps.core_data`). |
| **Systems of Record** (`CDB`, `CMS`, `MEM`, `ART`) | `apps.core_data` | Functions as the single system of record for structured business records, CMS content models, vector embeddings, and immutable artifacts. | Implements the mandatory 7-tuple metadata contract; blocks direct agent mutations; commits state strictly through `apps.orchestration`. |
| **Worker Agent Layer** (`W_PROD`, `W_VOICE`, `W_COMP`, `W_STRAT`, `W_CREAT`, `W_DEV`, `W_PERF`) | `apps.workers` | Encapsulates the seven domain-specific execution engines responsible for bounded workstream planning, drafting, and evidence assembly. | Receives `BoundedTaskGrant` from `apps.orchestration`; requests context from `apps.knowledge`; delegates tasks to `apps.subagents`. |
| **Specialist Sub-Agents** (`S_VAL`, `S_PARSE`, `S_SCRAPE`, `S_ALLOC`, `S_COPY`, `S_CODE`, `S_ATTR`) | `apps.subagents` | Executes atomic, single-purpose micro-tools (regex linters, syntax validators, ad library scrapers). | Subordinate to `apps.workers`; runs inside an ephemeral session that terminates upon subtask completion. |
| **Execution Gateways** (`MCP_ACT`) | `apps.gateways` | Actuation and publishing gateway; enforces cryptographic approval token verification and schema validation before dispatch. | Authorized exclusively by `apps.orchestration` post-HITL; dispatches external actions to `apps.telemetry` and external runtimes. |
| **External Endpoints & Telemetry** (`CH_STORE`, `CH_ADS`, `CH_SOC`, `TELEMETRY`) | `apps.telemetry` | Ingests and normalizes webhook events and performance streams from ad platforms, social channels, and headless storefronts. | Streams performance telemetry into `apps.core_data`; consumed by `W_PERF` in `apps.workers` for closed-loop learning. |
| **Audit Ledger** (`AUDIT`) | `apps.governance.audit` | Records an append-only, cryptographically chained W3C PROV ledger tracking all delegations, approvals, and mutations. | Subscribes to events and state transitions emitted by `apps.orchestration`, `apps.core_data`, and `apps.gateways`. |

---

### 2. Final Project Folder/File Hierarchy

```text
enterprise_os/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── urls.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       ├── local.py
│       └── test.py
├── apps/
│   ├── __init__.py
│   ├── core_data/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py
│   │   ├── managers.py
│   │   ├── services.py
│   │   └── tests.py
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── policy.py
│   │   ├── hitl.py
│   │   ├── audit.py
│   │   ├── api.py
│   │   └── tests.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── engine.py
│   │   ├── state_machine.py
│   │   ├── personas.py
│   │   ├── commit_gate.py
│   │   ├── api.py
│   │   └── tests.py
│   ├── knowledge/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── rag_controller.py
│   │   ├── retrieval_boundary.py
│   │   ├── evaluators.py
│   │   ├── memory_store.py
│   │   └── tests.py
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── base.py
│   │   ├── product_evidence.py
│   │   ├── customer_voice.py
│   │   ├── competitor_intel.py
│   │   ├── strategy.py
│   │   ├── creative_content.py
│   │   ├── development.py
│   │   ├── performance_learning.py
│   │   └── tests.py
│   ├── subagents/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── base.py
│   │   ├── tools.py
│   │   └── tests.py
│   ├── gateways/
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── mcp_actuation.py
│   │   ├── security.py
│   │   └── tests.py
│   └── telemetry/
│       ├── __init__.py
│       ├── apps.py
│       ├── models.py
│       ├── ingestion.py
│       ├── api.py
│       └── tests.py

```

---

### 3. Brief of Each Major Directory/File

* **`config/settings/`**: Modular Django settings separating shared configurations (`base.py`), local development parameters (`local.py`), and test runners (`test.py`).
* **`apps/core_data/`**: Singular system of record.
* `models.py`: Defines `EnterpriseRecord`, `ContentModelRecord`, `VectorChunkRecord`, and `DurableArtifactRecord`, enforcing the 7-tuple metadata contract.
* `managers.py`: Database query managers implementing tenant row-level security (RLS) enforcement.
* `services.py`: Internal persistence routines called strictly by the orchestrator.


* **`apps/governance/`**: Guardrail and compliance layer.
* `policy.py`: Evaluates tenant risk constraints and monotonic capability rules.
* `hitl.py`: State handler for human approvals and cryptographic signature validation.
* `audit.py`: Append-only hash-chained W3C PROV ledger service.


* **`apps/orchestration/`**: Central control plane.
* `engine.py`: Central Orchestrator managing task lifecycles and capability allowlists.
* `state_machine.py`: Deterministic task state machine with checkpoint/rollback capabilities.
* `commit_gate.py`: Validation gatekeeper intercepting and committing worker write proposals.
* `personas.py`: Dynamically compiles brand voice and design tokens into task grants.


* **`apps/knowledge/`**: Governed perception and retrieval.
* `rag_controller.py`: Manages iterative query decomposition, routing, and synthesis.
* `retrieval_boundary.py`: Pre-retrieval access control filtering by tenant and classification.
* `evaluators.py`: Corrective RAG (CRAG) inspector checking relevance, conflicts, and freshness.
* `memory_store.py`: Durable institutional knowledge and promotion registry.


* **`apps/workers/`**: Domain execution engines.
* `base.py`: Abstract worker interface establishing contract validation and evidence envelope emission.
* Engine modules (`product_evidence.py` through `performance_learning.py`): Concrete domain coordinators.


* **`apps/subagents/`**: Specialist micro-execution layer.
* `base.py`: Ephemeral sub-agent session harness with automatic lifecycle termination.
* `tools.py`: Bounded micro-tools (regex linters, claim checkers, scrapers, syntax validators).


* **`apps/gateways/`**: Actuation choke-point.
* `mcp_actuation.py`: Standardized Model Context Protocol client dispatching outbound payloads.
* `security.py`: Verifies cryptographic approval tokens and platform-specific API credentials.


* **`apps/telemetry/`**: Telemetry perception engine.
* `ingestion.py`: Normalizes incoming webhooks and event logs from ad channels and web storefronts.
* `api.py`: Ingestion endpoints receiving external events.



---

### 4. Component-to-Module Mapping

| Architectural Entity | Concrete Python Class / Module Interface |
| --- | --- |
| **Governance Metadata (7-tuple)** | `apps.core_data.models.GovernanceMetadata` (Composite model/mixin) |
| **Central Enterprise DB (`CDB`)** | `apps.core_data.models.EnterpriseRecord` & `VectorChunkRecord` |
| **Headless CMS (`CMS`)** | `apps.core_data.models.ContentModelRecord` |
| **Institutional Memory (`MEM`)** | `apps.knowledge.memory_store.InstitutionalMemoryStore` |
| **Artifact Registry (`ART`)** | `apps.core_data.models.DurableArtifactRecord` |
| **Policy Engine (`POLICY`)** | `apps.governance.policy.EnterprisePolicyEngine` |
| **HITL Gate (`HITL`)** | `apps.governance.hitl.HITLApprovalGate` |
| **Audit Ledger (`AUDIT`)** | `apps.governance.audit.W3CProvAuditLedger` |
| **Intelligence Engine (`IE`)** | `apps.orchestration.engine.IntelligenceEngine` |
| **Task State Machine (`CTS`)** | `apps.orchestration.state_machine.CanonicalTaskStateLedger` |
| **Orchestrator Commit Gate** | `apps.orchestration.commit_gate.OrchestratorCommitGate` |
| **Agentic RAG Controller (`RAG`)** | `apps.knowledge.rag_controller.AgenticRAGController` |
| **Worker Engines (`W_*`)** | `apps.workers.<domain>.py` subclassing `apps.workers.base.BaseWorkerEngine` |
| **Sub-Agents (`S_*`)** | `apps.subagents.base.EphemeralSubAgent` invoking `apps.subagents.tools` |
| **Actuation Gateway (`MCP_ACT`)** | `apps.gateways.mcp_actuation.ActuationMCPGateway` |
| **Telemetry Engine (`TELEMETRY`)** | `apps.telemetry.ingestion.TelemetryIngestionService` |

---

### 5. Development Request/Data Flow

#### Forward Execution Flow (Objective to Governed Actuation)

1. **Intake:** Client sends `POST /api/v1/orchestration/tasks/`. Handled by `apps.orchestration.api`. Task objective, tenant ID, and constraints are bound into a `CanonicalTaskState` record.
2. **Policy Verification:** `apps.orchestration.engine` queries `apps.governance.policy` to evaluate tenant permissions and assign the appropriate risk tier.
3. **Perception & Retrieval:** The engine queries `apps.knowledge.rag_controller`. The RAG controller enforces tenant filters through `apps.knowledge.retrieval_boundary` and retrieves records from `apps.core_data.models`.
4. **Worker Delegation:** The engine issues a `BoundedTaskGrant` to appropriate engines in `apps.workers`.
5. **Specialist Sub-Tasking:** Worker engines spawn an `EphemeralSubAgent` from `apps.subagents.base` with a single micro-tool from `apps.subagents.tools`. Output returns as an atomic result, and the sub-agent terminates.
6. **Proposal Consolidation:** The worker packages results into an `EvidenceEnvelope` and submits a `WriteProposal` to `apps.orchestration.commit_gate`.
7. **HITL Review:** If the task is classified as high-impact (e.g., financial spend, live publishing), `apps.orchestration.state_machine` pauses at `BLOCKED_HITL`. An authorized reviewer approves via `apps.governance.api`, generating a signed clearance token.
8. **Actuation:** With clearance confirmed, `apps.orchestration.engine` instructs `apps.gateways.mcp_actuation` to dispatch the payload to external runtimes.
9. **Audit Emission:** Every lifecycle transition and payload hash is appended to `apps.governance.audit`.

#### Reverse Closed-Loop Learning Flow (Telemetry to Strategy Optimization)

1. **Event Ingestion:** External platforms send telemetry to `POST /api/v1/telemetry/events/`. `apps.telemetry.ingestion` normalizes the payload and persists raw events to `apps.core_data.models.TelemetryRecord`.
2. **Evaluation & Attribution:** `apps.workers.performance_learning` consumes new telemetry timeseries data and calculates attribution curves and fatigue decay.
3. **Memory Delta Formulation:** The engine formulates a proposed institutional memory update and submits it to `apps.knowledge.memory_store`.
4. **Promotion:** `apps.orchestration.engine` reviews and promotes the update to long-term memory, adjusting brand persona parameters for subsequent orchestration runs.

---

### 6. Required Python Packages

* **`Django`**: Core web framework, ORM, migration system, and application registry. Used by all apps.
* **`djangorestframework`**: Serializers, API views, and authentication handlers for REST endpoints. Used across `apps.orchestration.api`, `apps.governance.api`, and `apps.telemetry.api`.
* **`django-environ`**: 12-factor environment variable parsing for configuration hygiene. Used in `config/settings/`.
* **`psycopg[binary]`**: Modern, async-capable PostgreSQL driver supporting connection pooling. Used for primary database connections.
* **`pgvector`**: Native PostgreSQL vector search integration for Django ORM. Used in `apps.core_data.models.vectors` and `apps.knowledge`.
* **`pydantic`**: Strict data validation for task grants, evidence envelopes, and tool schemas. Used in `apps.orchestration`, `apps.workers`, and `apps.subagents`.
* **`langgraph`**: Graph-based state machine providing deterministic checkpoints, cyclic workflows, and `interrupt()` primitives. Used in `apps.orchestration.state_machine`.
* **`langchain-core`**: Base abstractions for message structures, tool calls, and prompt templates. Used in `apps.orchestration` and `apps.knowledge`.
* **`langchain-anthropic`**: Primary LLM interface for Claude models driving orchestration and worker reasoning. Used in `apps.orchestration.engine` and `apps.workers`.
* **`mcp`**: Official Python SDK for Model Context Protocol client/server transports and protocol compliance. Used in `apps.gateways.mcp_actuation`.
* **`pytest-django`**: Testing harness for Django database models, fixtures, and API client calls. Used in all test modules.

---

### 7. requirements.txt

```text
# Core Django & Framework
Django==6.1.1
djangorestframework==3.16.1
django-environ==0.12.0
django-filter==25.1

# Database & Vector Engine
psycopg[binary]==3.3.5
pgvector==0.4.1

# Data Validation & Schemas
pydantic==2.11.7

# Agent Orchestration & LLM Tooling
langgraph==1.0.8
langchain-core==1.3.0
langchain-anthropic==1.3.0
mcp==1.2.0

# Testing & Development Utilities
pytest==8.4.1
pytest-django==4.11.1
pytest-asyncio==0.26.0

```

---

### 8. Environment Variables / .env.example

```bash
# Django Core Settings
DEBUG=True
SECRET_KEY=dev-insecure-secret-key-change-in-production-1234567890
ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SETTINGS_MODULE=config.settings.local

# Database Configuration (PostgreSQL with pgvector)
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/enterprise_os_dev

# Model Providers
ANTHROPIC_API_KEY=sk-ant-api03-dev-mock-key

# MCP Actuation Gateway
MCP_ACTUATION_ENDPOINT=https://mcp-gateway.internal/v1
MCP_CLIENT_ID=dev_client_orchestrator
MCP_CLIENT_SECRET=dev_secret_gateway_token

# Governance & Security
HITL_AUTO_APPROVE_LOW_RISK=False
DEFAULT_TENANT_ID=tenant_default_brand
AUDIT_LOG_STORAGE_PATH=/tmp/enterprise_audit_prov/

```

---

### 9. Development Setup Commands

```bash
# 1. Create and activate a Python virtual environment
python3.11 -m venv venv
source venv/bin/activate

# 2. Upgrade core packaging tools and install verified dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 3. Provision development environment file
cp .env.example .env

# 4. Generate and apply database migrations
python manage.py makemigrations
python manage.py migrate

# 5. Verify system configuration and test suite execution
python manage.py check
pytest

```

---

### 10. Testing Structure

```text
tests/
├── conftest.py
├── integration/
│   ├── test_end_to_end_flow.py
│   ├── test_closed_loop_telemetry.py
│   └── test_mcp_actuation_boundary.py
└── unit/
    ├── test_core_data_invariants.py
    ├── test_governance_policy.py
    ├── test_hitl_checkpoints.py
    ├── test_orchestration_state.py
    ├── test_rag_isolation.py
    └── test_monotonic_attenuation.py

```

#### Primary Verification Focus Areas

* **`test_core_data_invariants.py`**: Verifies that any model creation in `apps.core_data` without the mandatory 7-tuple metadata raises `ValidationError`, and confirms that subordinate agents attempting direct ORM writes are blocked.
* **`test_monotonic_attenuation.py`**: Validates that sub-agent capability allowlists are strictly calculated as the intersection of host policy, worker task grant, and server authorizations.
* **`test_hitl_checkpoints.py`**: Validates that tasks entering high-impact states freeze at `BLOCKED_HITL`, persist an uncorrupted checkpoint in `apps.orchestration`, and resume only upon receiving a cryptographically valid approval signature.
* **`test_rag_isolation.py`**: Tests `apps.knowledge` retrieval boundary to guarantee cross-tenant queries return zero matches even when vector similarity is high.

---

### 11. Architecture Decisions & Assumptions

* **Django ORM as Central Database (`CDB`) Authority:** The Django ORM handles all relational tables and vector chunk indices (via `pgvector`). This avoids managing an external database engine while maintaining full SQL transaction isolation, schema versioning, and row-level multi-tenancy.
* **Separation of Proposal from Persistence:** The ORM's standard `.save()` method is wrapped or restricted on core models. Subordinate workers interact with `OrchestratorCommitGate`, submitting `WriteProposal` objects that must clear validation checks before database commits occur.
* **Stateless Agents with Stateful Orchestration:** Worker and sub-agent classes are stateless execution frames. All state is externalized into Django database models and LangGraph checkpointers, ensuring operations can be paused, retried, or rolled back deterministically.
* **Local MCP Transport for Development:** While production environments use remote HTTP/SSE for MCP, development uses `stdio` or in-memory pipe transports via the `mcp` library to minimize local setup overhead.

---

### 12. Web Research Sources

* **Django Project Documentation**: Official release roadmap and version compatibility guidelines ([Django Download](https://www.djangoproject.com/download/)).
* **Django REST Framework (DRF)**: PyPI releases and official documentation ([DRF on PyPI](https://pypi.org/project/djangorestframework/)).
* **Psycopg 3**: Official PostgreSQL adapter documentation for modern Python/Django configurations ([Psycopg on PyPI](https://pypi.org/project/psycopg/)).
* **Pgvector Python**: Official documentation and PyPI releases for vector search extensions in Django/PostgreSQL ([pgvector-python GitHub](https://github.com/pgvector/pgvector-python)).
* **LangGraph Core**: Official LangChain API reference for graph runtimes, checkpointing, and `interrupt()` primitives ([LangGraph Documentation](https://docs.langchain.com/oss/python/langgraph/graph-api)).
* **Model Context Protocol (MCP)**: Official architecture specification for client-server protocol isolation ([Model Context Protocol](https://modelcontextprotocol.io/specification/2026-07-28/architecture)).