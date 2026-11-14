# Chopify Project Inspection

**Target Component:** `business-os/agents/marketing/chopify`  
**Scope:** Exhaustive inspection of source modules, tests, specifications, documentation, data contracts, and runtime architecture.

---

## 1. Self-Description and Machine-Facing Contract

Chopify documents its purpose, capabilities, and machine interfaces across a hierarchy of documentation and specification files:

1. **`README.md` (lines 1–318):** Defines Chopify as a free, open-source, local-first Python application and browser dashboard that converts long videos into scored, captioned shorts without subscriptions, cloud uploads, watermarks, or paid API keys. Last updated 2026-11-05 (`FACT`).
2. **`docs/product.json` (lines 1–32):** Provides structured machine-readable product facts. Highlights:
   - Primary platform: Windows; CI: Windows + Linux (`product.json`, line 10).
   - Input formats: MP4, MOV, MKV, WebM, M4V, AVI, and yt-dlp-supported HTTP(S) URLs (`product.json`, line 11).
   - Outputs: H.264 MP4, AAC audio, clip-relative SRT, PNG poster, and metadata JSON (`product.json`, line 12).
   - Explicit Exclusions (`product.json`, line 30): `"not_included": ["social publishing", "scheduling", "cloud collaboration", "hosted processing", "translation", "bilingual captions", "dubbing", "speaker diarization", "guaranteed virality"]`.
3. **`llms.txt` (lines 1–46):** Concise documentation index and system summary designed for LLM consumption, outlining CLI usage, local HTTP endpoints, pipeline architecture, and privacy posture (`FACT`).
4. **`docs/AGENT-API.md` (lines 1–158):** Defines developer and local agent interfaces:
   - CLI contracts for `prepare`, `render`, `all`, and batch modes.
   - Long source heuristics (>=2 hours or >=8 GB).
   - Project filesystem schema (`project.json`, `transcript.json`, `segments.json`, `candidates.json`, `selection.json`).
   - Python programmatic entry points (`projects.py`, `branding.py`, `captions.py`, `semantic.py`).
   - Local HTTP API on `127.0.0.1:8765` secured with `X-Chopify-Token`.
5. **`docs/CLI.md` (lines 1–112):** Exhaustive reference of all 46 CLI arguments, defaults, and accepted values across Input, Scoring, Captions, Output, Batch, and Diagnostics (`FACT`).
6. **`docs/WORKFLOWS.md` (lines 1–453):** Practical guide detailing Studio review workflows, local file versus batch processing, stage invalidation rules, caption editing, SRT export, split-screen setup, and brand presets.
7. **`docs/USER-DEMAND-RESEARCH.md` (lines 1–135):** Research document establishing competitor gaps (Opus Clip, Anil-matcha, ClipsAI); establishes that local execution, clip selection precision, installability preflights, and visual awareness are primary product drivers.
8. **`docs/DISCOVERABILITY.md` (lines 1–68) & `docs/TROUBLESHOOTING.md` (lines 1–69):** Detail static site deployment to GitHub Pages and remediation steps for missing ffmpeg codecs, CUDA errors, and network failures.
9. **Superpowers Plans and Design Specs (`docs/superpowers/{plans,specs}/*.md`):** Six dated implementation plans and three design specifications (dated October–November 2026) documenting the evolutionary architecture of Chopify Studio, adaptive clip discovery, caption styling, creator evidence timelines, and long-source sectioning.

---

## 2. Pipeline and Internal Orchestration

Chopify’s execution pipeline is coordinated primarily by `projects.py:run_project()` (lines 189–528) and driven by `chopify.py:main()`. The pipeline is organized into five discrete, stateful, and resumable stages.

### 2.1 Root Python Module Directory & Responsibilities

