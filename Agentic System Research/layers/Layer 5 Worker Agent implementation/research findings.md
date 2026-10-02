# Layer 5 Worker Agent Implementation & Alignment Specification

---

## 1. Source & Inspection Inventory and Evidence Limitations

### 1.1 Source Inventory

* **Repository Trees**:
* `File Tree-backend.tree` (Enterprise OS Backend: `app/agents/`, `integrations/sandbox/`, `schemas/`, `tests/`, `services/`, `persistence/`).
* `File Tree-enterprise_os.tree` (Monorepo root: `Agentic System Research/`, `backend/`, `sandbox/`).
* `File Tree-sandbox.tree` (Dockerized Sandbox: hardened runtime configs, seccomp profiles, egress-proxy rules, skills directory).


* **Research Findings & Plans (`worker agents.zip`)**:
* `Competitor Intel Engine/` (`research findings.md`, `task plan.md`).
* `Creative & Content Engine Research/` (`research findings.md`, `task plan.md`).
* `Customer Voice Engine/` (`research findings.md`, `task plan.md`).
* `Development Engine Research/` (`research findings.md`, `task plan.md`).
* `Learning & Performance Engine/` (`research findings.md`, `task plan.md`).
* `Product-Evidence Engine/` (`Research Findings.md`, `task plan.md`).
* `Strategy Engine Research/` (`research findings.md`, `task plan.md`, `IMPLEMENTATION.md`, `strategy_engine_validated_patch.zip`).


* **Core Sandbox & Integration Artifacts**:
* `backend/app/integrations/sandbox/s_alloc_core.py`, `capabilities.py`, `client.py`, `micro_tools.py`, `sandbox_policy.py`.
* `sandbox/docker/hardened/skills/s-alloc/` (`SKILL.md`, `scripts/run.py`).
* Sandbox sibling skills: `s-attr`, `s-code`, `s-comp`, `s-copy`, `s-parse`, `s-val`.



### 1.2 Evidence Limitations & Epistemic Boundaries

* **Static vs. Runtime Evidence**: Analysis is established via static AST inspection, file manifests, and configuration trees. Live container execution and end-to-end socket calls are not executed in this environment.
* **Cache Exclusion**: Compiled artifacts (`__pycache__`, `.pyc`) were excluded from architectural consideration.
* **Research vs. Code Status**: Proposals in `Agentic System Research/` were cross-checked against `File Tree-backend.tree` and `File Tree-sandbox.tree`. A proposal is treated as unimplemented unless its presence in `backend/` or `sandbox/` is verified.

---

## 2. Seven-Worker Architecture & Alignment Matrix

| Worker Agent | Layer & Role | Primary Sub-Agents | Sandbox Capability | Host/Sandbox Core Tools | Data Access Mode | Test Location |
| --- | --- | --- | --- | --- | --- | --- |
| **`W_DEV`**<br>

<br>(Development Engine) | L5: Brand Dev & Infrastructure | `planning`, `cms_contract`, `ui_layout`, `implementation`, `verification`, `security_review`, `release_ops` | `S_CODE`<br>

<br>(Skill: `s-code`) | `ast_code_linter`, `cms_schema_validator`, `git_diff_builder` | Model A: Read-only, mediated by IE | `tests/development_engine/` (13 test files) |
| **`W_STRAT`**<br>

<br>(Strategy Engine) | L5: Marketing Strategy & Planning | `allocation` | `S_ALLOC`<br>

<br>(Skill: `s-alloc`) | `s_alloc_core.py` (`budget_allocator`, `media_mix_evaluator`) | Model A: Read-only, mediated by IE | `tests/unit/test_strategy_allocation_verification.py`, `tests/integration/test_strategy_integration.py` |
| **`W_CREAT`**<br>

<br>(Creative & Content Engine) | L5: Social & Campaign Creative | `research`, `concept`, `copy`, `visual`, `adaptation`, `quality` | `S_COPY`<br>

<br>(Skill: `s-copy`) | `s_copy_core.py` (`copy_variant_generator`, `hook_ranker`, `visual_brief_formatter`) | Model A: Read-only, mediated by IE | `tests/unit/test_creative_content_verification.py`, `tests/integration/test_creative_integration.py` |
| **`W_PROD`**<br>

<br>(Product / Evidence Engine) | L5: Product Formulation & Regulatory | `discovery`, `appraisal`, `product_lab`, `safety`, `claims`, `regulatory` | `S_VAL`<br>

