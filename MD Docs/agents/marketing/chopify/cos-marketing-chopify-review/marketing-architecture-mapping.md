# Marketing-Context Architecture Mapping

This document maps the seven core architectural elements of the **Local-First Federated Multi-Agent Business OS** onto the marketing domain, specifically evaluating the current codebase of `business-os/agents/marketing/chopify` against the system requirements.

---

## 1. Architectural Element Mapping Table

| # | Architecture Element | Marketing-Domain Counterpart | Candidate Code Anchors | Status | Evidence & Concrete Citations |
|---|---|---|---|---|---|
| **1** | **Chief of Staff agent** | External command & orchestration consumer | `docs/AGENT-API.md`<br>`docs/CLI.md`<br>`llms.txt`<br>`business-os/chief-of-staff/` | **ABSENT** | The CoS receptacle is documented (`docs/AGENT-API.md`, lines 1–158; `docs/CLI.md`, lines 1–112; `llms.txt`, lines 1–46). However, the CoS implementation itself is completely absent: `business-os/chief-of-staff/` contains only `.gitkeep` (`FACT`). Grep for `chief` or `of-staff` across chopify returned 0 functional hits (`business-os/agents/marketing/chopify/`). |
| **2** | **Independent specialized agents** | Marketing agent (Postiz + Chopify) | `business-os/agents/marketing/`<br>`chopify/`<br>`postiz-app/` | **EXISTS** | Chopify exists as an independent Python application (`business-os/agents/marketing/chopify/README.md`, lines 3–27). Postiz is present in the tree (`business-os/agents/marketing/postiz-app/package.json`). Chopify operates as a deterministic pipeline with optional local LLM scoring, rather than an autonomous conversational agent runtime (`FACT`). |
| **3** | **Internal orchestrators** | Chopify internal pipeline & batch sequencer | `chopify.py`<br>`projects.py`<br>`ingest.py`<br>`download_and_transcribe.py`<br>`score_clips.py`<br>`render_clips.py`<br>`sections.py`<br>`examples/batch.json` | **EXISTS** | Implemented as a staged, stateful, resumable pipeline orchestrated by `projects.py:run_project()` (lines 189–528) and CLI entry `chopify.py:main()` (lines 175–365). Pipeline transitions through `source` -> `transcribe` -> `discover` -> `select` -> `render`, with atomic state checkpoints in `project.json` (`FACT`). |
| **4** | **Individual UI per agent** | Chopify Studio & Documentation site | `assets/studio/index.html`<br>`assets/studio/app.js`<br>`assets/studio/style.css`<br>`dashboard.py`<br>`tools/build_site.py`<br>`.github/workflows/pages.yml` | **EXISTS** | Chopify Studio is implemented in `assets/studio/` (1066 lines in `app.js`) and served locally via `dashboard.py:ThreadingHTTPServer` (lines 340–345) at `127.0.0.1:8765`. Provides candidate video playback, subtitle correction, and 13-preset caption styling (`FACT`). Static docs site built via `tools/build_site.py` and deployed via `.github/workflows/pages.yml`. |
| **5** | **Integration layer (APIs, MCP, webhooks, adapters)** | Programmatic command, delegation, and reporting surfaces | `docs/AGENT-API.md`<br>`chopify.py`<br>`dashboard.py`<br>`examples/batch.json`<br>`docs/product.json` | **PARTIAL** | Non-interactive CLI interface exists (`chopify.py --no-input --batch`) and local HTTP API exists (`dashboard.py` lines 144–338 with `/api/projects`, `/api/batch`, `/api/projects/<id>/run`). However, network-accessible HTTP, Model Context Protocol (MCP), and webhooks/event push mechanisms are **ABSENT** (`FACT`: 0 hits for `mcp`, `webhook`, `fastapi`, `flask`). |
| **6** | **Shared intelligence** | Brand knowledge, product context, and cross-agent memory | `examples/brand.json`<br>`docs/product.json`<br>`business-os/shared/knowledge/`<br>`business-os/shared/events/` | **ABSENT** | Chopify consumes only local JSON files (`examples/brand.json`, `branding.py`). The central PostgreSQL + Qdrant shared layer and Redis event bus specified in `Recommended architecture.md` (lines 21–24) have no counterparts in Chopify (`business-os/shared/knowledge/.gitkeep`, `shared/events/.gitkeep` only; 0 hits for `qdrant`, `postgres`, `redis`). |
| **7** | **Controlled data access** | Authorization, RBAC, isolation, and audit trail | `dashboard.py`<br>`CONTRIBUTING.md`<br>`business-os/docker-compose.yml` | **ABSENT** | Single-user, trusted-operator local model. No user accounts, RBAC, or persistent authorization keys. `dashboard.py` implements an ephemeral in-memory token (`secrets.token_urlsafe(32)`) to prevent cross-origin browser abuse on `127.0.0.1`, but no external or role-based access control exists (`FACT`). `docker-compose.yml` is an empty stub (`services: {}`). |

---