| Python Module | Lines | Primary Responsibility | Inputs | Outputs | External Services / Subprocesses |
|---|---|---|---|---|---|
| **`chopify.py`** | 371 | CLI entrypoint, argument parsing, preflight environment validation, interactive prompting, and batch dispatch. | CLI flags, arguments, `sys.stdin` | Dispatched project jobs, stdout human log | `ffmpeg -encoders` (subprocess check) |
| **`projects.py`** | 542 | Pipeline orchestrator, project lifecycle, cache invalidation, and stage execution (`run_project`, `run_batch`). | `source`, options dictionary, stage files | `project.json`, staged JSON files | Invokes sibling modules |
| **`ingest.py`** | 363 | Source probing, duration/filesize estimation, disk space verification, and discovery media downloads. | Local file path or video URL | Discovery media (`source.mp4`, audio stream), metadata dict | `ffprobe`, `yt-dlp` (subprocess) |
| **`download_and_transcribe.py`** | 369 | Full video downloading and speech-to-text transcription with word-level timestamps; chunked transcription for long sources. | Video file or URL | `transcript.json`, `transcript.partNNN.json` | `yt-dlp`, `ffmpeg`, `faster-whisper` |
| **`evidence.py`** | 570 | Audio-based creator evidence: builds 1 Hz timeline (loudness, spectral flux, transients, peaks) to score reaction/impact moments. | Mono 16 kHz audio track | `audio_features.npz` | `ffmpeg` (mono pcm extraction) |
| **`visual.py`** | 733 | Visual-based creator evidence: decodes 2 fps 160x90 frames to detect motion spikes, cuts, UI changes, and face activity. | Source video file | `visual_baseline.json`, `visual_sections/*.npz` | `ffmpeg` (frame pipe), OpenCV (`cv2`) |
| **`score_clips.py`** | 1753 | Heuristic virality scoring, multi-modal evidence fusion (text + audio + visual), duration laddering, and selection filtering. | `transcript.json`, audio/visual evidence | `candidates.json`, `selection.json`, `segments.json` | Local Ollama HTTP (`127.0.0.1:11434`) if `--llm` |
| **`semantic.py`** | 94 | Semantic transcript search using local vector embeddings. | Transcript sentences, query string | Ranked sentence indices, similarity scores | Local Ollama HTTP (`127.0.0.1:11434/api/embed`) |
| **`tighten.py`** | 133 | Filler word removal (um, uh, you know) and silence excision; computes cut plans and retimes subtitle cues. | Word timestamps, start/end bounds | Clip-relative keep ranges `[(start, end)]` | None |
| **`captions.py`** | 59 | SubRip (.srt) subtitle generation from word timestamps; transcript update validation. | Word list, clip boundaries | Formatted SRT subtitle text | None |
| **`branding.py`** | 130 | Validation and resolution of JSON brand presets, colors, fonts, margins, logos, and caption style overrides. | `brand.json` or style dictionary | Validated brand dictionary | None |
| **`render_clips.py`** | 797 | Final video rendering via ffmpeg: crops (16:9, 9:16 face-tracking, 1:1, split-screen), burns ASS subtitles, applies cuts and loudnorm. | Source media, segment bounds, style | `<clip>.mp4`, `<clip>.srt`, `<clip>.png`, `<clip>.meta.json` | `ffmpeg`, `ffprobe`, OpenCV (`cv2`), YuNet face model |
| **`sections.py`** | 211 | Section planner and downloader for long URLs: merges nearby clip ranges into padded sections (max 10 min) to avoid full downloads. | Segment list, video duration | Padded section MP4 files under `sections/` | `yt-dlp` via `ingest.py` |
| **`dashboard.py`** | 367 | Studio backend: standard-library `ThreadingHTTPServer` on `127.0.0.1:8765`, REST API, single-worker job executor, static UI hosting. | HTTP requests from Studio UI | JSON responses, media streams, dispatched CLI runs | Spawns `chopify.py` as child process |
| **`tools/build_site.py`** | 38 | Public documentation site builder: validates file allowlists, concatenates guides into `llms-full.txt`, creates `_site`. | Docs, assets, guides | Static `_site` directory | None |
| **`tools/make_social_preview.py`** | 53 | Generates OpenGraph / Twitter social preview card (`social-preview.png`). | Template assets | `assets/social-preview.png` | Pillow (`PIL`) |

---

