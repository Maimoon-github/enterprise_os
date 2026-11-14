# Gap, Risk, Dependency, and Modification-Point Analysis

---

## 1. Gap Register (Chief of Staff Lenses)

Derived strictly from the Phase 4 Integration Assessment matrix:

| # | Gap Identifier | Affected CoS Lens | Gap Description & Current Codeposture | Target Architecture Expectation | Evidence / Citation |
|---|---|---|---|---|---|
| **G1** | **No Remote Network Surface** | Command, Delegation | `dashboard.py` strictly binds to `127.0.0.1:8765` and rejects non-loopback Host headers (`valid_host()`). Chopify cannot be commanded across network/container boundaries without an adapter. | Lightweight HTTP/REST API or adapter reachable across Docker network (`Recommended architecture.md`, lines 24, 66). | `dashboard.py:173`<br>`test_dashboard.py:37` |
| **G2** | **No Model Context Protocol (MCP) Interface** | Command, Delegation, Reporting | No MCP tool definitions, resources, or stdio/SSE server wrappers exist. An agentic LLM (CoS) cannot discover tools or invoke clipping via standard MCP tool calls. | Native MCP server providing structured tool calling for business OS agents (`Recommended architecture.md`, line 24). | Negative search: 0 hits for `mcp` in chopify codebase (`FACT`). |
| **G3** | **No Webhook or Event Emission** | Monitoring, Orchestration | Long-running tasks (transcription, rendering) emit no asynchronous callbacks, webhooks, or Redis events. Callers must actively poll file state or HTTP endpoints. | Central event bus (Redis) for state synchronization and workflow triggers (`Recommended architecture.md`, lines 23, 62). | Negative search: 0 hits for `webhook`, `redis` (`FACT`). |
| **G4** | **No Enterprise Auth or Tenant Isolation** | Controlled Data Access | Chopify relies on an ephemeral, in-memory token (`secrets.token_urlsafe(32)`) designed exclusively for local CSRF protection. No API keys, service accounts, or RBAC exist. | Controlled data access with environment isolation via Docker Compose (`Recommended architecture.md`, line 66). | `dashboard.py:66, 240`<br>`product.json:29` |
| **G5** | **No Machine-Readable Run Summary Stream** | Monitoring, Reporting | The CLI prints unstructured human-readable logs to stdout. Structured data exists only in scattered JSON files (`project.json`, `selection.json`, `segments.json`, `.meta.json`). | Structured, streaming execution events and machine-readable execution summaries for CoS scorecard ingestion. | `chopify.py:201`<br>`projects.py:200` |
| **G6** | **Absence of Task Cancellation in Service Layer** | Delegation, Orchestration | `dashboard.py` provides no HTTP endpoint to cancel an active queued or running job once submitted to `ThreadPoolExecutor`. Only server shutdown terminates children. | Cancellable, preemptible tasks with graceful resource release. | `dashboard.py:136–142` (cancellation only on server close) |
| **G7** | **Disconnected Shared Intelligence** | Shared Intelligence | Brand assets and guidelines are loaded strictly from local file paths (`--brand examples/brand.json`). Zero connection to central PostgreSQL or Qdrant vector memory. | Central knowledge layer providing brand voice and RAG context across agents (`Recommended architecture.md`, lines 22, 61). | `branding.py:92`<br>`business-os/shared/knowledge/.gitkeep` |
| **G8** | **Incomplete Marketing Domain Scope (Postiz Boundary)** | Command, Orchestration | Chopify handles only short-form video clipping. Social post drafting, multi-platform publishing, and performance tracking live outside Chopify. | Full marketing execution: post creation, publishing, and weekly analytics reporting (`Agents info.md`, lines 20–27). | `docs/product.json:30`<br>`Agents info.md:20–27` |

---

## 2. Risk Register