## 2. Per-Element Realization Narrative

### 1. Chief of Staff Agent (`ABSENT`)
Chopify provides a well-documented machine-facing contract in `docs/AGENT-API.md`, `docs/CLI.md`, and `llms.txt`, but neither Chopify nor the parent workspace currently contains an active Chief of Staff agent. The directory `business-os/chief-of-staff` contains only an empty `.gitkeep` placeholder. A future CoS agent will find well-defined non-interactive CLI flags (`--no-input`, `--batch`, `--action prepare|render`) and local HTTP endpoints (`/api/projects`, `/api/projects/<id>/run`), but must manage process spawning and lifecycle externally because no daemon or supervisor agent currently commands Chopify.

### 2. Independent Specialized Agents (`EXISTS`)
Chopify realizes the independent specialized agent architecture by confining its entire scope to video processing, transcription, virality scoring, and clip rendering. It maintains zero dependencies on other business agents (such as sales, support, or finance) and preserves its own Python 3.11 environment (`requirements.txt`). Adjacent marketing capabilities (social post generation and multi-platform publishing) reside separately in `postiz-app`, preserving clean modular separation. Chopify's internal "agentness," however, is currently a deterministic heuristic and media-analysis pipeline with optional Ollama LLM reranking, rather than an autonomous planning agent loop.

### 3. Internal Orchestrators (`EXISTS`)
Chopify implements a sophisticated internal orchestrator in `projects.py:run_project()` and `chopify.py`. Rather than relying on an external workflow manager, Chopify manages a multi-stage execution lifecycle (`source` -> `transcribe` -> `discover` -> `select` -> `render`). It features automatic branching for long sources (sources >=2 hours or >=8 GB trigger chunked 30-minute transcription in `download_and_transcribe.py` and sectioned rendering in `sections.py`). State transitions, intermediate signatures, and render errors are recorded atomically in `project.json`, allowing jobs to be safely resumed or retried without duplicate computation.

### 4. Individual UI (`EXISTS`)
Chopify provides a dedicated user interface via Chopify Studio, located in `assets/studio/` (`index.html`, `app.js`, `style.css`) and served by `dashboard.py`. The UI communicates with the backend over a loopback REST API (`127.0.0.1:8765`), allowing creators to visually inspect candidate clips, play source video aligned with word timestamps, edit subtitles, and style caption overlays with live preview. In addition, `tools/build_site.py` generates a static documentation and showcase site deployed to GitHub Pages via `.github/workflows/pages.yml`.

### 5. Integration Layer (`PARTIAL`)
The integration layer is partially realized through Chopify's CLI interface and local HTTP API. A local caller can issue structured CLI commands (`chopify.py --batch batch.json --no-input`) or submit jobs to `dashboard.py` via HTTP POST (`/api/batch`, `/api/projects/<id>/run`). However, this surface is strictly local-first: `dashboard.py` explicitly rejects any `Host` header other than `127.0.0.1:PORT` (line 169) and forbids cross-origin requests. Furthermore, Model Context Protocol (MCP) servers, asynchronous webhook emitters, and enterprise event adapters are completely absent from the codebase.

### 6. Shared Intelligence (`ABSENT`)
Chopify has no connection to the target shared intelligence layer. While `Recommended architecture.md` prescribes a centralized PostgreSQL database, Qdrant vector store, and Redis event bus for cross-agent business context, Chopify relies entirely on local filesystem artifacts (`examples/brand.json`, `docs/product.json`, and local NPZ audio caches). Semantic search is performed via standalone calls to a local Ollama instance (`127.0.0.1:11434/api/embed` in `semantic.py`), with sentence embeddings cached in local JSON files rather than a centralized vector database.

### 7. Controlled Data Access (`ABSENT`)
Chopify operates under a local, single-user trust model with no enterprise access control. There are no authentication mechanisms, API keys, role-based permissions (RBAC), or multi-tenant boundaries. The only security mechanism in evidence is the generation of a random 32-byte session token (`secrets.token_urlsafe(32)`) in `dashboard.py` to guard HTTP mutations against CSRF from local browser tabs. File access is unrestricted across the host filesystem where the user has read/write permissions. `business-os/docker-compose.yml` provides no container isolation, containing only an empty service block (`services: {}`).

---

## 3. Unimplemented Marketing Agent Capabilities

As established in the capability decomposition against `Agents info.md`:
1. **Create Social Posts (Captions & Carousels in Brand Voice):** Not implemented in Chopify (`docs/product.json` lists social publishing as not included). Implemented in adjacent `postiz-app`.
2. **Schedules and Publishes (Best-Time Multi-Platform Posting):** Not implemented in Chopify. Implemented in adjacent `postiz-app`.
3. **Analyzes Metrics (Weekly Report on What Worked and What's Next):** **Completely Unimplemented in both Chopify and the active marketing repository tree.** Chopify generates internal diagnostic scores (`selection.json`), but has no connection to social media performance data, viewer engagement analytics, or automated executive brief generation.