### 2.2 End-to-End Pipeline Data Flow

```
[ Input: Local File / URL ]
             │
             ▼
   ┌───────────────────┐
   │ 1. Stage: source  │ ── ingest.py / download_and_transcribe.py
   │    Probe / Ingest │    Detects short vs long (>2h / >8GB); downloads discovery media if URL
   └───────────────────┘
             │
             ▼
   ┌───────────────────┐
   │ 2. Stage:         │ ── download_and_transcribe.py
   │    transcribe     │    faster-whisper (30-min chunks for long sources)
   │                   │    Output: transcript.json (words with [start, end])
   └───────────────────┘
             │
             ▼
   ┌───────────────────┐
   │ 3. Stage:         │ ── score_clips.py, evidence.py, visual.py
   │    discover       │    Computes 1 Hz audio timeline & 2 fps visual action arcs
   │                   │    Output: candidates.json (discovered moment windows)
   └───────────────────┘
             │
             ▼
   ┌───────────────────┐
   │ 4. Stage:         │ ── score_clips.py (optional Ollama --llm)
   │    select         │    Applies min_score (8.0+) & preferred_len; generates selection diagnostics
   │                   │    Output: selection.json & segments.json
   └───────────────────┘
             │
      [ Review Gate: Studio / CLI pause ]
             │
             ▼
   ┌───────────────────┐
   │ 5. Stage:         │ ── render_clips.py, sections.py, branding.py, tighten.py
   │    render         │    Downloads section slices (if long URL); applies crop, face-track,
   │                   │    burns ASS captions, tightens silence, exports:
   │                   │    -> <id>.mp4 (H.264 video)
   │                   │    -> <id>.srt (clip-relative subtitles)
   │                   │    -> <id>.png (poster frame)
   │                   │    -> <id>.meta.json (social title, description, tags)
   └───────────────────┘
```

### 2.3 Resumption, Invalidation, and Failure Handling
- **State Persistence:** `projects.py:save_project()` writes `project.json` atomically using temporary files (`atomic_json`, lines 33–37) to prevent corrupted state on crashes.
- **Cache Keys:** Stages cache cryptographic SHA-256 digests of their inputs (`projects.py:digest`, lines 29–30). For local files, identity combines path, file size, and modification timestamp in nanoseconds (`file_identity`, lines 44–48).
- **Partial Render Retries:** If clip rendering fails midway, successfully completed clips remain on disk, and failed clips are logged to `render_errors` in `project.json`. Calling `--action render` retries only the missing/failed clips (`projects.py`, lines 452–454).
- **Studio Interruption Recovery:** When `dashboard.py` initializes, it inspects all project directories; any project left in `queued` or `running` status is automatically updated to `interrupted` (`dashboard.py`, lines 72–79), allowing safe manual or programmatic resumption.

---

## 3. Interfaces and Contracts

### 3.1 Command-Line Interface (CLI)
- **Executable:** `python chopify.py`
- **Verified Flag Surface (46 arguments in code, 52 in `docs/CLI.md`):**
  - *Modes:* `--action all|prepare|render`, `--preview`, `--batch <path>`, `--project <path>`, `--workdir <dir>`, `--projects-dir <dir>`, `--resume/--no-resume`.
  - *Automation / Headless:* `--no-input` (suppresses interactive prompts for scripts/CI), `--no-preflight` (bypasses dependency checks), `--version`, `--list-styles`.
  - *Scoring & Selection:* `--min-score <float>`, `--preferred-len <str>`, `--min-len <int>`, `--max-len <int>`, `--max-clips <int>`, `--search <keywords>`, `--semantic <query>`, `--embed-model <name>`, `--llm <model>`, `--explain`.
  - *Captions & Styling:* `--style <preset>`, `--caption-json <path>`, `--words-per-cue <int>`, `--uppercase/--no-uppercase`, `--caption-position <pos>`, `--caption-animation <anim>`, `--caption-background <bg>`, `--caption-outline <int>`, `--caption-shadow <int>`, `--emoji/--no-emoji`, `--emphasis/--no-emphasis`, `--caption-font <str>`, `--caption-color <hex>`, `--caption-highlight <hex>`, `--caption-emphasis-color <hex>`.
  - *Video Framing & Output:* `--aspect 16:9|9:16|1:1`, `--layout single|split`, `--centers <float> <float>`, `--clips <1,3,5>`, `--out <dir>`, `--tighten`, `--loudnorm`, `--device cpu|cuda|auto`, `--whisper-model <size>`, `--brand <path>`.

