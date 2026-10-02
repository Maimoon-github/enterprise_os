Based on the currently available Creative Engine attachment, this is the **essential implementation plan**, compressed into **7 sequential tasks** while preserving the intended architecture and minimal-change approach.

| Task ID | Phase                     | Task Name                                                  | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Predecessor | Milestone                                                                              | Resource / Owner                 |
| ------- | ------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- | -------------------------------------------------------------------------------------- | -------------------------------- |
| **T1**  | Foundation                | **Define Creative Contracts & Boundaries**                 | Establish typed contracts for `CreativePlan`, `ResearchBrief`, `PlatformSpecSnapshot`, `ConceptPack`, `CopyPack`, `VisualPack`, `AdaptedCreativePack`, and `QAReport`. Add immutable lineage fields: tenant/task/run/attempt IDs, hashes, evidence refs, model/tool refs. Update `agents/base.py` minimally so `W_CREAT` can have `capability=None`. **Subtasks:** scope enforcement; evidence fail-closed rules; approved-channel constraints; artifact envelope/schema updates.                                                                 | —           | **Creative contracts and zero-sandbox W_CREAT boundary defined**                       | Backend / Agent Architecture     |
| **T2**  | Coordinator               | **Refactor `W_CREAT`**                                     | Modify `creative_content_engine/creative_content.py` so `W_CREAT` performs only task validation, Creative planning, deterministic scope checks, workflow invocation, and final packaging. Remove direct `S_COPY` / `SandboxClient` execution. After QA `PASS`, W_CREAT may package/select approved artifacts but must not rewrite them.                                                                                                                                                                                                           | T1          | **W_CREAT operates as LLM coordinator with zero sandbox capability**                   | Creative Engine / Backend        |
| **T3**  | Specialist Layer          | **Implement Creative Sub-Agents**                          | Add `research.py`, `concept.py`, `copy.py`, `visual.py`, `adaptation.py`, and `quality.py`. Each specialist receives its own purpose-scoped LLM identity/context, typed I/O contract, sandbox mandate, fixed tool allowlist, and provenance identity. **Subtasks:** RESEARCH → public reference/spec gathering; CONCEPT → territories/angles; COPY → variants; VISUAL → art direction/storyboards; ADAPT → placement/channel variants; QA → independent `PASS / REVISE / BLOCK`.                                                                  | T2          | **Six isolated Creative specialists implemented**                                      | AI/Agent Engineering             |
| **T4**  | Orchestration             | **Build Deterministic Creative Workflow**                  | Add `creative_content_workflow.py` implementing the fixed DAG: `RESEARCH → CONCEPT → [COPY ∥ VISUAL] → ADAPT → QA`. Only COPY and VISUAL may run in predefined parallelism. Add static QA revision routes and bounded `max_revision_attempts`; workflow structure must never be redesigned by an LLM.                                                                                                                                                                                                                                             | T3          | **Deterministic Creative pipeline executable end-to-end**                              | Orchestration / Backend          |
| **T5**  | Security & Execution      | **Enforce Specialist Sandbox Policies**                    | Modify `sandbox/capabilities.py`, `client.py`, and `sandbox_policy.py`. Deny sandbox access to `W_CREAT`; authorize only known `CREAT-*` identities. Provision a fresh AIO sandbox per `(task_id, specialist_id, stage_attempt_id)`. Set `CREAT-RESEARCH` to allowlisted proxy egress only; all other specialists use `DENY_ALL`. No backend-process fallback when AIO fails. **Subtasks:** identity-bound authorization; ephemeral execution; credential stripping; sealed inputs/outputs; sandbox teardown; research anti-SSRF/egress controls. | T4          | **Least-privilege AIO execution and network isolation enforced**                       | Security / Sandbox Platform      |
| **T6**  | Shared Utilities & Wiring | **Refactor Creative Tools, `S_COPY`, and LLM Composition** | Convert `S_COPY` from monolithic Creative generation into deterministic utilities only: schema checks, claim refs, character limits, channel scope, prohibited terms, aspect ratios, safe-zone metadata, format validation, deduplication, citation validation, hashing. Reuse `integrations/llm/client.py` and create separate identities for W_CREAT + six specialists in `main.py`. Keep all provider credentials outside sandboxes.                                                                                                           | T5          | **Creative generation separated from deterministic tooling; all LLM identities wired** | Backend / LLM Platform / Sandbox |
| **T7**  | Validation                | **Integrate, Test & Prove Architecture**                   | Extend unit/integration tests for the complete design. Verify: W_CREAT sandbox denial; specialist sandbox access; separate LLM identities; Model-A/IE-only enterprise data access; fixed workflow order; COPY/VISUAL parallelism; research-only egress; unsupported-channel rejection; missing-evidence fail-closed behavior; QA immutability; no post-QA rewrite; provenance completeness; no autonomous publishing; `IE → HITL → Outbound MCP` enforcement.                                                                                     | T6          | **Creative Engine passes architectural, security, workflow, and acceptance tests**     | QA / Backend / Security          |

### Final implementation sequence

```text
T1  Contracts & Boundaries
 ↓
T2  W_CREAT Refactor
 ↓
T3  Six Creative Specialists
 ↓
T4  Deterministic Workflow
 ↓
T5  Sandbox & Security Enforcement
 ↓
T6  Microtools + S_COPY Refactor + LLM Wiring
 ↓
T7  Integration & Acceptance Testing
```

The resulting implementation keeps the intended responsibility split:

```text
W_CREAT
  = plan + orchestrate + synthesize/package
  ≠ sandbox execution

CREAT-*
  = purpose-scoped LLM + fresh AIO sandbox

IE
  = exclusive enterprise/RAG broker

QA
  = independent evaluator, not rewriter

Publishing
  = IE → HITL → Outbound MCP
```