<br>(Skill: `s-val`) | `s_val_core.py` (`evidence_dossier_builder`, `claim_mapper`, `regulatory_linter`) | Model A: Read-only, mediated by IE | `tests/product_evidence_engine/` (8 test files) |
| **`W_COMP`**<br>

<br>(Competitor Intel Engine) | L5: Market Intel & Benchmarking | `discovery`, `advertising`, `pricing`, `search_intel`, `positioning`, `synthesis` | `S_COMP`<br>

<br>(Skill: `s-comp`) | `ad_library_parser`, `price_tracker_tool`, `serp_intel_scraper` | Model A: Read-only, mediated by IE | `tests/competitor_intel_engine/` (11 test files) |
| **`W_VOICE`**<br>

<br>(Customer Voice Engine) | L5: VoC & Sentiment Intelligence | `discovery`, `themes`, `sentiment`, `needs_objections`, `journey`, `quality` | `S_PARSE`<br>

<br>(Skill: `s-parse`) | `s_parse_core.py` (`review_scraper_parser`, `sentiment_analyzer`, `ticket_classifier`) | Model A: Read-only, mediated by IE | `tests/customer_voice_engine/` (6 test files) |
| **`W_LEARN`**<br>

<br>(Learning & Performance Engine) | L5: Feedback Loops & Closed-Loop Attribution | `telemetry`, `attribution`, `incrementality`, `fatigue`, `decay`, `quality` | `S_ATTR`<br>

<br>(Skill: `s-attr`) | `s_attr_core.py` (`attribution_calculator`, `fatigue_detector`, `decay_curve_estimator`) | Model A: Read-only, mediated by IE | `tests/learning_performance_engine/` (7 test files) |

---

## 3. Worker & Sub-Agent Responsibility, I/O, and Access Matrices

### 3.1 Model A Data Access Invariant

* **No Direct Enterprise Database/RAG Access**: No worker or sub-agent imports or accesses `persistence/database.py`, vector repositories, or external CMS systems directly.
* **Mediated Ingestion**: Context is assembled by Layer 2 (`orchestration/context_assembly.py`) and passed via typed directives (`TaskContext`, `EvidenceEnvelope`).
* **Read-Only Scoping**: Workers operate only on memory blocks or payload slices provided inside their execution directive.

---

### 3.2 Strategy Engine (`W_STRAT`) Matrix

* **Parent Worker (`StrategyEngineWorkerAgent`)**:
* *Responsibility*: Ingests marketing directives from IE, verifies budget constraints, commands the `allocation` sub-agent, verifies outputs, envelopes findings, and emits W3C PROV events.
* *Inputs*: `SpendTargetDirective`, historical channel performance summary, brand budget bounds.
* *Outputs*: `StrategyResultEnvelope` containing validated channel budget allocations and Pareto-optimal trade-off parameters.
* *Data Access*: Read-only slice of spend targets and performance telemetry from IE.


* **Sub-Agent (`allocation.py`)**:
* *Responsibility*: Formulates mathematical allocation mandates, delegates solver execution to sandbox `s-alloc`, validates optimization outputs, and detects allocation constraint violations.
* *Inputs*: Channel list, target budget, ROAS priors, minimum/maximum channel bounds.
* *Outputs*: Channel allocation mapping, projected marginal ROAS, constraint satisfaction flags.
* *Sandbox Mandate*: Capability `s-alloc` (`run.py` invoking SLSQP / convex optimization routines).



---

### 3.3 Development Engine (`W_DEV`) Matrix

* **Parent Worker (`DevelopmentEngineWorkerAgent`)**:
* *Responsibility*: Orchestrates multi-phase implementation pipeline (Plan → Contract → Layout → Code → Verify → Security → Release).
* *Inputs*: Technical specifications, component design tokens, CMS schema models.
* *Outputs*: Verified code patch, AST lint report, CMS schema diff.


* **Sub-Agents**:
* `planning.py`: Decomposes technical tasks into phased milestones.
* `cms_contract.py`: Generates and validates CMS payload schemas.
* `ui_layout.py`: Maps component tokens to semantic templates.
* `implementation.py`: Synthesizes code diffs using isolated code models.
* `verification.py`: Executes tests, linters, and type checkers in sandbox `s-code`.
* `security_review.py`: AST static analysis for secrets and insecure calls.
* `release_ops.py`: Prepares migration scripts and deployment artifacts.
* *Sandbox Mandate*: Capability `s-code` (isolated environment running Python/Node test tools, linter scripts, and diff builders).



