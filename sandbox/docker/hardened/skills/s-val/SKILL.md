---
name: s-val
description: Claim, schema, evidence, and regulatory compliance validation micro-tool and specialist execution runtime for W_PROD.
---

# S_VAL: Claim, Schema & Product Evidence Specialist Runtime

Authorized Worker: `W_PROD` (Product Evidence Engine)
Permitted Roles: `discovery`, `appraisal`, `product_lab`, `safety`, `claims`, `regulatory`, and deterministic validators.
Core Tools: Compliance / schema linter, claims evaluator, study methodology appraiser, formulation & lab auditor, toxicology evaluator, regulatory rule linter.

## Permitted Specialist Operations
- **Discovery (`w_prod.discovery`)**: `research_literature`, `fetch_official_rules`, `acquire_source`, `parse_metadata`, `default`. Enforces protocol adherence, disclosure-safe queries, truthful access levels, immutable snapshots, and study-family deduplication without assigning evidence certainty.
- **Regulatory (`w_prod.regulatory`)**: `check_regulatory_rules`, `verify_statutory_requirements`, `parse_rule_context`, `default`
- **Claims (`w_prod.claims`)**: `extract_claims`, `classify_claim`, `map_claim_evidence`, `inspect_claim_imagery`, `validate_claim`, `default`
- **Appraisal (`w_prod.appraisal`)**: `appraise_evidence`, `assess_study_design`, `grade_certainty`, `default`
- **Product/Lab (`w_prod.product_lab`)**: `validate_formulation`, `audit_lab_report`, `verify_test_methods`, `default`
- **Safety (`w_prod.safety`)**: `assess_safety`, `evaluate_hazards`, `screen_adverse_signals`, `default`
- **Deterministic Validators**: `validate_claim`, `lint_compliance`, `check_schema`, `validate_product_dossier`, `assemble_dossier`, `validate_trace_bundle`, `default`

## Execution & Security Boundary
- **Egress Governance**:
  - `w_prod.discovery` & `w_prod.regulatory`: Governed egress to approved official/literature subsets ONLY when an explicit, unexpired `SandboxEgressGrant` is attached (`network_policy: allowlist`).
  - `w_prod.appraisal`, `w_prod.product_lab`, `w_prod.safety`, `w_prod.claims`, and deterministic validators: Strictly isolated with `network_policy: disabled` (DENY_ALL).
- **Prohibited Accesses**:
  - Zero direct access to Intelligence Engine (IE) state machines, RAG indices, operational databases, headless CMS, or persistent storage.
  - Zero host runtime fallback or parent process execution.
  - Zero sibling-specialist direct communication or RPC.
- **Claim Compliance Contract**:
  - Detects prohibited absolute claims (e.g., "cures", "100% guaranteed", "prevents all", "permanent elimination").
  - Enforces statutory disclaimer footnotes for quantitative and performance claims.
  - All outputs conform to PE-02 bounded `SpecialistResult` and `EvidenceEnvelope` schemas.