### 3.2 Data Contracts
1. **`examples/batch.json`:** Plain JSON array of strings containing video paths or URLs (`["C:\\Videos\\podcast.mp4", "https://youtube.com/..."]`). Validated by `projects.py:run_batch()` (requires non-empty array of strings, max 100 entries in HTTP API).
2. **`examples/brand.json`:** JSON dictionary configuring fonts, colors, margins, logos, and caption styles. Validated by `branding.py:validate_brand()` (lines 92–130). Unknown keys or invalid hex color formats trigger actionable `ValueError` exceptions.
3. **`project.json`:** Project state contract containing `id`, `source`, `options`, `status` (`new`, `queued`, `running`, `review`, `complete`, `failed`, `interrupted`), `stage`, `created`, `updated`, `cache`, `renders`, `error`, `source_meta`, `progress`, and `render_errors`.
4. **`segments.json` / `candidates.json`:** Array of candidate objects containing `start` (float seconds), `end` (float seconds), `hook` (string), `overall` (float score 0–10), and optional `similarity` (float).

### 3.3 Dashboard Loopback HTTP API
Implemented in `dashboard.py` via Python's standard `http.server.ThreadingHTTPServer` bound to `127.0.0.1:8765`.
- **Security:** Requires `Host: 127.0.0.1:PORT` and validates `X-Chopify-Token` header for all mutating POST requests (`dashboard.py`, lines 173, 237–241).
- **Core Endpoints:**
  - `GET /api/config`: Returns process session token, defaults, brand names, and caption presets.
  - `GET /api/projects`: Lists all existing projects sorted by creation date.
  - `POST /api/projects`: Creates a new project without starting (`{"source": "...", "options": {}}`).
  - `POST /api/batch`: Creates and enqueues up to 100 sources for preparation.
  - `GET /api/projects/<id>`: Returns project state, progress, selection stats, transcript, render errors, and file lists.
  - `POST /api/projects/<id>/settings`: Updates project options and brand links.
  - `POST /api/projects/<id>/transcript`: Updates word-level transcript timestamps and words.
  - `POST /api/projects/<id>/candidates`: Overrides clip candidate intervals.
  - `POST /api/projects/<id>/run`: Enqueues an execution action (`{"action": "prepare"|"render", "preview": bool, "pick": "1,3"}`).
  - `POST /api/brands`: Creates or updates a brand preset file.
  - `GET /media/<id>/clips/<file>` & `/previews/<file>`: Serves rendered MP4, SRT, and PNG files with HTTP 206 byte-range support.

---

## 4. Boundaries, Runtime Model, and Credential Surface

1. **Process Model:** Pure local execution. The CLI runs synchronously in a single process. `dashboard.py` runs a multi-threaded HTTP server with an internal `ThreadPoolExecutor(max_workers=1)`, executing jobs serially by spawning `chopify.py` as a subprocess (`dashboard.py`, line 122).
2. **Network Exposure:** The server explicitly rejects external connections. Line 173 of `dashboard.py` asserts `Host == 127.0.0.1:PORT`, refusing remote network traffic.
3. **Storage & Multi-Tenancy:** Project storage resides on the local filesystem under `projects/<project_id>/` (or user-specified `--workdir`). No multi-tenant isolation exists; concurrent project writes to the same directory are unsafe.
4. **Credential and Secret Audit:**
   - **External API Keys:** ZERO API keys or tokens are stored, accepted, or required. Video downloads rely on public `yt-dlp` scraping; transcription runs local `faster-whisper` models; AI scoring and embeddings use local Ollama (`127.0.0.1:11434`).
   - **Internal Security Tokens:** The only token in the codebase is an ephemeral 32-byte URL-safe string generated at runtime via `secrets.token_urlsafe(32)` in `dashboard.py` (line 66) to protect against local browser CSRF.