---

### 3.4 Creative & Content Engine (`W_CREAT`) Matrix

* **Parent Worker (`CreativeContentEngineWorkerAgent`)**:
* *Responsibility*: End-to-end creative generation pipeline under Brand Persona policy.
* *Inputs*: Creative brief, audience segment, brand voice guidelines, product claim keys.
* *Outputs*: Ranked hook sets, validated copy variants, visual briefs.


* **Sub-Agents**:
* `research.py`: Grounding brief in market cues and claims.
* `concept.py`: Angle and theme ideation.
* `copy.py`: Generating copy variants (headings, bodies, CTAs).
* `visual.py`: Art direction and asset generation framing.
* `adaptation.py`: Multi-channel format adjustments (Meta, TikTok, Email).
* `quality.py`: Tone linter, safety checks, and brand constraint validation via `s-copy`.
* *Sandbox Mandate*: Capability `s-copy` (deterministic regex filters, length checks, readability scoring).



---

### 3.5 Product / Evidence Engine (`W_PROD`) Matrix

* **Parent Worker (`ProductEvidenceEngineWorkerAgent`)**:
* *Responsibility*: Grounding all marketing claims in clinical trials and regulatory standards.
* *Inputs*: Formulation data, lab trials, target regulatory jurisdictions.
* *Outputs*: Validated claims dossier, safety clearance, regulatory risk score.


* **Sub-Agents**:
* `discovery.py`: Ingesting formula and trial metadata.
* `appraisal.py`: Methodological quality appraisal of evidence.
* `product_lab.py`: Ingredient active efficacy calculation.
* `safety.py`: Contraindication, allergen, and safe usage checks.
* `claims.py`: Mapping claims to primary evidence dossier entries.
* `regulatory.py`: Boundary evaluation against FTC/FDA rules via `s-val`.
* *Sandbox Mandate*: Capability `s-val` (verification scripts, dose calculations, safety threshold evaluations).



---

### 3.6 Competitor Intel Engine (`W_COMP`) Matrix

* **Parent Worker (`CompetitorIntelEngineWorkerAgent`)**:
* *Responsibility*: Aggregates competitive intelligence across ads, prices, SERPs, and positioning.
* *Inputs*: Competitor domain lists, market category, ad library scrape requests.
* *Outputs*: Consolidated competitor intelligence dossier, pricing shift notifications.


* **Sub-Agents**:
* `discovery.py`: Competitor domain discovery and cataloging.
* `advertising.py`: Parsing ad creative variants, messaging, and spend estimates.
* `pricing.py`: Monitoring SKU pricing and discount trajectories.
* `search_intel.py`: Organic/paid search rankings and keyword overlap.
* `positioning.py`: Value proposition matrix mapping.
* `synthesis.py`: Aggregating cross-subagent signals into an actionable digest.
* *Sandbox Mandate*: Capability `s-comp` (web scraper parsers, JSON response sanitizers; egress restricted via proxy allowlist).



---

### 3.7 Customer Voice Engine (`W_VOICE`) Matrix

* **Parent Worker (`CustomerVoiceEngineWorkerAgent`)**:
* *Responsibility*: Processes customer feedback, reviews, and support logs into structured VoC insights.
* *Inputs*: Unstructured review feeds, support tickets, survey responses.
* *Outputs*: Anonymized sentiment vectors, clustered themes, objection profiles.


* **Sub-Agents**:
* `discovery.py`: Raw feed ingestion and PII sanitization.
* `themes.py`: Semantic topic extraction and frequency clustering.
* `sentiment.py`: Aspect-based sentiment quantification.
* `needs_objections.py`: Purchase friction and customer barrier mapping.
* `journey.py`: Touchpoint attribution across pre/post-purchase stages.
* `quality.py`: Statistical validation of sample size and sentiment confidence.
* *Sandbox Mandate*: Capability `s-parse` (NLP tokenizers, PII masking routines, clustering scripts).



---

### 3.8 Learning & Performance Engine (`W_LEARN`) Matrix

