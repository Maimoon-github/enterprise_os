# Production-Grade Multi-Agent System Architecture & Implementation Specification: Self-Hosted Agentic Brand Marketing Platform

## 1. Architectural Synthesis & Critical Refinements Over Baseline Context

A critical synthesis of official reference implementations—spanning [LangGraph StateGraph & Supervisor Architectures](https://github.com/langchain-ai/langgraph-supervisor-py), the [Model Context Protocol (MCP) 2026-07-28 Specification](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture), the [Agent Skills Specification](https://agentskills.io/specification), [Pydantic AI v2 Toolsets](https://airflow.apache.org/docs/apache-airflow-providers-common-ai/0.5.0/toolsets/index.html), [Anthropic's Building Effective Agents Blueprint](https://www.anthropic.com/research/building-effective-agents), and [OpenInference Semantic Conventions](https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md)—identifies seven high-impact architectural refinements required to elevate the baseline `Agentic Brand Marketing.md` requirements and `resorces.txt` reference notes into a deterministic, production-grade specification:

| Architectural Dimension | Baseline Context (`Agentic Brand Marketing.md` & `resorces.txt`) | Verified Production Refinement & Protocol Alignment | Primary Technical Source |
| :--- | :--- | :--- | :--- |
| **Orchestration vs. Workflow Boundary** | Applies general ReAct loops broadly across orchestrator and worker tasks. | Explicitly separates deterministic **Workflows** (Prompt Chaining, Routing, Parallel Sectioning, Orchestrator-Workers, Evaluator-Optimizer) from open-ended **Autonomous Agents**, reserving multi-turn ReAct loops strictly for unpredictable exploration while compiling predictable multi-platform pipelines via **ReWOO** variable substitution (`#E1`, `#E2`) or **Plan-and-Solve**. | [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) & [ControlScope / ReWOO (arXiv:2609.34313v1)](https://arxiv.org/html/2609.34313v1) |
| **LangGraph State, Checkpointing & Interrupt Idempotency** | Uses `StateGraph`, `Send`, `Command`, and `PostgresSaver` without addressing node replay semantics on `interrupt()`. | Enforces strict pre-interrupt idempotency because [LangGraph Checkpointers](https://futureagi.com/blog/what-is-langgraph-2026/) snapshot state at **super-step boundaries** rather than mid-node; when `Command(resume=...)` resumes an `interrupt()`, the entire node re-executes from its first line. Side effects must be isolated into dedicated post-approval nodes or guarded via deterministic idempotency keys. | [LangGraph 2026 Stateful Graph Guide](https://futureagi.com/blog/what-is-langgraph-2026/) & [Durable HITL Workflows](https://nirajiitr.com/blog/durable-hitl-ai-workflows-langgraph-postgresql-nextjs) |
| **Supervisor Tool-Calling vs. Custom Handoffs** | Centralizes all multi-agent routing through a single Master Orchestrator bottleneck. | Implements a **Hybrid Hierarchical Graph**: follows the [LangGraph Supervisor guidance](https://github.com/langchain-ai/langgraph-supervisor-py) by using explicit tool-calling subagents and custom handoff tools (`InjectedState`, `InjectedToolCallId`, `Command.PARENT`, and `create_forward_message_tool`) with `output_mode="last_message"` for context engineering, while enabling direct peer-to-peer subgraph handoffs (`Command(update=..., goto=...)`) inside domain teams. | [LangGraph Supervisor Python SDK](https://github.com/langchain-ai/langgraph-supervisor-py) & [Handoff vs. Supervisor Benchmarks](https://medium.com/@attia.atef92/handoff-vs-supervisor-why-your-multi-agent-architecture-choice-matters-%EF%B8%8F-40cadb0e0dc2) |
| **Model Context Protocol (MCP) 2026-07-28 Alignment** | References older stateful session assumptions and omits modern MCP discovery, caching, and deprecation rules. | Adopts the stateless `_meta` per-request envelope (`io.modelcontextprotocol/protocolVersion`, `clientInfo`, `clientCapabilities`), `server/discover` with `ttlMs`/`cacheScope`, `subscriptions/listen` for opt-in `toolsListChanged` notifications, the **Tasks extension** for durable long-running media jobs, and replaces deprecated MCP `sampling` and `logging` primitives with direct LLM provider SDK calls and OpenTelemetry spans. | [MCP 2026-07-28 Architecture Overview](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture) & [MCP Specification](https://modelcontextprotocol.io/specification/2026-07-28) |
| **Agent Skills Progressive Disclosure** | Mentions `SKILL.md` conceptually without enforcing token budgets or directory validation rules. | Enforces the [Agent Skills Specification](https://agentskills.io/specification) 3-tier progressive disclosure contract: Tier 1 Metadata (`name`, `description` ~100 tokens loaded at startup), Tier 2 Instructions (`SKILL.md` body <5,000 tokens and <500 lines loaded on activation), and Tier 3 Bundled Resources (`scripts/`, `references/`, `assets/` loaded strictly on demand, one level deep), validated via `skills-ref validate`. | [Agent Skills Specification](https://agentskills.io/specification) & [Anthropic Skills Repository](https://github.com/anthropics/skills) |
| **Pydantic AI v2 Worker API Contracts** | Uses `output_type` and `retries=3` uniformly across read and write tools. | Aligns with [Pydantic AI v2.43+ API contracts](https://blog.csdn.net/ygn12/article/details/165331769) (`output_type`, `result.usage` property, `TestModel` zero-token schema verification, `MCPServerStdio` / `MCPServerStreamableHTTP`) and differentiates retry budgets by side-effect class (`retries=3` for idempotent read/RAG tools; `retries=1` for mutating platform publishing tools to prevent duplicate posts on `UnexpectedModelBehavior`). | [Pydantic AI v2 Verification](https://blog.csdn.net/ygn12/article/details/165331769) & [Airflow Pydantic AI Toolsets](https://airflow.apache.org/docs/apache-airflow-providers-common-ai/0.5.0/toolsets/index.html) |
| **OpenInference Semantic Conventions & Span Hierarchy** | Uses ad-hoc span attributes (`agent.executed_tools`, `eval.trajectory_valid`). | Standardizes on canonical [OpenInference Semantic Conventions](https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md): eleven span kinds (`AGENT`, `CHAIN`, `LLM`, `TOOL`, `RETRIEVER`, `RERANKER`, `EMBEDDING`, `GUARDRAIL`, `EVALUATOR`, `PROMPT`, `DECISION`), graph topology attributes (`graph.node.id`, `graph.node.parent_id`, `agent.name`), flattened indexed arrays (`llm.output_messages.0.message.tool_calls.0.tool_call.function.name`), and trace-level evaluations (`trace.evaluations.0.evaluation.*`). | [OpenInference Semantic Conventions Spec](https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md) & [Arize Phoenix](https://github.com/arize-ai/phoenix) |

## 2. Core Reasoning, Planning, and Execution Loops

Production multi-agent systems do not rely on a single homogeneous reasoning loop. Instead, the orchestration layer selects the execution paradigm that matches the determinism, latency budget, and error-recovery profile of each marketing subsystem.

### 2.1 Comparative Taxonomy of Reasoning Paradigms

| Reasoning Paradigm | Canonical Literature / Blueprint | Control Loop Topology | Token & Latency Profile | Target Subsystem in Agentic Marketing OS |
| :--- | :--- | :--- | :--- | :--- |
| **ReAct (Reason + Act)** | Yao et al., [arXiv:2210.03629](https://community.sap.com/t5/technology-blog-posts-by-sap/tame-your-agents-10-design-patterns-for-reliable-agentic-ai/ba-p/14424874) | `Thought -> Action (Tool Call) -> Observation -> Thought` (bounded by `recursion_limit` and `max_iterations`). | High token cost ($O(N)$ full-prefix LLM calls per step); high adaptability. | Deep competitor reconnaissance, exploratory web research, and dynamic anomaly investigation where tool outputs determine the next query. |
| **Plan-and-Solve** | Wang et al., [arXiv:2305.04091](https://arxiv.org/html/2402.07456v2) | `Frontier Planner (Decompose & Variable-Bind) -> Step Executor -> Conditional Re-Planner`. | Medium token cost; decouples strategic planning (`ollama:llama3.3:70b` / `qwen2.5:72b`) from step execution (`ollama:qwen2.5:14b`). | Campaign blueprint synthesis (`campaign.json`), translating high-level brand objectives into multi-week, cross-channel execution plans. |
| **ReWOO (Reasoning Without Observation)** | Xu et al., [arXiv:2305.18323](https://www.zair.top/en/post/ai-agent-design-pattern/) | `Planner (Emits DAG with #E1, #E2 placeholders) -> Parallel Tool Worker Pool -> Solver (Single Synthesis Call)`. | Reduces token consumption by >50% and minimizes wall-clock latency by eliminating intermediate LLM calls between predictable tool invocations. | Cross-platform analytics ingestion, daily KPI rollups across 8 social channels, and deterministic RAG context assembly. |
| **Reflexion (Verbal Reinforcement Learning)** | Shinn et al., [arXiv:2303.11366](https://blog.muralikannan.com/designing-autonomous-ai-workers/) | `Actor -> Deterministic Schema & Policy Validator -> Self-Critique Episodic Buffer -> Actor Revision`. | High token cost when triggered; bounded to `max_revisions <= 2` to prevent oscillation. | Brand voice compliance auditing, platform media aspect-ratio/character-limit verification, and structured `campaign.json` schema repair. |
| **Evaluator-Optimizer & Sectioning Workflows** | Anthropic, [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) | Deterministic code-driven DAG with parallel fan-out (**Sectioning** / **Voting**) and isolated rubric evaluation loops. | Predictable, bounded cost; eliminates autonomous routing drift on routine pipelines. | Multi-platform copy adaptation (LinkedIn, X, Instagram, Threads, YouTube, Pinterest, Facebook, GBP) and automated pre-publish safety guardrails. |

### 2.2 Formal Control-Flow Equations & Loop Guardrails

To prevent runaway recursion on local Ollama inference servers, every reasoning loop must enforce three hard runtime invariants:

1. **Super-Step Recursion Ceiling:** Every LangGraph invocation must pass `config={"configurable": {"thread_id": thread_id}, "recursion_limit": 25}` ([LangGraph Stateful Graph Guide](https://futureagi.com/blog/what-is-langgraph-2026/)).
2. **ReWOO Variable Substitution DAG:** During analytics collection and multi-source enrichment, the Planner emits a topological execution plan $G = (V, E)$ where each node $v_i \in V$ binds a tool call $T_i(\text{args})$ to a symbolic variable `#E_i`. Independent nodes execute concurrently via `asyncio.gather`, and dependent nodes substitute resolved `#E_j` outputs directly into their argument payloads before invoking the Solver LLM once.
3. **Reflexion Episodic Critique Buffer:** When a worker output fails validation, the Evaluator node appends a structured `CritiqueRecord(step_id, violated_rule, exact_error, remediation_hint)` to a bounded state channel (`max_length=3`) rather than retaining raw failed drafts in the main message history, preventing context window pollution.

## 3. Interoperability Layer: Tools, Model Context Protocol (MCP), Agent Skills, and Plugins

A production multi-agent platform requires a strict separation of concerns between **atomic capabilities (Tools/Plugins)**, **standardized context & transport wiring (MCP)**, and **composable procedural expertise (Agent Skills)**.

### 3.1 Architectural Taxonomy: Tools vs. MCP vs. Agent Skills vs. Plugins

| Abstraction Layer | Granularity & Role | Control Owner | Specification / Contract | Lifecycle & Context Footprint |
| :--- | :--- | :--- | :--- | :--- |
| **Tool (Function Call)** | Atomic executable function (e.g., `publish_linkedin_post`, `query_qdrant_chunks`). | **Model-Controlled:** LLM decides when and how to invoke based on JSON Schema (`inputSchema`). | JSON Schema / Pydantic `BaseModel` bound to the model decoding layer or exposed via MCP `tools/list`. | Registered per turn; excessive tools (>20) degrade model selection accuracy unless filtered by active skill or sub-agent scope. |
| **MCP Resource** | Read-only contextual data source identified by URI (e.g., `config://brand/{id}/voice`, `postgres://campaigns/{id}/schema`). | **Application-Controlled:** Host or orchestrator fetches via `resources/read` and injects into context. | [MCP 2026-07-28 Resources Spec](https://modelcontextprotocol.io/specification/2026-07-28/server/resources) (`uri`, `mimeType`, `text`/`blob`). | Fetched deterministically on demand; cached according to server `ttlMs` and `cacheScope`. |
| **MCP Prompt** | Parameterized interaction template or workflow slash-command. | **User / Host-Controlled:** Selected explicitly by the user or orchestrator workflow trigger. | [MCP 2026-07-28 Prompts Spec](https://modelcontextprotocol.io/specification/2026-07-28) (`prompts/list`, `prompts/get`). | Instantiated at workflow initialization to seed standardized system instructions or few-shot examples. |
| **Agent Skill** | Domain-specific procedural package combining `SKILL.md` instructions, `scripts/`, `references/`, and `assets/`. | **Progressively Disclosed:** Agent sees metadata (~100 tokens) at startup and loads full `SKILL.md` (<5,000 tokens) upon task match. | [Agent Skills Specification (`agentskills.io`)](https://agentskills.io/specification) | Eliminates context bloat by keeping domain playbooks (e.g., `instagram-reels-strategy`, `competitor-seo-audit`) dormant until activated. |
| **Plugin / Toolset** | Deployment unit bundling related tools, authentication hooks, and transport adapters (e.g., `MCPToolset`, `SQLToolset`). | **Infrastructure-Controlled:** Configured by platform engineers at host startup. | [Pydantic AI `AbstractToolset`](https://airflow.apache.org/docs/apache-airflow-providers-common-ai/0.5.0/toolsets/index.html) / FastMCP Server package. | Governs connection pooling, credential injection, read/write allow-lists (`allow_writes=False`), and row/token budgets. |

### 3.2 Model Context Protocol (MCP) Production Architecture (2026-07-28 Spec)

In accordance with the [MCP 2026-07-28 Architecture Specification](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture), the platform operates as an **MCP Host** that instantiates dedicated **MCP Client** connectors for each isolated **MCP Server**:

1. **Data Layer & Stateless Per-Request `_meta` Envelope:**
   - Every JSON-RPC 2.0 request from an MCP Client must carry `"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientInfo": {"name": "marketing-os-worker", "version": "1.0.0"}, "io.modelcontextprotocol/clientCapabilities": {"elicitation": {}}}`.
   - Clients execute capability and version discovery via `server/discover`, honoring `ttlMs` and `cacheScope` hints in the response so capability metadata is cached across ephemeral worker spawns without redundant handshakes.
2. **Transport Layer Selection:**
   - **`stdio` Transport:** Used for local, single-client subprocess tools inside an isolated worker container (e.g., local filesystem asset inspection, FFmpeg media validation, or local SQLite scratchpads). Logs must write strictly to `stderr` or OpenTelemetry so `stdout` JSON-RPC framing is never corrupted.
   - **`Streamable HTTP` Transport:** Used for shared multi-client internal microservices (e.g., the Qdrant Brand RAG MCP Server, PostgreSQL Analytics MCP Server, and the Social Platform Gateway MCP Server). Uses HTTP `POST` for client-to-server requests with optional Server-Sent Events (SSE) streams and OAuth 2.1 / Bearer token headers.
3. **Dynamic Notification Subscriptions & Long-Running Tasks Extension:**
   - When platform API rate limits or feature flags dynamically disable a publishing tool, the MCP Server emits `notifications/tools/list_changed` over an opt-in `subscriptions/listen` stream (`"notifications": {"toolsListChanged": true}`).
   - For asynchronous operations (such as AI video generation or YouTube HD processing), MCP servers use the **MCP Tasks Extension** to return a durable task handle immediately rather than blocking the JSON-RPC call, paired with `elicitation/create` when human confirmation is required.
   - **Deprecation Compliance:** Per the [2026-07-28 MCP Specification](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture), client-side `sampling/createMessage` and protocol-level `logging` are deprecated; MCP servers that require LLM inference call the internal Ollama gateway directly and emit telemetry via OpenTelemetry.

### 3.3 Agent Skills Standard (`SKILL.md`) & Progressive Disclosure

To equip ephemeral workers with deep marketing expertise (copywriting frameworks, platform algorithm rules, visual design rubrics, and competitor teardown methodologies) without exhausting local Ollama context windows, all procedural knowledge is structured according to the [Agent Skills Specification](https://agentskills.io/specification):

```text
skills/
├── linkedin-b2b-thought-leadership/
│   ├── SKILL.md                # Required: YAML frontmatter + core instructions (<500 lines, <5000 tokens)
│   ├── references/
│   │   ├── HOOK_PATTERNS.md    # Loaded on-demand: high-converting B2B hook structures
│   │   └── ALGORITHM_RULES.md  # Loaded on-demand: dwell-time and external-link penalties
│   ├── scripts/
│   │   └── validate_post.py    # Executable validator: checks character limits, hashtag count, readability
│   └── assets/
│       └── carousel_spec.json  # JSON Schema template for 1080x1350 PDF carousel slides
```

Every `SKILL.md` file must validate against `skills-ref validate` and adhere to the following frontmatter contract:
- `name`: 1–64 characters, lowercase alphanumeric and single hyphens only (`^[a-z0-9]+(-[a-z0-9]+)*$`), matching the parent directory name exactly.
- `description`: 1–1,024 characters stating both *what* the skill does and *when* the orchestrator or worker should activate it.
- `compatibility`: Optional (max 500 chars) declaring runtime dependencies (e.g., `Requires Python 3.12+, Pillow, and access to BrandRAG MCP server`).
- `allowed-tools`: Space-separated pre-approved tool scope (e.g., `mcp_brand_rag:query_guidelines Bash(python3:scripts/validate_post.py)`).

### 3.4 Agent-Computer Interface (ACI) & Poka-Yoke Tool Engineering

Following [Anthropic's Appendix 2: Prompt Engineering Your Tools](https://www.anthropic.com/research/building-effective-agents), every tool exposed to an Ollama worker must be engineered for mistake-proofing (*poka-yoke*):
- Require canonical, unambiguous arguments (e.g., always require ISO-8601 UTC timestamps with explicit timezone offsets `2026-11-05T14:00:00Z` and enumerated `PlatformLiteral` types rather than free-text strings).
- Avoid requiring the LLM to generate deeply escaped JSON-inside-JSON or line-counted diffs; accept structured Pydantic fields and return actionable validation errors directly to the model when a constraint fails.

## 4. Orchestration Layer, Agent Graphs, and Multi-Agent Topologies

The core control plane of the Self-Hosted Agentic Marketing Platform is modeled as a hierarchical, checkpointed **LangGraph `StateGraph`** ([LangGraph 2026 Guide](https://futureagi.com/blog/what-is-langgraph-2026/)) paired with **Pydantic AI** ([Airflow Pydantic AI Toolsets](https://airflow.apache.org/docs/apache-airflow-providers-common-ai/0.5.0/toolsets/index.html)) inside the leaf worker nodes.

### 4.1 Hybrid Multi-Agent Topology: Supervisor Tool-Calling + Subgraph Teams + Map-Reduce Fan-Out

Rather than routing every low-level message through a single central LLM call with full conversation history—which [LangChain's multi-agent benchmarks](https://medium.com/@attia.atef92/handoff-vs-supervisor-why-your-multi-agent-architecture-choice-matters-%EF%B8%8F-40cadb0e0dc2) and the [LangGraph Supervisor documentation](https://github.com/langchain-ai/langgraph-supervisor-py) note can bloat context and latency—the platform implements a **Three-Tier Hybrid Graph Topology**:

1. **Tier 1: Master Orchestrator Supervisor (`MasterOrchestratorGraph`)**
   - Powered by a primary local reasoning model (`ollama:llama3.3:70b` or `ollama:qwen2.5:72b`).
   - Owns global state, user intent parsing, campaign lifecycle governance, human approval gates (`interrupt()`), and top-level delegation across four compiled domain subgraphs.
   - Uses custom handoff tools built with `InjectedState`, `InjectedToolCallId`, and `Command(goto=subgraph_name, graph=Command.PARENT, update=...)` alongside `output_mode="last_message"` and `create_forward_message_tool` ([LangGraph Supervisor Python SDK](https://github.com/langchain-ai/langgraph-supervisor-py)) so only validated structured summaries—never raw intermediate scratchpads—return to the Master Orchestrator's context window.
2. **Tier 2: Domain Subgraph Teams (Scoped State & Peer Handoffs)**
   - **Research & Strategy Subgraph:** Executes market intelligence, competitor scraping, audience segmentation, and Agentic RAG synthesis. Uses direct peer handoffs (`Command(update=..., goto=...)`) between the *Scraper Worker*, *Competitor Analyst*, and *Strategy Synthesizer* before returning the consolidated strategy brief to the parent graph via `Command(graph=Command.PARENT, update=...)`.
   - **Campaign & Creative Blueprint Subgraph:** Uses a **Plan-and-Solve** loop to compile the master `campaign.json` specification, then dispatches media generation tasks (image, graphic, promotional video, tutorial script) and enforces brand compliance via a **Reflexion** evaluator gate.
   - **Multi-Platform Publishing Subgraph:** Uses LangGraph's `Send(node_name, payload)` primitive for **Map-Reduce Parallel Fan-Out** across all 8 target platforms (LinkedIn, YouTube, Instagram, Threads, Facebook, X, Pinterest, Google Business Profile). Each platform branch runs an isolated ephemeral worker equipped with that platform's specific `SKILL.md` and MCP publishing toolset.
   - **Closed-Loop Analytics & Optimization Subgraph:** Runs on a scheduled cron trigger or manual invocation using a **ReWOO** pipeline to pull 7-day and 28-day cross-platform metrics, compute z-score anomalies in Polars/PostgreSQL, and trigger autonomous creative or schedule adjustments when conversion or engagement thresholds drift.
3. **Tier 3: Ephemeral Pydantic AI Leaf Workers**
   - Each leaf node instantiates a short-lived `pydantic_ai.Agent` bound to a strict `output_type` (`BaseModel`), scoped MCP client connections, and explicit retry budgets (`retries=3` for read/analysis nodes; `retries=1` for write/publish nodes). Once the validated Pydantic object is returned and merged into the LangGraph state channel via its reducer, the worker context is garbage-collected.

### 4.2 State Schema, Reducers, Checkpointing, and Idempotent Interrupts

```python
import operator
from datetime import datetime
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, Field
from langchain_core.tools import tool, BaseTool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import InjectedState
from langgraph.types import Send, Command, interrupt
from langgraph.checkpoint.postgres import PostgresSaver

PlatformType = Literal[
    "linkedin", "youtube", "instagram", "threads",
    "facebook", "x", "pinterest", "google_business_profile"
]

class PlatformAssetSpec(BaseModel):
    platform: PlatformType
    copy_text: str
    media_urls: list[str]
    aspect_ratio: Literal["1:1", "4:5", "9:16", "16:9", "2:3"]
    scheduled_utc: datetime
    idempotency_key: str = Field(description="SHA-256 of campaign_id + platform + scheduled_utc")
    compliance_passed: bool

class CampaignBlueprint(BaseModel):
    campaign_id: str
    objective: str
    target_audience_segments: list[str]
    positioning_statement: str
    platform_assets: list[PlatformAssetSpec]

def merge_platform_results(
    existing: list[dict], new_items: list[dict]
) -> list[dict]:
    # Deterministic reducer deduplicating parallel Send() worker outputs by idempotency_key
    by_key = {item["idempotency_key"]: item for item in existing}
    for item in new_items:
        by_key[item["idempotency_key"]] = item
    return list(by_key.values())

class MarketingOSState(TypedDict):
    thread_id: str
    user_command: str
    task_description: str
    active_skills: list[str]
    research_dossier: dict
    campaign_blueprint: dict
    platform_publish_results: Annotated[list[dict], merge_platform_results]
    critique_history: Annotated[list[str], operator.add]
    revision_count: int
    human_approved: bool
    analytics_anomalies: list[dict]

def create_scoped_subgraph_handoff(
    *, subgraph_name: str, tool_name: str, description: str
) -> BaseTool:
    # Custom handoff tool forwarding only scoped task_description to avoid context bloat
    @tool(tool_name, description=description)
    def handoff_to_subgraph(
        task_description: Annotated[str, "Scoped objective and constraints for the subgraph team."],
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        return Command(
            goto=subgraph_name,
            graph=Command.PARENT,
            update={
                "task_description": task_description,
                "active_skills": state.get("active_skills", []),
            },
        )
    return handoff_to_subgraph
```

**Critical Production Rule for `interrupt()` and Super-Step Replay:**
Because `PostgresSaver` checkpoints graph state at super-step boundaries ([LangGraph 2026 Stateful Graph Guide](https://futureagi.com/blog/what-is-langgraph-2026/)), any node that calls `interrupt()` will re-execute from line 1 when resumed via `graph.invoke(Command(resume=approval_payload), config)`. Therefore:
- **Never** place non-idempotent side effects (such as charging ad spend, minting external media jobs, or inserting un-keyed database rows) *above* an `interrupt()` call inside the same node function.
- Split the workflow into three distinct nodes: `prepare_publish_payload_node` (pure state preparation) $\rightarrow$ `human_approval_gate_node` (calls `interrupt()` and returns `Command(goto="dispatch_platform_workers" if approved else "campaign_planner_node")`) $\rightarrow$ `execute_platform_publish_node` (executes idempotent API calls using `idempotency_key`).

## 5. Domain Subsystems & External Platform Integration Specification

To fulfill the functional requirements of `Agentic Brand Marketing.md` without third-party SaaS schedulers, the platform integrates external social, media, and storage services behind a **Zero-Trust MCP Tool Proxy**.

### 5.1 Multi-Platform Publishing Matrix & API Contracts

All eight target social platforms are wrapped as dedicated MCP Tools inside the `SocialPlatformGatewayMCP` server (`Streamable HTTP` transport). Worker agents never receive raw OAuth client secrets or refresh tokens; the MCP server resolves tenant credentials from an encrypted secret backend (HashiCorp Vault / PostgreSQL pgcrypto), enforces platform rate limits, and attaches idempotency keys.

| Target Platform | Official API / Protocol Surface | Supported Formats & Media Constraints | Scheduling & Asynchronous Publishing Pattern |
| :--- | :--- | :--- | :--- |
| **LinkedIn** | LinkedIn Marketing / Community Management API (`/rest/posts`, `/rest/images`, `/rest/videos`) | Text (max 3,000 chars), single/multi-image, native PDF carousel (`1080x1350`), video (`1:1`, `16:9`, `9:16`). | Multi-part upload initialize $\rightarrow$ binary chunk upload $\rightarrow$ finalize $\rightarrow$ post creation or Celery beat scheduled dispatch. |
| **YouTube** | YouTube Data API v3 (`videos.insert` resumable upload) & YouTube Analytics API | Long-form video (`16:9`), YouTube Shorts (`9:16`, $\le 60\text{s}$), custom thumbnails, titles (max 100 chars), descriptions, tags, `publishAt` ISO timestamp. | Resumable upload yields `external_video_id` via MCP Tasks extension; native scheduled publishing via `status.privacyStatus="private"` + `status.publishAt`. |
| **Instagram** | Instagram Graph API (`/me/media`, `/me/media_publish`) | Feed images (`1:1`, `4:5`), Carousels (up to 10 items), Reels (`9:16`), Stories (`9:16`). | Two-stage container lifecycle: create media container (`POST /media`) $\rightarrow$ poll container `status_code == FINISHED` via background worker $\rightarrow$ call `/media_publish`. |
| **Threads** | Meta Threads API (`/me/threads`, `/me/threads_publish`) | Text posts (max 500 chars), image/video attachments, carousel threads, reply chains. | Two-stage container creation and publication identical to Instagram Graph pattern; thread chains link parent `reply_to_id` sequentially. |
| **Facebook** | Meta Graph API (`/page-id/feed`, `/page-id/photos`, `/page-id/videos`) | Page posts, native video reels, link previews, scheduled posts (`published=false` + `scheduled_publish_time`). | Supports native server-side scheduling (`scheduled_publish_time` Unix timestamp between 10 mins and 30 days ahead) plus local Celery fallback. |
| **X (Twitter)** | X API v2 (`POST /2/tweets`) + Media Upload v1.1/v2 (`INIT`, `APPEND`, `FINALIZE`, `STATUS`) | Text (280 chars standard), multi-tweet threads, 4-image grids, native video (`max 512MB`). | Chunked media upload returns `media_id_string`; thread sequences execute atomically with `reply.in_reply_to_tweet_id` chaining. |
| **Pinterest** | Pinterest REST API v5 (`POST /v5/pins`, `/v5/media`) | Standard Pins (`2:3` aspect ratio, `1000x1500`), Video Pins, Idea Pins, board assignment, destination URL. | Register media upload (`POST /v5/media`) $\rightarrow$ upload to pre-signed S3 URL $\rightarrow$ create Pin tied to `board_id`. |
| **Google Business Profile** | Google Business Profile APIs (`accounts.locations.localPosts.create`) | What's New posts, Event posts, Offer posts (with coupon codes/terms), call-to-action buttons (`BOOK`, `ORDER`, `LEARN_MORE`), photo attachments. | Direct REST creation with structured `callToAction` and `event`/`offer` schedule windows; polled for `LIVE` moderation state. |

### 5.2 Agentic RAG Knowledge Base & Media Library Architecture

1. **Hybrid Agentic RAG Knowledge Base (`BrandKnowledgeMCP`):**
   - Backed by **Qdrant** (dense embeddings via local `nomic-embed-text` / `bge-m3` on Ollama + sparse BM25 vectors via FastEmbed) and **PostgreSQL** for relational campaign history.
   - Exposes MCP Resources (`brand://guidelines/{brand_id}`, `brand://personas/{segment_id}`) for deterministic context injection and MCP Tools (`search_brand_knowledge`, `retrieve_winning_campaigns`, `store_campaign_learnings`) with mandatory cross-encoder reranking (`openinference.span.kind = "RERANKER"`).
2. **Centralized Media Library & Asynchronous Rendering Pipeline (`MediaStudioMCP`):**
   - Stores all AI-generated and uploaded images, graphics, promotional videos, and tutorials in self-hosted S3-compatible object storage (**MinIO**) indexed in PostgreSQL (`media_assets` table with SHA-256 content hash, MIME type, resolution, duration, aspect ratio, prompt lineage, and `campaign_id` foreign key).
   - Long-running external or local media jobs (ComfyUI / Flux image generation, Runway / Sora / Kling / Wan video synthesis, FFmpeg subtitle burn-in) never block an Ollama worker thread. The worker submits the generation spec and receives a task handle; a background Celery worker polls completion, validates media dimensions against `PlatformAssetSpec`, uploads the asset to MinIO, and invokes `graph.invoke(Command(resume={"asset_url": minio_uri}), config)`.

### 5.3 Unified Workspace & Closed-Loop Autonomous Optimization (`Observe -> Analyze -> Act -> Evaluate`)

The Unified Workspace exposes a FastAPI + Next.js control plane backed by PostgreSQL, Qdrant, MinIO, and Arize Phoenix:
- **Closed-Loop Feedback Engine:** Every 6 hours (and on weekly backup snapshots), a scheduled cron triggers the `ClosedLoopAnalyticsSubgraph`.
- **Step 1 (Observe):** Parallel MCP calls ingest impressions, reach, watch time, CTR, and conversions across all 8 platforms into PostgreSQL time-series tables.
- **Step 2 (Analyze):** A Polars analytics pipeline computes rolling 7-day and 28-day z-scores per platform and content pillar:
  $$Z_{\text{metric}} = \frac{X_{t} - \mu_{28d}}{\sigma_{28d}}$$
  Any asset or platform where $Z_{\text{CTR}} < -1.5$ or $Z_{\text{conversion}} < -1.5$ is flagged as an underperformance anomaly; $Z > +1.5$ is flagged as a breakout pattern.
- **Step 3 (Act):** The Master Orchestrator spawns diagnostic Research and Creative workers to inspect the underperforming assets, compare them against breakout baselines in the Agentic RAG Knowledge Base, and generate a revised `campaign.json` delta (adjusting posting windows, hook styles, or media formats).
- **Step 4 (Evaluate):** Post-intervention performance is tracked over the subsequent 7-day window, and verified causal findings are committed into Qdrant (`brand://learnings/experiments`) with weekly cold backups written to object storage.

## 6. Multi-Layer Observability, OpenInference Distributed Tracing, and Agent Evaluation

Because multi-agent systems fail silently via subtle routing drift, degraded retrieval, or tool schema retries, observability and evaluation are embedded directly into the runtime data plane using [OpenInference Semantic Conventions](https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md) and self-hosted [Arize Phoenix](https://levelop.dev/blog/llm-observability-tools-comparison-2026).

### 6.1 OpenInference Span Hierarchy & Required Attributes

Every user command or scheduled optimization cycle creates a root OpenTelemetry trace propagated across FastAPI, LangGraph nodes, Celery queues, and MCP servers via the W3C `traceparent` header. Each operation must emit its canonical `openinference.span.kind` ([OpenInference Spec](https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md)):

| Operation Layer | `openinference.span.kind` | Mandatory OpenInference Attributes | Operational Purpose |
| :--- | :--- | :--- | :--- |
| **LangGraph Node / Orchestrator / Sub-Agent** | `AGENT` or `CHAIN` | `agent.name`, `graph.node.id`, `graph.node.name`, `graph.node.parent_id`, `session.id`, `user.id`, `input.value`, `output.value` | Reconstructs the exact multi-agent execution DAG and parent-child delegation tree in the Phoenix UI. |
| **Ollama Model Inference** | `LLM` | `llm.system="ollama"`, `llm.provider="ollama"`, `llm.model_name`, `llm.invocation_parameters`, `llm.input_messages.<i...>` (flattened), `llm.output_messages.<i...>`, `llm.token_count.prompt`, `llm.token_count.completion`, `llm.token_count.completion_details.reasoning`, `llm.token_count.total` | Tracks token velocity, reasoning token overhead, prompt caching hits, and per-node latency across local models. |
| **FastRouter / Rubric Gate** | `DECISION` | `decision.system`, `decision.provider`, `decision.model_name`, `decision.token_count.input`, `decision.token_count.output` | Captures discrete routing classifications and binary policy gate decisions distinctly from free-form text generation. |
| **MCP Tool Execution** | `TOOL` | `tool.name`, `tool.description`, `tool.id`, `tool.parameters`, `tool_call.function.name`, `tool_call.function.arguments`, `tool_call.id`, `exception.type`, `exception.message` | Audits exact arguments passed to external APIs, validation failures, and tool P95 latency. |
| **Qdrant Vector Search & Reranking** | `RETRIEVER` & `RERANKER` | `retrieval.documents.<i>.document.id`, `document.score`, `document.content`, `reranker.query`, `reranker.model_name`, `reranker.top_k`, `reranker.output_documents.<i>.*` | Diagnoses RAG context precision, empty retrievals, and embedding drift. |
| **Safety & Brand Policy Filter** | `GUARDRAIL` | `input.value`, `output.value`, `annotation.name="brand_safety"`, `annotation.label`, `annotation.score` | Records blocked prompts, PII/credential redaction, and brand policy interventions. |
| **Online / CI Judge Scoring** | `EVALUATOR` | `evaluation.annotator_kind` (`"CODE"` or `"LLM"`), `evaluation.name`, `evaluation.score`, `evaluation.label`, `evaluation.explanation`, `trace.evaluations.0.evaluation.*` | Attaches deterministic and LLM-as-a-Judge scores directly to spans and root traces. |

### 6.2 Four-Layer Production Evaluation Architecture

1. **Layer 1: Deterministic Schema, Poka-Yoke & Source-of-Truth Verification (`evaluation.annotator_kind = "CODE"`)**
   - Every worker output is validated against its Pydantic `output_type` (`CampaignBlueprint`, `PlatformAssetSpec`).
   - Platform-specific deterministic validators verify hard constraints prior to scheduling: X character count $\le 280$, Threads $\le 500$, LinkedIn $\le 3,000$, valid aspect ratios (`9:16` for Reels/Shorts, `2:3` for Pinterest), and zero hallucinated URLs or unverified KPI claims against PostgreSQL ground truth.
2. **Layer 2: Graph Trajectory & Tool-Order Evaluation (`trace.evaluations`)**
   - Evaluates the sequence of `TOOL` and `AGENT` spans within a trace using trajectory precision, recall, and strict ordering assertions:
     $$\text{TrajectoryOrderValid}(T_{\text{actual}}, T_{\text{expected}}) = \mathbb{I}\left(\forall (u \prec v) \in T_{\text{expected}}, \;\text{index}(u, T_{\text{actual}}) < \text{index}(v, T_{\text{actual}})\right)$$
   - Enforces that `search_brand_knowledge` (`RETRIEVER`) and `fetch_platform_metrics` (`TOOL`) always execute *before* `compile_campaign_json` or any `publish_*` tool call.
3. **Layer 3: Isolated LLM-as-a-Judge Rubric Evaluation (`evaluation.annotator_kind = "LLM"`)**
   - An isolated judge model scores sampled production traces and pre-publish drafts across three categorical rubrics (`evaluation.score` $\in [0.0, 1.0]$ + `evaluation.explanation`): **Brand Voice Fidelity**, **Groundedness / Hallucination-Free Claims**, and **Platform-Native Hook Quality**. Any draft scoring $< 0.85$ triggers a `Reflexion` loop back to the Creative Worker.
4. **Layer 4: Offline CI/CD Regression & Token Budget Guardrails (`pydantic-evals` + `TestModel`)**
   - Structural graph wiring, tool registration, and schema parsing are verified on every commit using Pydantic AI's `TestModel` (burning zero LLM tokens) ([Pydantic AI v2 Verification](https://blog.csdn.net/ygn12/article/details/165331769)).
   - Before promoting prompt, skill, or model updates to production, a golden dataset of 50+ multi-step marketing scenarios runs against Arize Phoenix Experiments. Builds fail automatically if trajectory accuracy drops below `95%`, schema retry rate exceeds `5%`, or total token consumption per campaign increases by more than `20%`.

### 6.3 Reference Implementation: OpenInference Instrumentation & Trajectory Gate

```python
from opentelemetry import trace
from phoenix.otel import register
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes

tracer_provider = register(
    project_name="self-hosted-marketing-os",
    endpoint="http://phoenix:6006/v1/traces",
)
tracer = trace.get_tracer("marketing_os.orchestrator")

def trace_and_evaluate_subgraph_run(
    thread_id: str,
    node_id: str,
    parent_node_id: str,
    executed_tools: list[str],
    required_sequence: list[str],
) -> bool:
    with tracer.start_as_current_span(
        name=f"Subgraph.{node_id}",
        attributes={
            SpanAttributes.OPENINFERENCE_SPAN_KIND: OpenInferenceSpanKindValues.AGENT.value,
            SpanAttributes.SESSION_ID: thread_id,
            SpanAttributes.AGENT_NAME: node_id,
            "graph.node.id": node_id,
            "graph.node.parent_id": parent_node_id,
        },
    ) as span:
        for idx, tool_name in enumerate(executed_tools):
            span.set_attribute(
                f"llm.output_messages.0.message.tool_calls.{idx}.tool_call.function.name",
                tool_name,
            )

        # Verify strict topological ordering of required tool calls
        positions = [
            executed_tools.index(req) for req in required_sequence if req in executed_tools
        ]
        order_valid = (
            len(positions) == len(required_sequence)
            and positions == sorted(positions)
        )

        span.set_attribute("trace.evaluations.0.evaluation.name", "trajectory_ordering")
        span.set_attribute("trace.evaluations.0.evaluation.annotator_kind", "CODE")
        span.set_attribute("trace.evaluations.0.evaluation.score", 1.0 if order_valid else 0.0)
        span.set_attribute(
            "trace.evaluations.0.evaluation.label",
            "valid_trajectory" if order_valid else "out_of_order_or_missing_tool",
        )
        return order_valid
```

## 7. End-to-End Implementation Blueprint & Directory Architecture

To translate this specification into a deployable repository, structure the codebase around modular subgraphs, MCP microservices, and validated Agent Skills:

```text
agentic-marketing-os/
├── orchestrator/
│   ├── graph.py                  # Root MasterOrchestratorGraph (StateGraph + PostgresSaver)
│   ├── state.py                  # MarketingOSState TypedDict, Pydantic models, and reducers
│   ├── subgraphs/
│   │   ├── research_strategy.py  # ReAct + Peer Handoff subgraph for market/competitor research
│   │   ├── campaign_creative.py  # Plan-and-Solve + Reflexion subgraph producing campaign.json
│   │   ├── publishing_fanout.py  # Send() Map-Reduce parallel fan-out across 8 platforms
│   │   └── closed_loop_eval.py   # ReWOO + Polars Z-score anomaly detection & auto-optimization
│   └── workers/
│       └── pydantic_worker.py    # Ephemeral Pydantic AI v2 Agent factory with MCP toolsets
├── mcp_servers/
│   ├── brand_rag_server.py       # FastMCP server (Streamable HTTP) wrapping Qdrant + PostgreSQL
│   ├── social_gateway_server.py  # Zero-trust FastMCP proxy for LinkedIn, YT, IG, X, Threads, FB, Pin, GBP
│   └── media_studio_server.py    # FastMCP server with Tasks extension for MinIO + image/video jobs
├── skills/                       # Validated via `skills-ref validate`
│   ├── brand-voice-audit/
│   │   ├── SKILL.md
│   │   └── scripts/check_tone.py
│   ├── multi-platform-copy/
│   │   ├── SKILL.md
│   │   └── references/PLATFORM_LIMITS.md
│   └── competitor-recon/
│       ├── SKILL.md
│       └── scripts/parse_serp.py
├── observability/
│   ├── tracing.py                # OpenInference + Arize Phoenix OTel registration & W3C propagation
│   └── evals/
│       ├── trajectory_evals.py   # Layer 2 deterministic trajectory order & precision checks
│       ├── rubric_judges.py      # Layer 3 LLM-as-a-Judge evaluators
│       └── test_golden_suite.py  # Layer 4 CI/CD regression suite using TestModel & Phoenix Datasets
└── docker-compose.yml            # Self-hosted stack: Ollama, Postgres, Qdrant, MinIO, Redis/Celery, Phoenix
```

## 8. Verified Reference Documentation & Canonical Sources

- **Anthropic Engineering — Building Effective Agents:** [https://www.anthropic.com/research/building-effective-agents](https://www.anthropic.com/research/building-effective-agents)
- **Anthropic — Building Agents with the Claude Agent SDK (Subagents & MCP):** [https://claude.com/resources/articles/building-agents-with-the-claude-agent-sdk](https://claude.com/resources/articles/building-agents-with-the-claude-agent-sdk)
- **Model Context Protocol (MCP) Architecture Overview (2026-07-28):** [https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture)
- **Model Context Protocol (MCP) Canonical Specification (2026-07-28):** [https://modelcontextprotocol.io/specification/2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28)
- **Model Context Protocol (MCP) Resources Specification:** [https://modelcontextprotocol.io/specification/2026-07-28/server/resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)
- **Agent Skills Format Specification (`SKILL.md` Standard):** [https://agentskills.io/specification](https://agentskills.io/specification)
- **Agent Skills Official Repository:** [https://github.com/agentskills/agentskills](https://github.com/agentskills/agentskills)
- **Anthropic Public Agent Skills Collection:** [https://github.com/anthropics/skills](https://github.com/anthropics/skills)
- **LangGraph Supervisor Python Reference Implementation:** [https://github.com/langchain-ai/langgraph-supervisor-py](https://github.com/langchain-ai/langgraph-supervisor-py)
- **LangGraph 2026 Stateful Graph Guide (`StateGraph`, `Send`, `Command`, `PostgresSaver`, `interrupt`):** [https://futureagi.com/blog/what-is-langgraph-2026/](https://futureagi.com/blog/what-is-langgraph-2026/)
- **Durable Human-in-the-Loop AI Workflows with LangGraph & PostgreSQL:** [https://nirajiitr.com/blog/durable-hitl-ai-workflows-langgraph-postgresql-nextjs](https://nirajiitr.com/blog/durable-hitl-ai-workflows-langgraph-postgresql-nextjs)
- **Multi-Agent Architecture Benchmarks (Handoff vs. Supervisor):** [https://medium.com/@attia.atef92/handoff-vs-supervisor-why-your-multi-agent-architecture-choice-matters-%EF%B8%8F-40cadb0e0dc2](https://medium.com/@attia.atef92/handoff-vs-supervisor-why-your-multi-agent-architecture-choice-matters-%EF%B8%8F-40cadb0e0dc2)
- **Pydantic AI Toolsets & MCP Client Integration (`MCPServerStreamableHTTP`, `MCPServerStdio`):** [https://airflow.apache.org/docs/apache-airflow-providers-common-ai/0.5.0/toolsets/index.html](https://airflow.apache.org/docs/apache-airflow-providers-common-ai/0.5.0/toolsets/index.html)
- **Pydantic AI v2 API Surface & Production Retry Verification:** [https://blog.csdn.net/ygn12/article/details/165331769](https://blog.csdn.net/ygn12/article/details/165331769)
- **OpenInference Semantic Conventions Specification:** [https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md](https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md)
- **OpenInference Instrumentation Suite Repository:** [https://github.com/Arize-ai/openinference](https://github.com/Arize-ai/openinference)
- **Arize Phoenix AI Observability & Evaluation Platform:** [https://github.com/arize-ai/phoenix](https://github.com/arize-ai/phoenix)
- **LLM Observability Tools 2026 Comparison Guide (Phoenix, Langfuse, Helicone, AgentOps):** [https://levelop.dev/blog/llm-observability-tools-comparison-2026](https://levelop.dev/blog/llm-observability-tools-comparison-2026)
- **ControlScope & Reasoning Loop Taxonomy (ReAct, Plan-and-Solve, ReWOO, LLMCompiler):** [https://arxiv.org/html/2609.34313v1](https://arxiv.org/html/2609.34313v1)
- **Autonomous AI Worker Design Patterns (ReAct arXiv:2210.03629, Reflexion arXiv:2303.11366, ReWOO arXiv:2305.18323, Plan-and-Solve arXiv:2305.04091):** [https://blog.muralikannan.com/designing-autonomous-ai-workers/](https://blog.muralikannan.com/designing-autonomous-ai-workers/)
