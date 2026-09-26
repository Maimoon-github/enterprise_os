Based on the provided architecture specifications, codebase manifests, and gap analysis, here is the essential, logically sequenced 7-task execution plan for the **Layer 5 Worker Agent implementation**, focusing on completing and aligning the **Strategy Engine (`W_STRAT`)** while maintaining the invariants of all seven worker engines.

---

### Layer 5 Worker Agent Execution Plan

| Task ID | Phase | Task Name | Description | Predecessor | Milestone | Resource / Owner |
| --- | --- | --- | --- | --- | --- | --- |
| **T1** | Phase 1: Baseline Audit & Alignment | **Audit Layer 5 Worker Boundaries & Invariants** | Inspect all 7 worker engines to verify architectural invariants and resolve cataloging discrepancies.<br>

<br>• **Sub-task 1.1**: Verify Model A mediated data access across all workers (no direct enterprise database or vector storage imports; all context delivered via IE `TaskContext` / `EvidenceEnvelope`).<br>

<br>• **Sub-task 1.2**: Reconcile sandbox naming documentation mismatches by formally standardizing on capability `s-comp` (retaining `sandbox/docker/hardened/skills/s-comp/`) rather than the outdated `S_SCRAPE`.<br>

<br>• **Sub-task 1.3**: Validate the single-specialist scope for `W_STRAT` (`subagents/allocation.py` backed by `s_alloc_core.py`), confirming that speculative sub-agents (`media_mix_modeler`, `funnel_simulator`) are not added without underlying code backing. | None | **M1: Architecture Invariants & Capability Baselines Confirmed** | Lead Systems Architect / Core Engine Engineer |
| **T2** | Phase 2: Schema Standardization | **Formalize Strategy Engine Pydantic Contracts** | Define strict data validation models to establish clear type safety and interface boundaries for `W_STRAT`.<br>

<br>• **Sub-task 2.1**: Author `backend/app/schemas/strategy.py` with Pydantic v2 schemas: `StrategyDirective`, `AllocationConstraint`, `ChannelSpendProposal`, and `StrategyResultEnvelope`.<br>

<br>• **Sub-task 2.2**: Reconcile generic models in `backend/app/schemas/agent_contracts.py` to ensure bidirectional compatibility with IE dispatch envelopes. | T1 | **M2: Strategy Contract Schemas Authored & Validated** | Backend Engineer / Schema Specialist |
| **T3** | Phase 3: Cognitive Profile Setup | **Implement Strategy Cognitive Profiles & Prompts** | Establish cognitive profile isolation and system prompt boundaries matching sibling Layer 5 workers.<br>

<br>• **Sub-task 3.1**: Create `backend/app/agents/strategy_engine/profiles.py` defining isolated system prompts, temperature bounds, token budgets, and output schemas for the allocation specialist.<br>

<br>• **Sub-task 3.2**: Enforce prompt isolation rules to prevent ambient credential leakage or ungrounded spend targets. | T2 | **M3: Strategy Cognitive Profile Configured** | LLM Engineer / Agent Architect |
| **T4** | Phase 4: Sandbox Hardening & Binding | **Configure & Verify `S_ALLOC` Sandbox Isolation** | Bind the allocation core tool to the hardened Docker execution environment and enforce security constraints.<br>

<br>• **Sub-task 4.1**: Modify `backend/app/integrations/sandbox/capabilities.py` to ensure explicit registration of capability `S_ALLOC` routing to `sandbox/docker/hardened/skills/s-alloc/scripts/run.py`.<br>

<br>• **Sub-task 4.2**: Verify that `backend/app/integrations/sandbox/s_alloc_core.py` and `sandbox_policy.py` enforce fail-closed behavior (no host-side mathematical fallback upon container error). | T1 | **M4: Sandbox `S_ALLOC` Tooling Confined & Bound** | Security Engineer / Sandbox Platform Engineer |
| **T5** | Phase 5: Worker Orchestrator Wiring | **Wire `W_STRAT` Orchestration & W3C PROV Lineage** | Implement the complete execution lifecycle in the primary worker orchestrator.<br>

<br>• **Sub-task 5.1**: Modify `backend/app/agents/strategy_engine/strategy.py` (`StrategyEngineWorkerAgent`) to receive directives from IE, invoke `AllocationSubAgent`, call the sandbox client, and construct the `StrategyResultEnvelope`.<br>

<br>• **Sub-task 5.2**: Hook execution events into `services/provenance.py` and `persistence/repositories/provenance.py`, generating W3C PROV records (`wasAssociatedWith`, `used`, `wasGeneratedBy`) with SHA-256 payload digests. | T3, T4 | **M5: Strategy Worker Orchestrator Operational with Lineage** | Backend Engineer / Distributed Systems Engineer |
| **T6** | Phase 6: Domain Test Suite Construction | **Build & Run Dedicated Strategy Test Package** | Construct a dedicated test suite under `backend/tests/strategy_engine/` mirroring sibling engine packages.<br>

<br>• **Sub-task 6.1**: Implement `test_contracts.py` (validating schema constraints) and `test_allocation.py` (unit testing mathematical allocation edge cases).<br>

<br>• **Sub-task 6.2**: Implement `test_sandbox_security.py` (asserting container isolation and zero host fallback on timeout) and `test_provenance.py` (verifying append-only W3C PROV records).<br>

<br>• **Sub-task 6.3**: Implement `test_ie_roundtrip.py` and verify regression passes across `test_strategy_integration.py` and `test_strategy_allocation_verification.py`. | T5 | **M6: Strategy Engine Test Suite Fully Passing** | QA Engineer / Test Automation Engineer |
| **T7** | Phase 7: End-to-End Governance Sign-Off | **Execute Multi-Worker Verification & Release Gate** | Certify all 7 Layer 5 worker engines against platform governance and release blockers.<br>

<br>• **Sub-task 7.1**: Validate multi-tenant isolation against PostgreSQL RLS policies (`migrations/sql/0005_tenant_rls_privileges.sql`).<br>

<br>• **Sub-task 7.2**: Audit egress network containment via `egress-proxy/tinyproxy-allowlist.conf` and seccomp filters (`worker-seccomp.json`).<br>

<br>• **Sub-task 7.3**: Enforce release gates: certify zero host execution fallback (RB-1), zero direct database imports in worker modules (RB-2), 100% W3C PROV capture (RB-3), and zero ambient credential leakage (RB-4). | T6 | **M7: Layer 5 Production Certification Complete** | Release Manager / Governance Auditor |