* **Parent Worker (`LearningPerformanceEngineWorkerAgent`)**:
* *Responsibility*: Evaluates omnichannel performance to compute incrementality, creative decay, and attribution updates.
* *Inputs*: Conversion events, ad spend logs, attribution snapshots.
* *Outputs*: Calibrated attribution model weights, creative fatigue alerts, learning delta updates.


* **Sub-Agents**:
* `telemetry.py`: Normalizing conversion and spend metrics across platforms.
* `attribution.py`: Multi-touch and Markov attribution modeling.
* `incrementality.py`: Matched-market and geo-lift estimation.
* `fatigue.py`: Detection of creative fatigue and CTR decay velocity.
* `decay.py`: Half-life decay curve calculation for campaigns.
* `quality.py`: Convergence and variance testing on telemetry batches.
* *Sandbox Mandate*: Capability `s-attr` (NumPy/SciPy econometric routines, decay solvers).



---

## 4. Verified Execution and Handoff Flows

```text
[Layer 2: Intelligence Engine]
       │
       ▼ (1. Macro-Directive + Bounded EvidenceEnvelope)
[Layer 5: Worker Agent (e.g. W_STRAT)]
       │
       ▼ (2. Domain Sub-Task Dispatch)
[Specialist Sub-Agent (e.g. allocation.py)]
       │
       ▼ (3. Typed Mandate JSON)
[SandboxClient / capabilities.py]
       │
       ▼ (4. Hardened Execution via seccomp + egress-proxy)
[Hardened Docker Container: s-alloc/scripts/run.py]
       │
       ▼ (5. Sealed JSON / Sanitized Output Envelope)
[Specialist Sub-Agent (validation & parsing)]
       │
       ▼ (6. Sub-Agent Result Contract)
[Layer 5: Worker Agent (synthesis & consistency checks)]
       │
       ├───► [Layer 4/9: W3C PROV Registry] (wasGeneratedBy, wasAssociatedWith, used)
       ▼ (7. Validated StrategyResultEnvelope)
[Layer 2: Intelligence Engine]

```

### Flow Invariants:

1. **IE Isolation**: The Intelligence Engine does not spawn, command, or observe the sub-agents directly. Sub-agents are private to the worker agent package.
2. **Deterministic Processing**: Mathematical, scraping, code-running, and token-parsing logic must run in the sandbox container (`S_*`), never in the host Python process.
3. **Fail-Closed Execution**: If the sandbox container times out, triggers seccomp violations, or fails schema validation, the sub-agent catches the error, marks the step failed, and returns an error envelope. **Host fallback is strictly forbidden.**

---

## 5. Sandbox, Security, and Provenance Model

### 5.1 Sandbox Isolation & Execution Boundaries

* **Capability Routing**:
* `s-alloc`: Budget allocation and optimization scripts.
* `s-attr`: Attribution modeling and decay curve calculations.
* `s-code`: Compilers, AST linters, test harnesses.
* `s-comp`: Competitor data extraction, ad library DOM parsers.
* `s-copy`: Copy scoring, readability algorithms, formatting checks.
* `s-parse`: PII redaction, tokenization, review parsing.
* `s-val`: Clinical trial analysis, dosage calculators, claim linters.


* **Hardened Sandbox Defense**:
* *Seccomp Filters*: Applied via `sandbox/docker/hardened/seccomp/worker-seccomp.json` (blocking raw networking syscalls and root permissions).
* *Egress Proxy*: Outbound traffic routed through `egress-proxy/tinyproxy-allowlist.conf` against `allowed-domains.txt`.
* *Ephemeral Working Directory*: Each invocation creates an isolated `/tmp/` workspace; no cross-task state leaks.



### 5.2 W3C PROV & Immutable Audit Model

* **Lineage Semantics (W3C PROV)**:
* `Entity`: Input directives, intermediate code patches, allocation proposals, and final output envelopes.
* `Activity`: Worker execution runs, sub-agent invocations, and sandbox container executions.
* `Agent`: `W_STRAT`, `IntelligenceEngine`, `s-alloc-runner`.
* Relations emitted: `wasAssociatedWith(Activity, Agent)`, `used(Activity, Entity)`, `wasGeneratedBy(Entity, Activity)`, `wasDerivedFrom(NewEntity, OldEntity)`.


* **Integrity & Storage Mechanics**:
* Registered via `services/provenance.py` and persisted in `persistence/repositories/provenance.py`.
* SHA-256 digests recorded for all inputs, sandbox script bundles, and output envelopes.
* Audit trail is append-only with cryptographic verification (`security/cryptographic_validator.py`).



