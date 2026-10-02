Based on the provided architecture specifications, dependency trees, and implementation requirements for **Layer 8 — Public Surfaces & Telemetry Collector**, the following is an essential, logically sequenced execution plan consolidated into **3 sequential tasks** with detailed, actionable sub-tasks.

### Layer 8 Execution Plan

| Task ID | Phase | Task Name | Description | Predecessor | Milestone | Resource / Owner |
| --- | --- | --- | --- | --- | --- | --- |
| **L8-TASK-01** | Phase 1: Baseline Architecture & Storage Foundation | **Contract Specification, Storage Migration & Security Boundary Hardening** | Establish the architectural baseline, resolve structural conflicts (D1–D9), define typed telemetry schemas, and deploy the durable persistence, gateway ingestion, and access-control foundation.<br>

<br>

<br>**Sub-tasks:**<br>

<br>• *1.1 Architectural Audit & Invariant Enforcement:* Inspect `backend/app/` call graphs and verify Model A invariants (D1, D3, D5): preserve sandbox isolation (`sandbox/` and `s-alloc` remain in Layer 6), decouple Layer 4 CMS authoring from Layer 8 delivery (D4), ensure external callers receive append-only capability, and confirm single entry points for `services/telemetry.py`, `services/telemetry_engine.py`, and `agents/strategy_engine/strategy.py` (D8, D9).<br>

<br>• *1.2 Typed Schema & Manifest Formalization:* Define discriminated record kinds (`event`, `metric_snapshot`, `operational_error`) in `app/schemas/telemetry.py`, standardized envelopes (trust classes, quality flags, provenance links, privacy retention classes), exact decimal money representations, and configuration-driven source manifests (R3, R6, R8).<br>

<br>• *1.3 Additive Storage Migration & Idempotency Constraints:* Author and apply `migrations/sql/0007_layer8_ingestion.sql` creating `telemetry_receipts`, `telemetry_work_items`, and `telemetry_collection_runs`; enforce composite relational unique constraints on `(tenant_id, source_id, source_account_id, logical_event_id, source_revision)` to guarantee cross-timestamp deduplication (E15, R6).<br>

<br>• *1.4 Ingestion Gateway, Isolation & Provenance Outbox:* Add scoped service-ingestion methods (`admit`, `claim_work`, `complete_work`) with expiring leases and fencing generations in `app/mcp/data_gateway.py` (D2, R5); configure isolated non-superuser PostgreSQL roles with RLS in `app/persistence/database.py` and `app/security/authorization_boundary.py` (E16, R4); and wire transactional provenance logging in `app/services/provenance.py` without storing raw secrets (D6, R9). | Existing Layer 2–4 and Layer 7 contracts available | **Foundational Persistence & Contract Baseline Verified:** Decisions D1–D9 codified; schemas frozen; migration `0007` applied; RLS, gateway capabilities, and deduplication constraints verified (T02–T06, T10–T11, T15). | Architecture, Backend, Persistence, Security |
| **L8-TASK-02** | Phase 2: Public Ingress & Channel Telemetry Ingestion | **Public Surface Ingress, Provider Adapters & Telemetry Engine Processing** | Build authenticated and unauthenticated public intake routes, pre-parse cryptographic verification, payload minimization, ad/social provider collection adapters, and scheduled fenced engine processing.<br>

<br>

<br>**Sub-tasks:**<br>

<br>• *2.1 Ingress API Routes & Pre-Parse Verification:* Register endpoints in `app/api/routes/telemetry.py`, `app/api/router.py`, and `app/main.py`; implement HMAC/signature verification on raw request bytes prior to JSON parsing in `app/security/cryptographic_validator.py` (E14, R4); and enforce source/tenant bindings to reject spoofing or cross-tenant contamination.<br>

<br>• *2.2 Admission Service & Surface Handoff Isolation:* In `app/services/telemetry.py`, validate schemas, scrub unauthorized PII/secrets, commit minimized envelopes atomically, and return opaque receipts (R3–R5); integrate `app/integrations/cms/client.py` with deployed release ID stamping (R2); isolate telemetry failures so production website availability is never impacted; and treat client browser purchases strictly as untrusted events.<br>

<br>• *2.3 Reporting Adapters & Quota/Cost Envelopes:* Standardize interfaces in `app/integrations/ads/base.py` and `social/base.py`; extend reporting adapters for Meta Ads (`meta.py`), Google Ads GAQL (`google.py`), TikTok Ads (`tiktok.py`), LinkedIn Ads (`linkedin.py`), Instagram Insights (`instagram.py`), X API v2 (`x.py`), TikTok Display v2 (`tiktok.py`), and YouTube Analytics (`youtube.py`); and enforce operation allowlists, technical rate limits, and authorized collection-cost budgets prior to API dispatch (E1–E13, R3, R7).<br>

<br>• *2.4 Telemetry Engine Scheduling, Fencing & Run Commits:* In `app/services/telemetry_engine.py`, build scheduled polling and work processing with lease fencing, retry backoff with jitter, cursor tracking, metric-maturity correction lookbacks, and atomic `commit_report_run` executions only upon 100% verified partition coverage (R5, R7, R8). | L8-TASK-01 | **Public Ingress & Omnichannel Ingestion Operational:** Intake endpoints authenticated; pre-parse signature checks active; ad/social adapters and fenced telemetry engine processing validated (T01–T05, T07–T09, T13). | Backend, Security, Integrations, Production / Release Owners |
| **L8-TASK-03** | Phase 3: Governed Feedback, Verification & Production Release | **Governed Feedback Loop, End-to-End Verification & Staged Rollout** | Wire Intelligence Engine context assembly to feed Learning and Strategy, enforce quality/freshness gating, execute the comprehensive test suite, and execute a controlled production rollout.<br>

<br>

<br>**Sub-tasks:**<br>

<br>• *3.1 Governed Performance Context Assembly:* Implement `build_performance_context` in `app/orchestration/intelligence_engine.py` and `context_assembly.py` to assemble cited, bounded performance context envelopes (incorporating data quality, suppression, and freshness flags) via RAG/Data Gateway for `W_LEARN` without granting direct worker database access (D1, D7, R10).<br>

<br>• *3.2 Strategy Performance Gating & Boundary Preservation:* Extend `app/schemas/strategy.py` and `app/agents/strategy_engine/strategy.py` to evaluate performance evidence, require IE context when metrics are missing/stale/suppressed, block ungrounded budget allocations, and preserve the existing `S_ALLOC` boundary in Layer 6 (R10, R11).<br>

<br>• *3.3 Automated Verification Suite Execution:* Execute tests T01–T15 across unit, integration (`test_layer8_security.py`, `test_layer8_recovery.py`), and acceptance (`test_governed_end_to_end_flow.py`) suites under real PostgreSQL/TimescaleDB environments to validate crash recovery, fencing, tenant isolation, and lineage preservation (R12–R15).<br>

<br>• *3.4 Release Gates Sign-off & Staged Deployment:* Audit Release Gates 1–5 (Evidence, Security/Durability, Data, Feedback, Operational); execute staged deployment starting with shadow comparison-only feeds; and validate operational runbooks, capacity thresholds, and rollback procedures (R14). | L8-TASK-02 | **Governed Feedback Loop Validated & Production Released:** Closed-loop evidence path active; tests T12, T14, and T15 passing; Release Gates 1–5 satisfied; operational handoff and rollback runbooks accepted. | Intelligence Engine, Learning, Strategy, Release / Operations Owners |