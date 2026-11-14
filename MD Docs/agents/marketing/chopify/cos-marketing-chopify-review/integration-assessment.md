# Integration-Layer Assessment (Chief of Staff Lenses)

**Primary Evaluation Criterion:** The integration layer's ability to support future Chief of Staff (CoS) **command, delegation, orchestration, monitoring, and reporting**.

---

## 1. 4×5 Integration Readiness Matrix

Readiness Scale:
- **0 – Absent:** No surface found; verified by negative searches.
- **1 – Partial:** Surface exists but is not directly machine-consumable as-is (e.g. requires polling unformatted logs, lacks structured status/cancellation).
- **2 – Ready:** Documented contract, non-interactive invocation, deterministic outputs, and test coverage.
- **3 – Extensible:** Ready *and* designed for machine consumers (versioned contract, formal job model, event push, pluggable adapters).

| Channel \ CoS Lens | Command | Delegation | Orchestration | Monitoring | Reporting |
|---|---|---|---|---|---|
| **1. Documented Agent API / CLI**<br>(`chopify.py`, `docs/CLI.md`, `projects.py`, `docs/AGENT-API.md`) | **2 – Ready**<br>`chopify.py:175`<br>`test_chopify.py` | **1 – Partial**<br>`projects.py:530`<br>`test_project_render.py` | **2 – Ready**<br>`projects.py:189`<br>`test_long_projects.py` | **1 – Partial**<br>`chopify.py:201`<br>`projects.py:200` | **2 – Ready**<br>`render_clips.py:755`<br>`test_site.py` |
| **2. HTTP Service Surface**<br>(`dashboard.py`, `docs/AGENT-API.md`) | **2 – Ready**<br>`dashboard.py:250`<br>`test_dashboard.py:45` | **2 – Ready**<br>`dashboard.py:67, 108`<br>`test_dashboard.py:105` | **1 – Partial**<br>`dashboard.py:103`<br>`test_dashboard.py:118` | **1 – Partial**<br>`dashboard.py:50, 128`<br>`test_dashboard.py:51` | **2 – Ready**<br>`dashboard.py:28, 207`<br>`test_dashboard.py:51` |
| **3. Webhooks / Events**<br>(No broker or webhook handlers) | **0 – Absent**<br>0 hits for `webhook`<br>0 hits for `redis` | **0 – Absent**<br>0 hits for `event_emitter`<br>0 hits for `kafka` | **0 – Absent**<br>0 hits for `pubsub`<br>0 hits for `mq` | **0 – Absent**<br>0 hits for `notify`<br>0 hits for `callback` | **0 – Absent**<br>0 hits for `telemetry`<br>0 hits for `webhook` |
| **4. Model Context Protocol (MCP)**<br>(No MCP tools or server) | **0 – Absent**<br>0 hits for `mcp`<br>0 hits for `tool_call` | **0 – Absent**<br>0 hits for `mcp_server`<br>0 hits for `call_tool` | **0 – Absent**<br>0 hits for `list_tools`<br>0 hits for `mcp` | **0 – Absent**<br>0 hits for `mcp/events`<br>0 hits for `logging/mcp` | **0 – Absent**<br>0 hits for `mcp/report`<br>0 hits for `mcp` |

---

## 2. In-Depth Evaluation Across the Five CoS Lenses

### 2.1 Command (Issue and Authorize Actions)
- **CLI / Agent API (Rating: 2 – Ready):**
  - *Capability:* A CoS can command Chopify non-interactively using `python chopify.py <source> --no-input` or `python chopify.py --batch batch.json --no-input` (`chopify.py`, lines 214, 272).
  - *Validation & Error Handling:* Options are strictly validated by `projects.py:validate_options()` (lines 50–96) and caption parameters by `branding.py:validate_caption()`. Out-of-bounds parameters raise explicit `ValueError` messages.
  - *Dry-Run & Human Steps:* The pipeline can be split into `--action prepare` (discovers candidates without rendering) and `--action render` (executes renders), enabling a CoS to programmatically review candidates before spending compute on rendering.
- **HTTP Service Surface (Rating: 2 – Ready):**
  - *Capability:* The CoS can create and trigger jobs via `POST /api/projects` and `POST /api/projects/<id>/run` (`dashboard.py`, lines 252, 293).
  - *Authorization:* Requires fetching the ephemeral token via `GET /api/config` and supplying `X-Chopify-Token`. Calls with invalid tokens or external Host headers are rejected with 403 Forbidden (`test_dashboard.py`, lines 37–43).
- **Webhooks & MCP (Rating: 0 – Absent):**
  - No remote command hooks or MCP tool declarations exist in the codebase.

### 2.2 Delegation (Hand Off Task and Track Status)
- **CLI / Agent API (Rating: 1 – Partial):**
  - *Capability:* CLI invocations are synchronous and blocking. The calling process must remain attached until the render completes or fails.
  - *Batch Delegation:* Batch execution via `chopify.py --batch batch.json` iterates sequentially through sources. If one video fails, remaining sources still execute, but the CLI exits with a non-zero code (`chopify.py`, line 282), leaving the caller to inspect project folders to identify which jobs failed.
  - *Cancellation:* The CLI has no graceful cancellation command other than sending `SIGINT` (Ctrl+C), which immediately aborts execution.