---

## 6. Architecture-vs-Code Gap Analysis

1. **Strategy Engine (`W_STRAT`) Scope**:
* *Architecture Table*: Refers to `media_mix_modeler`, `budget_allocator_tool`, `funnel_simulator`.
* *Actual Implementation*: The repository contains `backend/app/agents/strategy_engine/strategy.py` and `subagents/allocation.py`.
* *Resolution*: **Research proposal already implemented via focused design.** The existing codebase intentionally consolidated strategic allocation into `subagents/allocation.py` driven by `s_alloc_core.py`. Adding speculative agents without code backing is avoided.


2. **Sandbox Capability Naming (`s-comp` vs `S_SCRAPE`)**:
* *Architecture Table*: Calls capability `S_SCRAPE`.
* *Actual Implementation*: `sandbox/docker/hardened/skills/s-comp/` exists and is referenced across `backend/app/agents/competitor_intel_engine/`.
* *Resolution*: **Naming mismatch in documentation.** Preserve `s-comp` throughout all code and tests.


3. **Cognitive Profile Presence (`profiles.py`)**:
* *Pattern*: `competitor_intel_engine`, `customer_voice_engine`, `learning_performance_engine`, and `product_evidence_engine` each feature a `profiles.py` defining isolated sub-agent system prompts.
* *Actual Implementation*: `strategy_engine/` lacks `profiles.py`.
* *Resolution*: **Implementation gap.** Add `profiles.py` to `strategy_engine/` to standardize LLM prompt boundaries.


4. **Test Suite Layout**:
* *Pattern*: `tests/competitor_intel_engine/`, `tests/customer_voice_engine/`, `tests/development_engine/`, `tests/learning_performance_engine/`, `tests/product_evidence_engine/` exist as dedicated directories.
* *Actual Implementation*: Strategy tests reside in `tests/unit/test_strategy_allocation_verification.py` and `tests/integration/test_strategy_integration.py`.
* *Resolution*: **Packaging gap.** Create `tests/strategy_engine/` preserving existing unit/integration tests and adding contract/security coverage.



---

## 7. Exact Minimal Codebase Modification Plan

| File Path | Classification | Justification |
| --- | --- | --- |
| `backend/app/agents/strategy_engine/__init__.py` | `REUSE` | Existing module init is intact. |
| `backend/app/agents/strategy_engine/strategy.py` | `MODIFY MINIMALLY` | Ensure clean worker orchestration of `allocation.py` and provenance emission. |
| `backend/app/agents/strategy_engine/subagents/__init__.py` | `REUSE` | Existing subagents package init is intact. |
| `backend/app/agents/strategy_engine/subagents/allocation.py` | `REUSE` | Functional budget allocation specialist; already aligns with `s_alloc_core.py`. |
| `backend/app/agents/strategy_engine/profiles.py` | `ADD ONLY IF MISSING` | Establishes cognitive profile isolation and system prompts for strategy sub-agents. |
| `backend/app/schemas/strategy.py` | `ADD ONLY IF MISSING` | Provides typed Pydantic models for allocation directives, constraints, and results. |
| `backend/app/integrations/sandbox/s_alloc_core.py` | `REUSE` | Validated core micro-tool implementation. |
| `backend/app/integrations/sandbox/capabilities.py` | `MODIFY MINIMALLY` | Confirm registration of `s-alloc` capability family. |
| `sandbox/docker/hardened/skills/s-alloc/SKILL.md` | `REUSE` | Skill manifest for sandbox container. |
| `sandbox/docker/hardened/skills/s-alloc/scripts/run.py` | `REUSE` | Runner script executing convex allocation in sandbox. |
| `backend/tests/strategy_engine/__init__.py` | `ADD ONLY IF MISSING` | Test package initialization. |
| `backend/tests/strategy_engine/test_contracts.py` | `ADD ONLY IF MISSING` | Verifies Pydantic schema validation for strategy payloads. |
| `backend/tests/strategy_engine/test_allocation.py` | `ADD ONLY IF MISSING` | Unit tests for `allocation.py` sub-agent. |
| `backend/tests/strategy_engine/test_sandbox_security.py` | `ADD ONLY IF MISSING` | Verifies `s-alloc` isolation and fail-closed behavior. |
| `backend/tests/strategy_engine/test_ie_roundtrip.py` | `ADD ONLY IF MISSING` | Verifies IE directive dispatch and result aggregation. |
| `backend/tests/strategy_engine/test_provenance.py` | `ADD ONLY IF MISSING` | Validates W3C PROV records for strategic planning runs. |