| # | Risk Description | Affected CoS Lens | Likelihood | Impact | Severity | Mitigation Strategy |
|---|---|---|---|---|---|---|
| **R1** | **Concurrent Directory Collisions**<br>Multiple CoS delegation requests commanding the same project directory simultaneously will corrupt `project.json` and overwrite intermediate render artifacts. | Delegation, Orchestration | High | High | **CRITICAL** | Enforce strictly unique project identifiers (`uuid.uuid4().hex[:12]`) per task, or require all CoS delegations to use isolated `--workdir` / `--projects-dir` paths (`projects.py:126`). |
| **R2** | **Blocking / Long-Running Command Starvation**<br>Video rendering and transcription can take 10–60+ minutes. A CoS invoking synchronous CLI commands will block its execution thread, leading to gateway timeouts or hung orchestrators. | Command, Delegation | High | High | **CRITICAL** | Mandate asynchronous execution: CoS must invoke `--action prepare` / `--action render` via background workers or poll `dashboard.py` status asynchronously. |
| **R3** | **Credential / Host Path Exposure via Network Adapters**<br>Opening `dashboard.py` or exposing a wrapper API to external networks without strict host path validation could allow arbitrary host file reading via `GET /media/...`. | Controlled Data Access | Medium | High | **HIGH** | Restrict adapter path resolution to an explicit allowlisted project directory tree (`test_dashboard.py:89` pins boundary containment); implement token authentication. |
| **R4** | **Silent Media Degradation / Zero-Clip Results**<br>A source video with low audio variance, missing speech, or strict thresholds will yield zero clips. If uninspected, the CoS might assume a failure rather than a valid empty result. | Reporting, Orchestration | High | Medium | **MEDIUM** | CoS must inspect `selection.json` to differentiate between pipeline failures (`status: "failed"`) and zero passing candidates (`passing: 0`, `score_max < threshold`). |
| **R5** | **Brand Configuration Drift & Validation Failures**<br>CoS injecting unvalidated brand presets can cause ffmpeg ASS render crashes if invalid color strings, font names, or filter flags are passed. | Command, Orchestration | Medium | High | **HIGH** | Utilize `branding.py:validate_brand()` in the integration adapter before passing configuration to `chopify.py` / `projects.py`. |
| **R6** | **Subprocess Leaks on Abrupt CoS Cancellation**<br>Killing a CoS parent process without sending `SIGINT`/`SIGTERM` to the child `ffmpeg` or `yt-dlp` subprocesses will leave orphaned CPU/GPU-intensive background jobs running. | Delegation, Monitoring | Medium | High | **HIGH** | The integration adapter must track process group IDs (`os.setpgrp()`) and propagate termination signals to the entire process tree on task cancellation. |
| **R7** | **Upstream Platform Scraping Fragility**<br>`yt-dlp` video downloading is vulnerable to bot-detection blocks and YouTube 403 changes, breaking automated pipelines without warning. | Command, Delegation | High | Medium | **MEDIUM** | Prefer local video file paths for mission-critical brand workflows; implement automatic retry and `yt-dlp` version auto-check in the integration layer. |

---

## 3. Dependency Map

### 3.1 Current Local Project Dependencies
- **Runtime Environment:** Python 3.11+ (`requirements.txt`).
- **Core Python Packages:** `yt-dlp` (video downloading), `faster-whisper` (word-level speech transcription), `opencv-python` (`cv2`, visual feature analysis & face tracking), `numpy` (timeline feature arrays).
- **System Binary Tooling:** `ffmpeg` and `ffprobe` (compiled with `libx264`, `aac`, and `libass` subtitle filter). Validated at runtime by `chopify.py:check_environment()`.
- **Local AI Engines (Optional):**
  - Face Tracking: YuNet ONNX model (automatically downloaded to local cache if missing, `render_clips.py:317`).
  - Semantic Search: Local Ollama daemon running on `http://127.0.0.1:11434` with model `nomic-embed-text` (`semantic.py:14`).
  - Local LLM Reranking: Local Ollama model (e.g. `qwen2.5:7b`, `score_clips.py:1272`).
- **Development & Testing:** `pytest>=8.0` (`requirements-dev.txt`), Pillow (`PIL`, for social preview generator), GitHub Actions (`.github/workflows/ci.yml`).

### 3.2 Target Architecture Infrastructure: Introduced vs. Assumed
When integrating with the **Local-First Federated Multi-Agent Business OS**, the dependencies bifurcate:

| Infrastructure Component | Status in Chopify Today | Role in Target CoS Integration | Introduced by Adapter vs Assumed by Core |
|---|---|---|---|
| **Docker Compose** | `ABSENT` (No Dockerfile or compose service) | Provides process isolation and container networking between CoS and Chopify. | **Introduced:** An integration adapter must containerize Chopify with ffmpeg and CUDA/CPU drivers. |
| **Redis Event Bus** | `ABSENT` (0 hits) | Transmits async events (`video.transcribed`, `clips.rendered`, `render.failed`) to CoS and Postiz. | **Introduced:** A lightweight integration bridge must publish Chopify status updates to Redis. |
| **PostgreSQL + Qdrant** | `ABSENT` (0 hits) | Stores centralized brand assets, product catalog vectors, and past clip engagement history. | **Assumed:** Managed by the central shared intelligence layer; Chopify adapter queries this to generate `brand.json`. |
| **Postiz Social Bridge** | `ABSENT` (in Chopify; present in sibling folder) | Receives rendered MP4, SRT, and `.meta.json` from Chopify for scheduling and social posting. | **Assumed:** CoS orchestrates handoff from Chopify outputs to Postiz API endpoints. |

---

## 4. Ranked Modification Points (Minimal-Touch Principle)

Ranked from least invasive (pure adapter, zero repo modification) to most invasive (core architectural changes):

| Rank | Change Target / File Area | Proposed Modification | Blast Radius | Additive vs Invasive | CoS Lens Served | Infrastructure Blockers |
|---|---|---|---|---|---|---|
| **1** | **`adapters/cos_adapter.py`** (External Integration Layer) | **Versioned JSON CLI Adapter / MCP Tool Server:** Pure integration wrapper around `chopify.py` and `projects.py`. Exposes `chopify_prepare_clips`, `chopify_render_clips`, and `chopify_get_project_status` as standard MCP tools. Reads structured JSON directly. | Zero (Outside repo) | **Strictly Additive** | Command, Delegation, Reporting | None. Can be implemented immediately. |
| **2** | **`projects.py` & `chopify.py`** | **Structured JSON Run Summary Emitter:** Add a `--json-summary` flag to `chopify.py` and an atomic `run_summary.json` output in `projects.py` capturing start time, stage timings, clips produced, scores, and file paths. | Low (CLI flag addition) | **Additive** | Monitoring, Reporting | None. Enhances machine observability without breaking existing stdout. |
| **3** | **`dashboard.py`** | **Headless Job Management & Cancellation Endpoint:** Add `POST /api/projects/<id>/cancel` to terminate active child processes, and expose a health/readiness endpoint `GET /api/health`. | Low (`dashboard.py` only) | **Additive** | Delegation, Monitoring | None. Expands local REST capability. |
| **4** | **`shared/integrations/chopify_redis.py`** (External Bridge) | **Redis Event Publisher Bridge:** A background file-watcher or hook in `projects.py:stage()` that emits Redis pub/sub events (`marketing.chopify.job_started`, `marketing.chopify.clip_completed`) matching the OS specification. | Low | **Additive** | Monitoring, Orchestration | Blocked on active Redis container in `business-os/shared/events/`. |
| **5** | **`branding.py` & `projects.py`** | **Dynamic Shared Intelligence Connector:** Enable loading brand presets and contextual hooks directly from central PostgreSQL/Qdrant instead of local file paths. | Medium (`branding.py`) | **Additive** | Shared Intelligence, Command | Blocked on PostgreSQL + Qdrant deployment in `business-os/shared/knowledge/`. |
| **6** | **`business-os/agents/marketing/bridge/`** | **Chopify-to-Postiz Ingestion Bridge:** Automated pipeline routing completed Chopify exports (`.mp4`, `.srt`, `.meta.json`) into `postiz-app`'s upload API for immediate multi-platform post scheduling. | Medium (Multi-repo) | **Additive** | Orchestration, Reporting | Blocked on Postiz container startup and API configuration. |

### Architectural Options Summary
- **Integration-Only Option (Rank 1):** Zero modifications to `business-os/agents/marketing/chopify`. A dedicated Python adapter or MCP server wraps the existing CLI (`chopify.py --no-input`) and reads `project.json` and `selection.json`.
- **Contract-First Modification Option (Ranks 2–3):** Minimal touch additions to Chopify to emit structured JSON execution summaries and support task cancellation.
- **Enterprise Federation Option (Ranks 4–6):** Connects Chopify and Postiz to Redis, PostgreSQL, and Qdrant once the shared infrastructure layer is deployed.