---

## 5. Test Suite as Executable Specification

The test suite consists of 14 test modules in `tests/` executed via `pytest`:

| Test Module | Test Count | Specification / Contracts Pinned |
|---|---|---|
| **`test_chopify.py`** | 122 | Sentence splitting, word preservation, calibration anchors, duration parsing, heuristic scoring, keyword search hits. |
| **`test_caption_studio.py`** | 45 | Caption option validation, style inheritance, color format enforcement, bounding limits for fonts and margins. |
| **`test_studio.py`** | 24 | Local input bypass of download, clip-relative SRT timing, caption text rebuilding, brand validation, filter injection rejection. |
| **`test_visual.py`** | 17 | Static frame cut rejection, motion spike detection, visual feature caching round-trips, video decoding. |
| **`test_evidence.py`** | 11 | 1 Hz audio timeline generation, loudness burst isolation, spectral flux transient scoring, timeline cache serialization. |
| **`test_ingest.py`** | 11 | Long source threshold detection (2 hours / 8 GB), local file probing, URL format estimation, disk space preflight checks. |
| **`test_sections.py`** | 11 | Nearby clip merging (<=30s gap), section padding (10s), section duration cap (600s), section cache reuse. |
| **`test_project_render.py`** | 7 | Retention of successful clips on failure, style variant caching, source modification detection, section offset rendering. |
| **`test_dashboard.py`** | 6 | HTTP rejection of missing token or cross-origin headers, project creation/editing over REST, caption preset exposure, media byte-ranges, busy project lockouts. |
| **`test_chunked_transcription.py`** | 6 | 30-minute chunk boundaries, 30-second overlap deduplication, part transcript resumption, timestamp offset calculation. |
| **`test_render_integration.py`** | 6 | Full ffmpeg render integration, subtitle burn-in, brand color ASS styling, tightened video/SRT synchronization. |
| **`test_long_projects.py`** | 6 | Long URL audio-first download, speechless audio fallback to visual discovery, local file chunked transcription. |
| **`test_block_scan.py`** | 5 | 30-minute block candidate discovery, part file caching, window boundary context overlap. |
| **`test_site.py`** | 2 | Public bundle asset allowlisting, rejection of unrelated output files in site builder. |

Total: **275 automated tests** pinning the behavioral contracts of the pipeline.

---

## 6. Verified Codebase Absences (Negative Search Audit)

To confirm the architectural posture and avoid assumptions, targeted negative searches were conducted across the entire codebase (`business-os/agents/marketing/chopify`):

| Target Concept | Search Regex / Terms | Scope | Result | Concrete Finding |
|---|---|---|---|---|
| **MCP Integration** | `mcp`, `modelcontextprotocol` | All files | **0 hits** | No Model Context Protocol server or client implementation exists. |
| **Webhooks / Events** | `webhook`, `event_emitter`, `redis`, `kafka` | All files | **0 hits** | No webhook callbacks or message bus event emitters exist. |
| **Shared Intelligence** | `postgres`, `postgresql`, `qdrant`, `vector_db` | All files | **0 hits** | No integration with shared PostgreSQL or Qdrant vector databases. |
| **Web Frameworks** | `fastapi`, `flask`, `django`, `aiohttp`, `starlette` | All files | **0 hits** | No web framework dependencies; uses standard library `http.server`. |
| **Enterprise Auth / RBAC** | `oauth`, `jwt`, `api_key`, `rbac`, `user_id` | All files | **0 hits** | No enterprise authentication or role-based access control. |
| **CoS Coordination** | `chief`, `of-staff`, `orchestrat*` (external) | All files | **0 hits** | No Chief of Staff consumer or delegation handler present. |
| **Docker Infrastructure** | `Dockerfile`, `docker-compose` | Chopify root | **0 hits** | No container definition exists within the Chopify repository. |