---

## 8. Required Tests and Release Blockers

### 8.1 Required Test Cases

1. **Contract Enforcement**: Validate that invalid budget bounds or unknown channels in `StrategyDirective` raise `ValidationError` before sub-agent execution.
2. **Sandbox Boundary Enforcement**: Ensure `allocation.py` calls `SandboxClient` with capability `s-alloc` and rejects host-side mathematical execution.
3. **Fail-Closed Failure Handling**: Inject sandbox container timeout/error; verify worker returns an error envelope and does **not** fall back to local computation.
4. **W3C PROV Compliance**: Inspect recorded lineage in `ProvenanceRepository` after strategy execution:
* Verify `Activity` exists for `W_STRAT_Allocation`.
* Verify `Entity` exists for the input directive and resulting allocation artifact.
* Verify `wasAssociatedWith` links to `StrategyEngineWorkerAgent`.


5. **Model A Access Boundary**: Assert that no enterprise database connection or unmediated RAG search is initiated by `W_STRAT` or `allocation.py`.

### 8.2 Release Blockers

* Any host execution fallback upon sandbox error.
* Direct database or vector repository access by worker or sub-agents.
* Omission of SHA-256 payload digests in provenance entity records.
* Missing cognitive profile isolation or temperature leakages in `profiles.py`.

---

## 9. Final Strategy Engine (`W_STRAT`) File/Folder Hierarchy

```text
enterprise_os/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── strategy.py                                     [REUSE / COMPATIBILITY WRAPPER]
│   │   │   └── strategy_engine/
│   │   │       ├── __init__.py                                 [REUSE]
│   │   │       ├── strategy.py                                 [MODIFY MINIMALLY]
│   │   │       ├── profiles.py                                 [ADD ONLY IF MISSING]
│   │   │       └── subagents/
│   │   │           ├── __init__.py                             [REUSE]
│   │   │           └── allocation.py                           [REUSE]
│   │   ├── integrations/
│   │   │   └── sandbox/
│   │   │       ├── s_alloc_core.py                             [REUSE]
│   │   │       ├── capabilities.py                             [MODIFY MINIMALLY]
│   │   │       ├── client.py                                   [REUSE]
│   │   │       └── micro_tools.py                              [REUSE]
│   │   └── schemas/
│   │       ├── agent_contracts.py                              [REUSE]
│   │       └── strategy.py                                     [ADD ONLY IF MISSING]
│   └── tests/
│       ├── integration/
│       │   └── test_strategy_integration.py                    [REUSE]
│       ├── unit/
│       │   └── test_strategy_allocation_verification.py        [REUSE]
│       └── strategy_engine/                                    [ADD ONLY IF MISSING]
│           ├── __init__.py                                     [ADD ONLY IF MISSING]
│           ├── test_contracts.py                               [ADD ONLY IF MISSING]
│           ├── test_allocation.py                              [ADD ONLY IF MISSING]
│           ├── test_sandbox_security.py                        [ADD ONLY IF MISSING]
│           ├── test_ie_roundtrip.py                            [ADD ONLY IF MISSING]
│           └── test_provenance.py                              [ADD ONLY IF MISSING]
└── sandbox/
    └── docker/
        └── hardened/
            └── skills/
                └── s-alloc/
                    ├── SKILL.md                                [REUSE]
                    └── scripts/
                        └── run.py                              [REUSE]

```

---

## 10. Unresolved Items Requiring Runtime / Environment Evidence

1. **Docker Seccomp Profile Conformance for `s-alloc**`: Requires running `docker-compose.hardened.yaml` to confirm that the SLSQP solver in `run.py` does not issue syscalls blocked by `worker-seccomp.json`.
2. **PostgreSQL RLS Multi-Tenant Enforcement**: Needs live execution against `migrations/sql/0005_tenant_rls_privileges.sql` to verify that `W_STRAT` tenant IDs are strictly isolated in `provenance` and `task_state` tables.
3. **Egress-Proxy Connectivity**: Requires validating that `tinyproxy-allowlist.conf` correctly denies external access during `s-alloc` execution while allowing necessary internal IPC.
