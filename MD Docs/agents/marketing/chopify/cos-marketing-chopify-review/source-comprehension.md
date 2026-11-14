# Source Comprehension: Agents Info & Recommended Architecture

This document establishes the normative baseline for the Marketing Agent and its integration with the Chief of Staff (CoS) agent within the **Local-First Federated Multi-Agent Business OS**, based on `MD Docs/Agents info.md` and `MD Docs/Recommended architecture.md`.

---

## 1. Architectural Element Extraction & Verbatim Baseline

The target architecture defines seven foundational elements across five layers. Below is the mapping and exact quotation of the normative requirements governing each element.

| # | Architecture Element | Target Architecture Intent & Verbatim Citation | Marketing-Domain Counterpart & Meaning |
|---|---|---|---|
| **1** | **Chief of Staff (CoS) Agent** | *"Chief of Staff: Command, delegation, orchestration, monitoring and reporting"* (`Recommended architecture.md`, Layer Table)<br>*"chief of staff agent (for a brand) which `runs your other agents, briefs you daily`... Delegate to agents: Routes work to marketing, sales, and finance... Builds your scorecard"* (`Agents info.md`, lines 1–12) | Central command consumer that issues video processing tasks, monitors long-running clipping/transcription progress, and consumes clip metadata for scorecard KPIs. |
| **2** | **Independent Specialized Agents** | *"Independent agents: Specialized execution, internal orchestrators and individual UIs"* (`Recommended architecture.md`, Layer Table)<br>*"Agents don't need to know each other... Keep each agent kept as its own repository and environment... preserving each agent's native language"* (`Recommended architecture.md`, lines 42–66) | Marketing agent autonomous scope: Postiz + Chopify (`Recommended architecture.md`, line 13). Operates without knowledge of sales, finance, support, or reputation agents. |
| **3** | **Internal Orchestrators** | *"Each application retains its own environment, database, UI and internal orchestration"* (`Recommended architecture.md`, line 64) | Chopify's internal pipeline execution engine: sequences source download, transcription, multi-modal discovery, scoring, and ffmpeg clip rendering. |
| **4** | **Individual UI per Agent** | *"Specialized execution, internal orchestrators and individual UIs"* (`Recommended architecture.md`, Layer Table)<br>*"Keep a Next.js dashboard for unified visibility, while preserving each agent's native language"* (`Recommended architecture.md`, lines 64–66) | Chopify Studio (`assets/studio/index.html`, `app.js`): loopback browser interface for reviewing candidates, adjusting clip boundaries, styling captions, and previewing drafts. |
| **5** | **Integration Layer** | *"Integration layer: APIs, MCP, webhooks and adapters for communication"* (`Recommended architecture.md`, Layer Table)<br>*"Build the Chief of Staff as a Python orchestrator that delegates via APIs, MCP, or lightweight adapters"* (`Recommended architecture.md`, line 66)<br>*"Exposes capabilities only via API / MCP / webhook / adapter"* (`business-os/agents/marketing/README.md`, line 4) | The programmatic interface through which the CoS commands Chopify non-interactively, delegates batch jobs, polls status, and receives run completions. |
| **6** | **Shared Intelligence** | *"Shared intelligence: Central knowledge, business context, RAG and controlled data access... PostgreSQL + Qdrant: Shared business data and knowledge... Add a shared knowledge layer using PostgreSQL plus Qdrant, and an event bus like Redis for state sync"* (`Recommended architecture.md`, lines 37, 61–66) | Central repository for brand voice guidelines, product catalog knowledge, visual brand assets, and cross-agent execution context. |
| **7** | **Controlled Data Access** | *"Shared intelligence: Central knowledge, business context, RAG and controlled data access"* (`Recommended architecture.md`, Layer Table)<br>*"Deploy with Docker Compose to keep services isolated, connected through the orchestrator and shared knowledge layer, without losing autonomy"* (`Recommended architecture.md`, line 66) | Permission boundaries, local filesystem security, API authentication, and sandboxing ensuring CoS commands and asset access cannot corrupt or expose host resources. |

---

## 2. Marketing Agent Capability Decomposition

`Agents info.md` (lines 16–28) defines the Marketing Agent as an entity that:
> *"Creates posts, edits videos, tracks metrics"*

Below is the decomposition into its four normative capabilities and their mapping to concrete codebase components:

| # | Normative Capability | Specification Definition (`Agents info.md`) | Implementing Component in Repo | Status & Evidence |
|---|---|---|---|---|
| **C1** | **Create social posts** | *"Captions and carousels in your brand voice."* | `business-os/agents/marketing/postiz-app` | **EXTERNAL TO CHOPIFY** (`FACT`). Not implemented in Chopify. Postiz repository exists in `business-os/agents/marketing/postiz-app` to handle post creation and social drafting. |
| **C2** | **Edit short form videos** | *"Cut long videos into captioned reels."* | `business-os/agents/marketing/chopify` | **IMPLEMENTED** (`FACT`). Implemented end-to-end in Chopify (`chopify.py`, `projects.py`, `score_clips.py`, `render_clips.py`, `captions.py`). |
| **C3** | **Schedules and publishes** | *"Posts at your best time on every platform."* | `business-os/agents/marketing/postiz-app` | **EXTERNAL TO CHOPIFY** (`FACT`). Explicitly excluded from Chopify: `docs/product.json` line 30 lists `"not_included": ["social publishing", "scheduling", ...]`. Managed by Postiz. |
| **C4** | **Analyzes metrics** | *"Weekly report on what worked and what's next."* | **NO IMPLEMENTING COMPONENT** (Partial diagnostic only) | **UNIMPLEMENTED / OPEN** (`FACT`). Chopify generates candidate virality scores and selection diagnostics (`selection.json`, `score_clips.py`), but has no social audience analytics, engagement tracking, or weekly reporting mechanism. |

### Capability Reconciliation Summary
- **Implemented in Chopify:** C2 (*Edit short form videos*).
- **Implemented in Postiz (adjacent marketing agent component):** C1 (*Create social posts*), C3 (*Schedules and publishes*).
- **Unimplemented in Marketing Agent tree:** C4 (*Analyzes metrics / weekly report*). This requires an analytics adapter pulling post-performance metrics from social platforms (via Postiz or platform APIs) into the CoS scorecard.

---

## 3. Source Discrepancies and Open Ambiguities (`OPEN`)

1. **Terminology Normalization (`OPEN` - Resolved as Typo):**
   - The user task references "marketing-chopigy".
   - The verified repository and all project documents name the project **Chopify** (`business-os/agents/marketing/chopify/README.md`, line 3).
   - *Resolution:* "Chopigy" is treated as a typographical error for Chopify. No separate project is fabricated.

2. **Presence of Postiz (`OPEN` - Verified in Environment):**
   - The requester's pre-survey stated: *"the sole project in the tree is chopify/ (plus README.md, .gitkeep at the agent root)... verified absences at tree level: no postiz component"*.
   - **Inspection Discovery:** `ls -la business-os/agents/marketing/` revealed that `postiz-app/` **is present** in the directory (`FACT`, directory size 1748 KB, full TypeScript/Next.js/Docker structure).
   - *Resolution:* In accordance with the prompt's scope fence, Postiz's presence is verified and recorded, but Postiz is not reviewed in depth. Chopify remains the primary review target.

3. **Agent Taxonomy Mismatches between Specifications (`OPEN`):**
   - `Agents info.md` (lines 121–133) specifies a **"Reviews agent"** (*"Gets 5 star reviews, replies to every one"*).
   - `Recommended architecture.md` (lines 20, 53) maps this role to `agents/reputation/` using **OpenGMB**.
   - `Agents info.md` lacks an explicit split for "research" workflows, whereas `Recommended architecture.md` allocates `agents/research/` (*Compete + GPT Researcher*).
   - *Resolution:* Preserved as open architectural discrepancies requiring CoS orchestration alignment.

---

## 4. Chopify vs. Marketing Agent Reconciliation Paragraph

Within the target "Local-First Federated Multi-Agent Business OS," **Chopify fulfills exactly one specialized sub-domain of the Marketing Agent: the autonomous ingestion, transcription, multi-modal moment discovery, and styled rendering of short-form video clips (Capability C2).** Chopify is designed as a local-first Python engine and interactive review studio that produces production-ready video files (`.mp4`), clip-relative subtitles (`.srt`), cover posters (`.png`), and metadata summaries (`.meta.json`). It does not purport to be a complete marketing agent on its own; it deliberately omits social publishing, scheduling, multi-platform audience engagement, and post-distribution metrics analysis (explicitly listed as `"not_included"` in `docs/product.json`). To fulfill the end-to-end Marketing Agent specification described in `Agents info.md`, Chopify must operate alongside `postiz-app` (which owns multi-channel post generation, scheduling, and publishing) under the coordination of the Chief of Staff, while social analytics and weekly reporting must either be implemented within an analytics bridge or synthesized directly by the Chief of Staff scorecard.

