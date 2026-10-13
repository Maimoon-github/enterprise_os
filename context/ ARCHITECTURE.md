Here is the complete architectural specification for the Universal AI Brand Strategy Engine, designed to orchestrate local [Ollama](https://github.com/ollama/ollama) models using the [Google Antigravity SDK](https://antigravity.google/docs/sdk/overview/) alongside an internalized, sandboxed VNC desktop browser environment.

### Executive System Scope & Operational Modalities

The engine operates as a containerized, local-first intelligence platform executing automated empirical reconnaissance, commercial diagnostic audits, and adversarial verification across three distinct operating modes:

* **Mode A (Personal Branding & Portfolio Strategy)**: Tailored for software engineers, consultants, data scientists, and creators. It audits above-the-fold positioning, proof-of-work discoverability, technical stack authority, case study conversion architecture, and social validation footprints (GitHub, LinkedIn, X).
* **Mode B (eCommerce Growth Strategy)**: Tailored for DTC brands and digital product merchants. It evaluates collection navigation, cart abandonment triggers, product detail page (PDP) conversion barriers, shipping/return policy transparency, semantic product schema, and unit-economic growth loops.
* **Mode C (Shared Strategic Intelligence Core)**: The shared multi-agent orchestration fabric underpinning both modes. It standardizes headless VNC browser automation, deterministic evidence indexing, customer persona synthesis, context-isolated state transitions, and adversarial validation.

```
                           ┌─────────────────────────────────────────────────────────────┐
                           │          Brand Strategy Orchestrator (Agent 0)              │
                           │     [Google Antigravity SDK Supervisor | Qwen 2.5 72B]      │
                           └──────┬───────────────────────────────┬────────────────▲─────┘
                                  │ (Task Delegation Slice)       │                │
            ┌─────────────────────▼────────┐             ┌────────▼────────┐       │ (Adversarial
            │  1. Website & Social Analyst │             │  2. Audience    │       │  Revisions
            │     [Llama 3.2 Vision 11B]   │             │     Strategist  │       │  Max 3 Loops)
            └──────────────┬───────────────┘             │  [Qwen 2.5 32B] │       │
                           │                             └────────┬────────┘       │
                           └───────────────┬──────────────────────┘                │
                                           ▼                                       │
                            ┌─────────────────────────────┐                        │
                            │    3. Brand Strategist      │                        │
                            │       [Qwen 2.5 32B]        │                        │
                            └──────────────┬──────────────┘                        │
                                           ▼                                       │
                            ┌─────────────────────────────┐                        │
                            │ 4. SEO & Content Strategist │                        │
                            │       [Qwen 2.5 32B]        │                        │
                            └──────────────┬──────────────┘                        │
                                           ▼                                       │
                            ┌─────────────────────────────┐                        │
                            │    5. Growth Strategist     │                        │
                            │    [Llama 3.3 70B Inst.]    │                        │
                            └──────────────┬──────────────┘                        │
                                           ▼                                       │
                            ┌─────────────────────────────┐                        │
                            │    6. Strategy Validator    ├────────────────────────┘
                            │    [DeepSeek-R1 Distill 70B]│
                            └──────────────┬──────────────┘
                                           │ (Approval Certificate)
                                           ▼
                            ┌─────────────────────────────┐
                            │   Validated Growth Plan     │
                            └─────────────────────────────┘

```

### Deliverable 1: Project Hierarchy and Component Architecture

#### 1. Internal VNC Subsystem Integration

The display automation components (`xvfb`, `x11vnc`, `novnc`, `mutter`, `tint2`) and tool definitions (`computer.py`, `bash.py`, `edit.py`) are encapsulated strictly as an internal, private subsystem. They are not exposed to the public network or exposed as general-purpose external endpoints. Authorized agents access these facilities through an internal Unix domain socket or an isolated Docker bridge network (`antigravity-internal-net`) via high-level Python tool bindings.

```
brand-strategy-engine/
├── .config/
│   ├── config.toml                     # Global runtime, Ollama model routing, Antigravity policies
│   └── settings.json                   # IDE and runtime workspace settings
├── docker/
│   ├── Dockerfile.engine               # Core Antigravity SDK & Agent runtime
│   ├── Dockerfile.vnc_sandbox          # Internalized headless VNC browser container
│   └── docker-compose.yml              # Multi-container isolated bridge topology
├── internal_sandbox/                   # PRIVATE: Sandboxed VNC Display Subsystem
│   ├── config/
│   │   └── tint2/
│   │       ├── applications/           # Firefox, terminal, desktop configurations
│   │       └── tint2rc
│   ├── entrypoint.sh                   # Display initialization supervisor
│   ├── scripts/
│   │   ├── mutter_startup.sh           # Window manager startup
│   │   ├── novnc_startup.sh            # Private localhost-only WebSocket bridge
│   │   ├── start_all.sh                # Main container initialization
│   │   ├── tint2_startup.sh            # Taskbar startup
│   │   ├── x11vnc_startup.sh           # Internal X11 server exporter
│   │   └── xvfb_startup.sh             # Virtual framebuffer initialization (:1, 1920x1080)
│   └── tools/                          # Internal computer use tool implementations
│       ├── base.py                     # Base tool abstractions
│       ├── bash.py                     # Sandboxed local command execution
│       ├── computer.py                 # Mouse, keyboard, screen coordinate controllers
│       ├── edit.py                     # File buffer modifications
│       └── vnc_client.py               # Headless Python RFB/VNC screenshot & event stream
├── src/
│   ├── __init__.py
│   ├── orchestrator/                   # Central supervisor and lifecycle management
│   │   ├── __init__.py
│   │   ├── manager.py                  # Antigravity Manager agent implementation
│   │   ├── state_machine.py            # Transition rules, stage gating, revision cycles
│   │   └── context_isolator.py         # Dynamic state-slicing and token budgeting
│   ├── agents/                         # Domain specialist agent implementations
│   │   ├── __init__.py
│   │   ├── base_agent.py               # Abstract agent base with ReAct engine
│   │   ├── analyst_agent.py            # Agent 1: VNC DOM, UX, competitor inspector
│   │   ├── audience_agent.py           # Agent 2: ICP designer and intent diagnostic
│   │   ├── brand_agent.py              # Agent 3: Differentiation matrix & narrative auditor
│   │   ├── seo_content_agent.py        # Agent 4: Semantic search & content gap planner
│   │   ├── growth_agent.py             # Agent 5: ICE synthesis & growth opportunity planner
│   │   └── validator_agent.py          # Agent 6: Adversarial verification and veto gate
│   ├── tools/                          # Public Antigravity agent tool interfaces
│   │   ├── __init__.py
│   │   ├── browser_bridge.py           # Agent 1 wrapper around internal_sandbox/tools/
│   │   ├── dom_parser.py               # Semantic accessibility tree & DOM extractor
│   │   ├── rag_search.py               # Vector retrieval tool for Agents 1-5
│   │   └── metric_validator.py         # Ground truth KPI feasibility evaluator
│   ├── memory/                         # Dual-tier memory architecture
│   │   ├── __init__.py
│   │   ├── short_term.py               # Redis/In-memory task scratchpad & ReAct buffer
│   │   ├── long_term.py                # PostgreSQL / pgvector cross-session persistence
│   │   └── summarizer.py               # Recursive hierarchical state compressor
│   ├── rag/                            # Local document ingestion and grounding
│   │   ├── __init__.py
│   │   ├── parser.py                   # Multi-format extractors (PDF, DOCX, CSV)
│   │   ├── chunker.py                  # Semantic sliding-window chunking
│   │   ├── embedder.py                 # Ollama nomic-embed-text embedding client
│   │   └── store.py                    # pgvector storage and metadata filter engine
│   ├── schemas/                        # Pydantic v2 master contracts
│   │   ├── __init__.py
│   │   ├── state.py                    # MasterEngineState and component states
│   │   ├── initiative.py               # Standard Strategic Initiative schema
│   │   ├── evidence.py                 # Evidence reference and provenance models
│   │   └── validation.py               # Audit logs and revision payloads
│   └── runtime/                        # Application entrypoints
│       ├── __init__.py
│       ├── cli.py                      # Terminal execution interface
│       └── api.py                      # Local REST API for strategy triggers
├── tests/
│   ├── test_agents.py
│   ├── test_rag_pipeline.py
│   ├── test_state_machine.py
│   └── test_vnc_bridge.py
├── pyproject.toml
└── README.md

```

#### 2. Dependency and Configuration Mapping

##### `docker/docker-compose.yml`

```yaml
version: '3.8'

networks:
  antigravity-internal-net:
    driver: bridge
    internal: true
  host-bridge:
    driver: bridge

services:
  ollama-node:
    image: ollama/ollama:latest
    container_name: engine-ollama
    restart: unless-stopped
    volumes:
      - ./ollama_models:/root/.ollama
    environment:
      - OLLAMA_KEEP_ALIVE=24h
      - OLLAMA_NUM_PARALLEL=4
    networks:
      - antigravity-internal-net
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  vnc-browser-sandbox:
    build:
      context: .
      dockerfile: docker/Dockerfile.vnc_sandbox
    container_name: engine-vnc-sandbox
    restart: unless-stopped
    ipc: host
    environment:
      - DISPLAY=:1
      - RESOLUTION=1920x1080x24
      - NOVNC_PORT=6080
      - VNC_PORT=5901
    networks:
      - antigravity-internal-net
    security_opt:
      - seccomp:unconfined

  postgres-pgvector:
    image: pgvector/pgvector:pg16
    container_name: engine-postgres
    restart: unless-stopped
    environment:
      - POSTGRES_DB=brand_strategy_db
      - POSTGRES_USER=engine_user
      - POSTGRES_PASSWORD=engine_secure_pass
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - antigravity-internal-net

  antigravity-engine:
    build:
      context: .
      dockerfile: docker/Dockerfile.engine
    container_name: engine-core
    restart: on-failure
    depends_on:
      - ollama-node
      - vnc-browser-sandbox
      - postgres-pgvector
    environment:
      - OLLAMA_BASE_URL=http://ollama-node:11434/v1
      - VNC_HOST=vnc-browser-sandbox
      - VNC_PORT=5901
      - DATABASE_URL=postgresql://engine_user:engine_secure_pass@postgres-pgvector:5432/brand_strategy_db
      - CONFIG_PATH=/app/.config/config.toml
    volumes:
      - ./evidence_blobs:/app/evidence_blobs
      - ./user_documents:/app/user_documents
    networks:
      - antigravity-internal-net
      - host-bridge
    ports:
      - "127.0.0.1:8000:8000"

volumes:
  pgdata:

```

##### `.config/config.toml`

```toml
[engine]
version = "2.4.0"
environment = "production-local"
default_mode = "Mode_A_Personal"
max_validator_revision_cycles = 3
zero_hallucination_enforcement = true
evidence_storage_path = "/app/evidence_blobs"

[runtime.ollama]
base_url = "http://ollama-node:11434/v1"
request_timeout_seconds = 180.0
embedding_model = "nomic-embed-text:latest"

[models.orchestrator]
name = "qwen2.5:72b-instruct-q4_K_M"
temperature = 0.1
context_window = 32768

[models.analyst]
name = "llama3.2-vision:11b-instruct-q4_K_M"
temperature = 0.0
context_window = 16384

[models.specialist]
name = "qwen2.5:32b-instruct-q4_K_M"
temperature = 0.2
context_window = 16384

[models.growth]
name = "llama3.3:70b-instruct-q4_K_M"
temperature = 0.2
context_window = 32768

[models.validator]
name = "deepseek-r1:70b"
temperature = 0.0
context_window = 32768

[sandbox.vnc]
host = "vnc-browser-sandbox"
port = 5901
display = ":1"
viewport_width = 1920
viewport_height = 1080
color_depth = 24
headless = true
screenshot_timeout_ms = 5000

[storage.postgres]
host = "postgres-pgvector"
port = 5432
database = "brand_strategy_db"
pool_size = 10
vector_dimensions = 768

```

---

### Deliverable 2: Agent Ecosystem, Tool Access Control, and ReAct Protocols

#### 1. Master RBAC and Permission Matrix

| Agent ID & Name | Model Profile (Ollama) | Execution Focus | Tool Whitelist | Sandbox Permissions | Network Bridge |
| --- | --- | --- | --- | --- | --- |
| **Agent 0: Orchestrator** | `qwen2.5:72b` (q4_K_M) | Central routing, context isolation, revision loops | `delegate_task`, `merge_agent_payload`, `route_revisions`, `compile_strategy_dossier` | No direct access | Internal loopback only |
| **Agent 1: Platform Analyst** | `llama3.2-vision:11b` (q4_K_M) | Visual DOM inspection, UX flow, competitor scanning | `vnc_navigate`, `vnc_interact`, `capture_visual_evidence`, `extract_dom_tree`, `rag_query` | Read-Write (Mouse, Keyboard, Display) | Internal VNC sandbox only |
| **Agent 2: Audience Strategist** | `qwen2.5:32b` (q4_K_M) | ICP modeling, journey mapping, intent diagnosis | `query_market_demographics`, `map_customer_journey`, `calculate_friction`, `rag_query` | None | Denied |
| **Agent 3: Brand Strategist** | `qwen2.5:32b` (q4_K_M) | Value proposition, narrative positioning, differentiation | `extract_brand_voice`, `benchmark_differentiation`, `evaluate_uvp`, `rag_query` | None | Denied |
| **Agent 4: SEO Strategist** | `qwen2.5:32b` (q4_K_M) | Semantic keywords, architecture, content gaps | `analyze_onpage_elements`, `cluster_serp_intent`, `scan_content_gaps`, `rag_query` | Read-only (DOM snapshots) | Denied |
| **Agent 5: Growth Strategist** | `llama3.3:70b` (q4_K_M) | ICE scoring, initiative synthesis, KPI setting | `calculate_ice_score`, `model_growth_projection`, `build_recommendation`, `rag_query` | None | Denied |
| **Agent 6: Strategy Validator** | `deepseek-r1:70b` (q4_K_M) | Adversarial audit, provenance verification, veto | `verify_evidence_provenance`, `audit_logical_consistency`, `validate_metric_feasibility`, `issue_veto` | Read-only (Raw evidence blob) | Denied |

#### 2. Detailed Agent Specifications and ReAct Loops

##### Agent 0: Brand Strategy Orchestrator (Manager Agent)

* **Runtime Profile**: High-capacity reasoning model managing pipeline state machines, enforcing schema boundaries, and directing revision cycles.
* **System Prompt**:

```text
You are the Brand Strategy Orchestrator, the central supervisory engine for the Universal AI Brand Strategy Engine.
Responsibilities:
1. State Management: Maintain the MasterEngineState and coordinate specialist agents in strict sequence: Analyst -> Audience -> Brand -> SEO/Content -> Growth -> Validator.
2. Context Isolation: Provide each downstream specialist ONLY with its required slice of state to prevent context dilution.
3. Revision Control: When Agent 6 (Strategy Validator) issues a veto, extract the failed initiatives and audit logs, increment the iteration counter, and route the items back to the initiating agent.
4. Hard Revision Ceiling: If an initiative fails verification 3 times, purge it permanently from the final strategic dossier.
5. Non-Interference: Never invent findings or strategy recommendations directly.

```

* **ReAct Execution Protocol**:
* **Reason**: Inspect current workflow stage in `MasterEngineState`. Determine whether preceding agent outputs satisfy graduation gates and prepare the minimal state slice for the next agent.
* **Act**: Execute `delegate_task(agent_name, target_slice)`.
* **Observe**: Ingest the returned Pydantic payload, verifying field constraints and error flags.
* **Reflect**: Check for validation errors. If revisions are requested and iteration counter $< 3$, trigger `route_revisions()`; otherwise, advance pipeline or compile final dossier.



##### Agent 1: Website and Social Platform Analyst

* **Runtime Profile**: Multimodal visual model with access to the private VNC container to collect DOM structures, screenshots, and competitor metrics.
* **System Prompt**:

```text
You are the Website and Social Platform Analyst. You operate an internal, sandboxed VNC desktop browser to conduct empirical visual and DOM audits of target brand properties and direct competitors.
Mandates:
1. Zero Speculation: Every finding must reference an empirical evidence_id pointing to a captured DOM selector or high-resolution VNC screenshot.
2. Mode A (Personal): Inspect hero positioning, proof of work, case study structure, technical stack badges, CV downloads, GitHub/LinkedIn links, and booking widget friction.
3. Mode B (eCommerce): Inspect navigation taxonomy, cart/checkout drop-offs, PDP layout, reviews, sizing guides, return policies, and trust signals.
4. Evidence Capture: When a friction point or structural deficiency is observed, call capture_visual_evidence immediately before continuing navigation.

```

* **ReAct Execution Protocol**:
* **Reason**: Identify navigation targets from input URL. Select target viewport (Desktop: 1920x1080, Mobile: 390x844).
* **Act**: Call `vnc_navigate(url)` $\rightarrow$ `extract_dom_tree(selector)` $\rightarrow$ `capture_visual_evidence(bounding_box)`.
* **Observe**: Analyze element responsiveness, layout shifts, DOM node visibility, and page render timings.
* **Reflect**: Correlate observed visual artifacts with competitor benchmarks; register unique evidence IDs in the research repository.



##### Agent 2: Audience Strategist

* **Runtime Profile**: Customer-intent diagnostic specialist synthesizing observed digital touchpoints and user documents into concrete Ideal Customer Profiles (ICPs) and friction models.
* **System Prompt**:

```text
You are the Audience Strategist. You translate empirical website observations and uploaded client documentation into grounded audience models, buyer personas, and friction assessments.
Mandates:
1. Grounded Personas: You are strictly forbidden from inventing generic personas. Every ICP trait must be anchored in observed brand features, product price points, or explicit RAG documentation.
2. Intent Mapping: Classify visitor intent (Informational, High-Consideration B2B, Impulse eCommerce) and determine exact drop-off triggers.
3. Friction Diagnostics: Quantify user journey friction across key conversion pathways (contact form, checkout, discovery).

```

* **ReAct Execution Protocol**:
* **Reason**: Parse visual evidence and DOM hierarchies from Agent 1. Formulate RAG search queries to inspect user-provided customer profiles.
* **Act**: Call `rag_query("customer demographics enterprise personas")` and `map_customer_journey(touchpoint_list)`.
* **Observe**: Evaluate alignment between observed copy and intended visitor sophistication.
* **Reflect**: Formulate quantified friction scores across key user pathways and commit ICP models to the state repository.



##### Agent 3: Brand Strategist

* **Runtime Profile**: Differentiation matrix architect evaluating messaging hierarchies, unique value propositions (UVPs), and competitive positioning.
* **System Prompt**:

```text
You are the Brand Strategist. You evaluate the target brand's narrative positioning, visual authority, UVP differentiation, and perceived market value relative to competitors.
Mandates:
1. Competitive Reality Standard: If a target property claims a "unique" value proposition that matches copy observed on competitor websites, flag it as commoditized.
2. Mode A: Establish the "Category of One". Audit clichéd phrasing ("passionate developer", "innovative problem solver") and enforce authoritative proof of competence.
3. Mode B: Evaluate perceived quality vs. price tier, trust architecture, brand storytelling, and emotional resonance.

```

* **ReAct Execution Protocol**:
* **Reason**: Compare hero copy, value propositions, and proof points against indexed competitor messaging vectors.
* **Act**: Call `extract_brand_voice(corpus)` and `benchmark_differentiation(target_features, competitor_features)`.
* **Observe**: Identify commoditized phrasing and messaging voids across digital touchpoints.
* **Reflect**: Establish the messaging hierarchy and synthesize the Category of One differentiation matrix.



##### Agent 4: SEO and Content Strategist

* **Runtime Profile**: Information retrieval auditor diagnosing semantic search visibility, schema markup validity, and content depth.
* **System Prompt**:

```text
You are the SEO and Content Strategist. You audit search engine discoverability, information architecture, technical on-page health, and commercial intent coverage.
Mandates:
1. Technical Grounding: Every technical flaw (missing canonicals, broken schema, improper heading hierarchy) must cite the exact DOM snapshot node.
2. Semantic Content Mapping: Identify high-intent content gaps based on verified competitor coverage and audience search intent.
3. CMS Feasibility: Constrain recommendations to standard CMS capabilities (WordPress, Shopify, Webflow, Next.js) unless custom architecture is verified.

```

* **ReAct Execution Protocol**:
* **Reason**: Inspect DOM metadata, OpenGraph tags, JSON-LD blocks, and heading structures from the research repository.
* **Act**: Call `analyze_onpage_elements(dom_snapshot)` and `scan_content_gaps(target_keywords, competitor_keywords)`.
* **Observe**: Flag technical rendering issues, unindexed case studies, and missing product rich snippets.
* **Reflect**: Formulate technical SEO fixes and design a commercial-intent content blueprint.



##### Agent 5: Growth Strategist

* **Runtime Profile**: Strategic synthesis and prioritization engine converting upstream diagnostic findings into high-impact initiatives.
* **System Prompt**:

```text
You are the Growth Strategist. You synthesize the diagnostic outputs of Agents 1 through 4 into high-leverage strategic initiatives conforming strictly to the Standard Strategic Initiative Contract.
Mandates:
1. Unbroken Evidence Chains: Every initiative must explicitly incorporate an upstream evidence_id, source URL, and DOM selector or screenshot reference.
2. Prioritization Rigor: Calculate ICE (Impact, Confidence, Effort) and Cost scores using empirical difficulty standards.
3. Verifiable Metrics: Define quantitative KPIs with explicit current baselines and achievable target thresholds verifiable via standard analytics platforms.

```

* **ReAct Execution Protocol**:
* **Reason**: Correlate technical SEO gaps, audience friction points, and brand differentiation voids to find highest-leverage remediation targets.
* **Act**: Call `calculate_ice_score(impact, confidence, ease)` and `build_recommendation(...)`.
* **Observe**: Validate that every synthesized initiative adheres strictly to the Pydantic initiative schema.
* **Reflect**: Rank recommendations into an execution roadmap categorized by Quick Wins, Core Priorities, and Architectural Bets.



##### Agent 6: Strategy Validator

* **Runtime Profile**: Zero-temperature adversarial auditor exercising strict veto power over unsupported assertions or unrealistic metrics.
* **System Prompt**:

```text
You are the Strategy Validator. You operate as an adversarial auditor with unilateral veto power over every proposed strategic initiative.
Mandates:
1. Provenance Audit: Query the raw research repository. If an initiative's evidence_id does not resolve to an empirical DOM snapshot, VNC visual capture, or indexed RAG citation, VETO IMMEDIATELY.
2. Logical Coherence: Verify that the actionable prescription directly resolves the observed business implication.
3. Metric Realism: Reject ungrounded claims (e.g., "increase CVR by 400% in 14 days"). Enforce statistically realistic target thresholds.
4. Corrective Feedback: For every rejected initiative, generate a detailed diagnostic log specifying the exact failure point and routing instructions for the Orchestrator.

```

* **ReAct Execution Protocol**:
* **Reason**: Audit each initiative against the raw evidence database, business goals, and feasibility rules.
* **Act**: Call `verify_evidence_provenance(evidence_id)` $\rightarrow$ `audit_logical_consistency(initiative)` $\rightarrow$ `validate_metric_feasibility(metric)`.
* **Observe**: Log pass/fail flags across all verification gates.
* **Reflect**: If all checks pass, issue an approval certificate; if any check fails, trigger `issue_veto(rec_id, failure_reasons)` to initiate corrective routing.



---

### Deliverable 3: Dual-Tier Memory and Context Management Engine

```
                             ┌────────────────────────────────────────────────────────┐
                             │               Master Execution State                   │
                             └───────────────────────────┬────────────────────────────┘
                                                         │
                     ┌───────────────────────────────────┴──────────────────────────────────┐
                     ▼                                                                      ▼
    ┌─────────────────────────────────┐                                    ┌──────────────────────────────────┐
    │    Short-Term Working Memory    │                                    │     Long-Term Persistent Memory  │
    │  (Redis / Ephemeral Scratchpad) │                                    │      (PostgreSQL + pgvector)     │
    ├─────────────────────────────────┤                                    ├──────────────────────────────────┤
    │ • Active ReAct Step Buffer      │                                    │ • Client Brand Profiles & Goals  │
    │ • Raw DOM Accessibility Trees   │ ── Hierarchical State Compressor ──► • Verified Competitor Footprints │
    │ • Raw VNC Frame Buffers         │                                    │ • Historical Baseline Metrics    │
    │ • Cross-Agent Bounded Slices    │                                    │ • Longitudinal Audit Trails      │
    └─────────────────────────────────┘                                    └──────────────────────────────────┘

```

#### 1. Context Window Optimization

* **Token Budget Allocation per Agent Stage**:
* System Prompt & Tool Schemas: 2,500 tokens (fixed reserve).
* Stage-Specific Input Slice: 6,000 tokens (bounded context view).
* Active Scratchpad & Tool Observations: 5,500 tokens (rolling window).
* Generation Headroom: 2,384 tokens (guaranteed output buffer).


* **Context Isolation Pattern**: Downstream specialists receive bounded context slices rather than monolithic prompt histories. For example, Agent 3 (Brand Strategist) receives only the Analyst's visual summary, hero copy snippets, and competitor messaging, omitting raw DOM trees, terminal logs, and technical SEO markups.
* **Hierarchical State Compression**: When active scratchpad observations exceed 5,000 tokens, the Orchestrator executes a recursive summarizer:
* Raw HTML/DOM trees are pruned to semantic accessibility outlines.
* Intermediate ReAct traces are converted into structured observation records (`{step, action, observation_digest}`).
* High-resolution visual screenshots are offloaded to local storage (`/app/evidence_blobs`) and referenced in prompt buffers via lightweight URI hashes.



#### 2. Short-Term Memory (Task & Session Graph)

* Manages the intra-agent execution graph, transient browser frames, unparsed visual buffers, and active scratchpads.
* Implemented in-memory with Redis replication to facilitate fast state transfers between agent containers.
* Enforces typed Pydantic serialization across all agent handoffs, ensuring no raw, unvalidated strings are transferred between pipeline stages.

#### 3. Long-Term Memory (Cross-Session Knowledge Base)

* Implemented on PostgreSQL 16 with [pgvector](https://github.com/pgvector/pgvector) for persistent historical storage.
* **Client Isolation Boundaries**: Uses PostgreSQL Row-Level Security (RLS) linked to `tenant_id` and `client_id` foreign keys, preventing cross-client data contamination.
* **Historical Baseline Tracking**: Maintains longitudinal records of client digital properties, tracking metric changes across successive audit sessions to evaluate initiative efficacy over time.

---

### Deliverable 4: User Document Ingestion and Evidence Assurance Subsystem

#### 1. Ingestion and Indexing Pipeline

The engine includes a localized RAG pipeline for processing proprietary client materials (pitch decks, brand guidelines, private analytics, internal roadmaps) without external network exposure:

1. **Multi-Format Extraction**:
* PDF files: Structured text, table, and layout extraction via `pypdf` and `pdfplumber`.
* DOCX files: Hierarchical heading and body extraction via `python-docx`.
* CSV/XLSX: Numerical and tabular parsing via `pandas`.


2. **Semantic Chunking**: Employs an overlapping sliding-window chunker (512 tokens with 64-token overlap) that preserves section headings, markdown tables, and list structures.
3. **Local Vector Storage**: Generates 768-dimensional dense vector embeddings using local Ollama instances running `nomic-embed-text:latest` or `bge-m3`. Embeddings are stored in PostgreSQL using `pgvector` HNSW indexes for sub-10ms retrieval.

#### 2. Provenance Tracking & Grounding Contract

Every indexed chunk is tagged with an immutable cryptographic provenance header:

```json
{
  "chunk_id": "chk_8a12f9b4",
  "document_id": "doc_pitch_deck_2026",
  "source_filename": "Q3_Brand_Pitch_Deck.pdf",
  "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "page_number": 12,
  "section_heading": "Unit Economics & Customer Acquisition Cost",
  "timestamp": "2026-10-13T21:50:00Z",
  "byte_range": [12400, 13420],
  "content": "Observed blended CAC across paid channels increased by 38% in Q2 due to generic landing page positioning..."
}

```

#### 3. Agent-Level Evidence Assurance vs. Strategy Validator Separation

```
┌────────────────────────────────────────────────────────────────────────┐
│             Agent-Level Evidence Assurance (Internal Self-Audit)        │
│                         (Agents 1–5 Drafting Phase)                    │
├────────────────────────────────────────────────────────────────────────┤
│ • Proactive RAG search to verify factual claims before proposing steps │
│ • Gap Detection: If no document or DOM proof exists, log a Context Gap │
│ • Contradiction Check: Resolve conflicts between pitch decks and live  │
│   website implementation                                               │
│ • Hard Rule: Record information limitations rather than hallucinating  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Generates Grounded Initiatives)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             Strategy Validator (External Adversarial Inspection)       │
│                            (Agent 6 Veto Gate)                         │
├────────────────────────────────────────────────────────────────────────┤
│ • Zero trust towards agent assertions                                  │
│ • Deterministic Provenance Lookup: Confirms evidence_id exists in raw  │
│   evidence tables                                                      │
│ • Metric Sanity Validation: Rejects unfeasible ROI or CVR lift claims  │
│ • Veto Power: Drops ungrounded claims or triggers Orchestrator rewrite │
└────────────────────────────────────────────────────────────────────────┘

```

---

### Deliverable 5: Unified State Schema, Execution Flow, and Governance

#### 1. Master Engine State Schema (Pydantic v2 Implementation)

```python
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, HttpUrl

class OperationalMode(str, Enum):
    MODE_A_PERSONAL = "Mode_A_Personal"
    MODE_B_ECOMMERCE = "Mode_B_eCommerce"

class PriorityLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class ApprovalStatus(str, Enum):
    PROPOSED = "Proposed"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    REVISION_REQUESTED = "Revision_Requested"

class EvidenceReference(BaseModel):
    evidence_id: str = Field(description="Unique deterministic ID of observed evidence")
    source_url: HttpUrl = Field(description="URL where evidence was captured")
    source_type: str = Field(description="dom_selector | vnc_screenshot | rag_chunk | serp_result")
    dataset_reference: str = Field(description="Selector path, pixel bounding box, or chunk ID")
    observation_notes: str = Field(description="Raw visual or structural notes recorded at capture")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PriorityMatrix(BaseModel):
    impact: PriorityLevel
    effort: PriorityLevel
    cost: PriorityLevel
    confidence: str = Field(description="Percentage confidence rating, e.g., '92%'")
    ice_score: float = Field(ge=0.0, le=10.0, description="Calculated ICE score")

class SuccessMetric(BaseModel):
    kpi: str = Field(description="Target quantitative business metric")
    baseline: str = Field(description="Current observed baseline level")
    target: str = Field(description="Realistic target threshold")
    verification_source: str = Field(description="Analytics platform to verify outcome")

class StrategicInitiative(BaseModel):
    recommendation_id: str = Field(description="Format: REC-A-XXX or REC-B-XXX")
    initiating_agent: str = Field(description="Agent ID that created the initiative")
    finding: str = Field(description="Observed empirical defect or opportunity")
    evidence: EvidenceReference
    business_implication: str = Field(description="Quantified risk or unrealized opportunity")
    actionable_prescription: str = Field(description="Step-by-step remediation plan")
    priority: PriorityMatrix
    success_metric: SuccessMetric
    approval_status: ApprovalStatus = Field(default=ApprovalStatus.PROPOSED)
    rejection_reasons: Optional[List[str]] = Field(default=None)
    iteration_cycle: int = Field(default=0, ge=0, le=3)

class BrandProfile(BaseModel):
    website_url: HttpUrl
    brand_name: str
    industry: str
    target_market: List[str]
    business_goals: List[str]

class ResearchRepository(BaseModel):
    dom_snapshots: Dict[str, Any] = Field(default_factory=dict)
    visual_evidence_vnc: List[EvidenceReference] = Field(default_factory=list)
    competitor_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    rag_citations: List[Dict[str, Any]] = Field(default_factory=list)
    context_gaps: List[str] = Field(default_factory=list)

class StrategicArtifacts(BaseModel):
    audience_analysis: Dict[str, Any] = Field(default_factory=dict)
    brand_positioning: Dict[str, Any] = Field(default_factory=dict)
    seo_and_content_plan: Dict[str, Any] = Field(default_factory=dict)
    growth_initiatives: List[StrategicInitiative] = Field(default_factory=list)

class ValidationReport(BaseModel):
    status: str = Field(default="Pending")
    total_audited: int = Field(default=0)
    passed_count: int = Field(default=0)
    failed_count: int = Field(default=0)
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)

class MasterEngineState(BaseModel):
    session_id: str
    mode: OperationalMode
    created_at: datetime = Field(default_factory=datetime.utcnow)
    brand_profile: BrandProfile
    research_repository: ResearchRepository = Field(default_factory=ResearchRepository)
    strategic_artifacts: StrategicArtifacts = Field(default_factory=StrategicArtifacts)
    validation_report: ValidationReport = Field(default_factory=ValidationReport)
    current_stage: str = Field(default="Initialization")
    iteration_counter: int = Field(default=0, le=3)

```

#### 2. Execution Workflow and Adversarial Review Governance

```
Stage 0: Engine Initialization & Ingestion
  ├── Parse user-provided brand profile, target URL, and operational mode
  └── Ingest user documents into local pgvector via Ollama embeddings
Stage 1: Empirical VNC Reconnaissance (Agent 1)
  ├── Headless VNC browser navigates target URL and competitor properties
  ├── Capture DOM accessibility trees and high-res visual evidence frames
  └── Index artifacts into research_repository with deterministic evidence_ids
Stage 2: Audience & Friction Modeling (Agent 2)
  ├── Extract ICP profiles grounded in observed products and pricing
  └── Calculate conversion drop-off points and journey friction scores
Stage 3: Brand & Narrative Positioning (Agent 3)
  ├── Benchmark target messaging against competitor positioning vectors
  └── Construct "Category of One" differentiation matrix
Stage 4: SEO & Content Gap Auditing (Agent 4)
  ├── Audit semantic structure, schema.org markups, and heading hierarchy
  └── Map commercial-intent search voids and technical crawl deficiencies
Stage 5: Strategic Synthesis & ICE Scoring (Agent 5)
  ├── Correlate upstream findings into standard Strategic Initiatives
  └── Assign ICE prioritization, resource costs, and verifiable KPI metrics
Stage 6: Adversarial Audit & Validation Loop (Agent 6)
  ├── Check 1: Provenance Verification (evidence_id exists in repository)
  ├── Check 2: Logical Alignment (prescription resolves the implication)
  ├── Check 3: Metric Feasibility (KPI targets are empirically realistic)
  │
  ├── [VERDICT: ALL PASS] ──────► Compile & Export Final Strategy Dossier
  └── [VERDICT: REJECTION]
        ├── Iteration Counter < 3 ──► Route back to Initiating Agent with Audit Log
        └── Iteration Counter >= 3 ─► Permanently drop unverified initiative

```

* **Zero-Hallucination Policy**: If an initiative fails to resolve its `evidence_id` to a recorded VNC screenshot bounding box, DOM selector node, or verified RAG text chunk, it is flagged as an ungrounded hallucination and rejected immediately.
* **Loop Termination & Deadlock Prevention**: The review loop enforces a hard ceiling of 3 iteration cycles. If an agent fails to provide empirical grounding or realistic metrics after three revisions, the initiative is dropped from the final dossier, and the reason for exclusion is recorded in the final audit ledger.

---

### Verification and Local Execution Runbook

You can deploy and verify the engine using the containerized runtime:

1. Pull the required models into your local Ollama instance:
```bash
ollama pull qwen2.5:72b-instruct-q4_K_M
ollama pull qwen2.5:32b-instruct-q4_K_M
ollama pull llama3.3:70b-instruct-q4_K_M
ollama pull llama3.2-vision:11b-instruct-q4_K_M
ollama pull deepseek-r1:70b
ollama pull nomic-embed-text:latest

```


2. Build and launch the container cluster:
```bash
docker compose -f docker/docker-compose.yml up -d --build

```


3. Trigger an autonomous audit run via the CLI interface:
```bash
docker exec -it engine-core python -m src.runtime.cli \
  --mode Mode_A_Personal \
  --url "https://portfolio-target.dev" \
  --docs-dir "/app/user_documents"

```



This architecture provides complete containment of the VNC automation tools, strict model access boundaries, dual-tier memory management, and adversarial validation loops to deliver audit-ready brand strategies.