- **HTTP Service Surface (Rating: 2 – Ready):**
  - *Capability:* Asynchronous task delegation is implemented via `dashboard.py:Studio` using `ThreadPoolExecutor(max_workers=1)` (line 67).
  - *Status Polling:* Submitting a run (`POST /api/projects/<id>/run`) returns immediately with `{ "ok": true }` while the job executes in the background. The caller can poll `GET /api/projects/<id>` to monitor `project.status` (`queued`, `running`, `review`, `complete`, `failed`, `interrupted`) and `busy` state (`dashboard.py`, line 211).
  - *Limitation:* The server does not support explicit cancellation of an active worker thread/subprocess over HTTP.

### 2.3 Orchestration (Multi-Step, Idempotent, Resumable)
- **CLI / Agent API (Rating: 2 – Ready):**
  - *Capability:* Stages are fully decoupled and idempotent. `projects.py:run_project()` supports `--action prepare` (download, transcribe, discover, select) followed by selective rendering via `--clips 1,3` or `--preview`.
  - *Resumption & Idempotence:* Cache digests (`cache.source`, `cache.transcript`, `cache.discovery`, `cache.selection`, `cache.renders`) ensure that unchanged stages are bypassed automatically (`projects.py`, lines 225, 290, 358, 373, 452).
  - *Fault Tolerance:* If a 2-hour video crashes during clip render #4, clips #1–3 remain intact, and repeating the command resumes directly at clip #4 without re-downloading or re-transcribing (`test_project_render.py`, lines 9–19).
- **HTTP Service Surface (Rating: 1 – Partial):**
  - *Capability:* Exposes individual step endpoints (`/settings`, `/transcript`, `/candidates`, `/run`), but does not expose a high-level workflow orchestrator.
  - *Concurrency Lock:* The single-thread executor rejects concurrent runs on busy projects with 400 Bad Request (`test_dashboard.py`, lines 105–120).

### 2.4 Monitoring (Events, State Changes, Health)
- **CLI / Agent API (Rating: 1 – Partial):**
  - *Capability:* Progress is printed to standard stdout/stderr as plain human-readable text (`[<id>] transcribe`, `[<id>] render 1/5`).
  - *State Output:* No structured JSON event stream or machine-parseable progress bar is emitted to stdout.
- **HTTP Service Surface (Rating: 1 – Partial):**
  - *Capability:* `GET /api/projects/<id>` exposes `project.progress` containing `{ "stage": "transcribe", "done": 1, "total": 4, "detail": "chunk 1/4" }` and tail logs from `job.log` (`dashboard.py`, lines 40–43).
  - *Limitation:* Monitoring requires active polling. No Server-Sent Events (SSE), WebSockets, or streaming push endpoints exist.
- **Webhooks & MCP (Rating: 0 – Absent):**
  - Zero event dispatching. The target Redis event bus from `Recommended architecture.md` has no publisher or subscriber in Chopify.

### 2.5 Reporting (Results, Metrics, and Audit)
- **CLI / Agent API (Rating: 2 – Ready):**
  - *Artifact Outputs:* For every successful clip, Chopify outputs a complete media bundle:
    - `<clip>.mp4`: H.264 video with burned-in ASS captions.
    - `<clip>.srt`: Clip-relative SubRip subtitles.
    - `<clip>.png`: Cover poster frame.
    - `<clip>.meta.json`: Machine-readable metadata containing title, virality score, description, and hashtags (`render_clips.py`, line 755).
  - *Diagnostics:* `selection.json` contains quantitative candidate statistics (`passing_count`, `score_min`, `score_max`, `score_mean`, `threshold`).
  - *Gap:* Zero audience metrics or social performance reporting (belongs to Postiz/CoS scorecard).
- **HTTP Service Surface (Rating: 2 – Ready):**
  - *Capability:* `GET /api/projects/<id>` returns complete structured data including candidate arrays, transcript words, selection statistics, and output file URLs (`/media/<id>/clips/...`).

---

## 3. Top-5 Findings Most Critical to Chief of Staff Feasibility

1. **Local-First Process Isolation (Finding F1 - High Impact):**
   Chopify is strictly a local Python process and loopback service (`127.0.0.1:8765`). It has no network exposure, CORS support, or containerized entrypoint. To command Chopify, the CoS must either execute on the same host filesystem (spawning CLI subprocesses) or interact through a co-located lightweight adapter.
2. **Serial Execution Bottleneck (Finding F2 - Medium Impact):**
   `dashboard.py` uses a single-worker queue (`ThreadPoolExecutor(max_workers=1)`) to avoid GPU/CPU encoder thrashing. The CoS cannot execute parallel clip pipelines across multiple projects concurrently without spawning separate isolated worker instances with unique project directories.
3. **Structured File Contracts Compensate for Missing Network Protocol (Finding F3 - Positive):**
   Chopify's file-based contract (`project.json`, `selection.json`, `candidates.json`, and `.meta.json`) is exceptionally well-structured, deterministic, and atomic. A CoS agent can reliably orchestrate multi-step pipelines simply by reading and manipulating these JSON files.
4. **Absence of Webhook / Push Event Architecture (Finding F4 - Medium Impact):**
   Video downloading, chunked transcription, and ffmpeg rendering are compute-heavy operations that can take minutes to hours. Without webhooks or Redis event emission, the CoS must rely on polling `project.json` or HTTP endpoints to detect job completion.
5. **Clear Separation of Concerns between Chopify and Postiz (Finding F5 - High Impact):**
   Chopify provides zero social publishing or distribution capabilities (by explicit design, `docs/product.json`). The CoS cannot treat Chopify as the sole Marketing Agent; the CoS must orchestrate a handoff where Chopify generates clips and metadata, and `postiz-app` ingests those artifacts for scheduling and publishing.

