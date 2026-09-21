"""Focused contract and schema verification tests for Product / Evidence Engine (PE-02).

Tests machine-validatability, cross-record semantic invariants, referential integrity,
tamper-evident hashing, unknown field rejection, and Draft 2020-12 JSON Schema generation.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.schemas.product_evidence import (
    AccessLevel,
    ClaimEvidenceEdge,
    ClaimKind,
    ClaimRecord,
    ClaimStatus,
    ConflictRecord,
    DossierValidation,
    EvidenceAssessment,
    EvidenceGap,
    EvidenceRelevance,
    EvidenceSubject,
    EvidenceType,
    ExtractedEvidence,
    FormulationEvidenceBridge,
    FreshnessStatus,
    LabValidation,
    MappingRelation,
    ProductContextRequest,
    ProductEvidencePayload,
    ProductEvidenceTask,
    ProductReviewBinding,
    RegulatoryRule,
    ResearchProtocol,
    ReviewStatus,
    RuleApplication,
    RuleApplicationResult,
    RuleForce,
    RuleStatus,
    SafetyAssessment,
    SafetyStatus,
    SearchRun,
    SourceRecord,
    SourceSnapshot,
    SpecialistResult,
    SpecialistResultStatus,
    SpecialistRole,
    SpecialistTask,
    TraceBundle,
    export_trace_bundle_json_schema,
)

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "evidence_cases.json"


def load_fixtures() -> dict:
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# Boundary Contract Tests
# ==============================================================================


def test_product_evidence_task_contract_and_hashing() -> None:
    task = ProductEvidenceTask(
        task_id="task-prod-001",
        tenant_id="tenant-derma-01",
        run_id="run-001",
        parent_grant_ref="grant-001",
        parent_grant_hash="abc123hash",
        context_version="1.0",
        context_hash="ctx456hash",
        product_version="serum-v2",
        category_hypothesis="cosmetics",
        jurisdictions=["US", "EU"],
        intended_use_or_populations=["adults", "sensitive_skin"],
        claim_asset_refs=["asset-001"],
        objectives=["validate_claims", "review_safety"],
    )
    assert task.schema_version == "1.0"
    assert len(task.jurisdictions) == 2
    digest = task.compute_hash()
    assert len(digest) == 64
    # Deterministic hashing
    assert task.compute_hash() == digest


def test_specialist_task_attenuation_and_role_bounds() -> None:
    stask = SpecialistTask(
        task_id="task-spec-001",
        tenant_id="tenant-derma-01",
        parent_task_id="task-prod-001",
        specialist_role=SpecialistRole.CLAIMS,
        operation="validate_claims",
        input_manifest=["doc-1", "doc-2"],
        profile_ref="prof-claims-v1",
        delegated_token_limit=3000,
    )
    assert stask.specialist_role == "CLAIMS"
    assert stask.delegated_token_limit == 3000

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        SpecialistTask(
            task_id="task-spec-002",
            tenant_id="tenant-derma-01",
            parent_task_id="task-prod-001",
            specialist_role=SpecialistRole.CLAIMS,
            operation="validate_claims",
            profile_ref="prof-claims-v1",
            unauthorized_extra_field="malicious_payload",  # type: ignore[call-arg]
        )


def test_specialist_result_contract() -> None:
    sresult = SpecialistResult(
        task_id="task-spec-001",
        attempt_id="1",
        tenant_id="tenant-derma-01",
        specialist_role=SpecialistRole.PRODUCT_LAB,
        operation="verify_lab_coa",
        status=SpecialistResultStatus.COMPLETED,
        typed_findings={"spec_conformance": "passed", "purity": 0.99},
        source_refs=["src-001"],
    )
    assert sresult.status == "completed"
    assert sresult.typed_findings["purity"] == 0.99


def test_product_context_request_contract() -> None:
    req = ProductContextRequest(
        request_id="req-001",
        task_id="task-prod-001",
        tenant_id="tenant-derma-01",
        specialist_role=SpecialistRole.REGULATORY,
        missing_field_or_source="CosIng inventory concentration limit",
        purpose="Confirm maximum permitted topical concentration in EU",
        affected_claim_or_question="Claim-001 safe concentration",
        minimum_scope_needed="Annex III regulatory entry",
        is_blocking=True,
        reason="Cannot establish safety without statutory ceiling",
    )
    assert req.is_blocking is True
    assert req.specialist_role == "REGULATORY"


def test_product_review_binding_defaults_and_statuses() -> None:
    binding = ProductReviewBinding(
        dossier_hash="dossierhash123",
        product_version="serum-v2",
        formula_version="form-v2.1",
        target_territory="EU",
        effective_date="2026-09-21",
        required_reviewer_role="Qualified Toxicologist & Regulatory Lead",
        review_reasons=["Material claim requires clinical trial sign-off"],
    )
    assert binding.approval_status == ReviewStatus.PENDING
    assert binding.locale == "en_US"


# ==============================================================================
# Domain Records Tests
# ==============================================================================


def test_source_record_requires_url_or_identifier() -> None:
    # Valid with identifier only
    s1 = SourceRecord(
        id="src-001",
        identifier="ISO 22716:2007",
        evidence_type=EvidenceType.STANDARD,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-001",
    )
    assert s1.identifier == "ISO 22716:2007"

    # Valid with url only
    s2 = SourceRecord(
        id="src-002",
        url="https://example.com/study",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.ABSTRACT_ONLY,
        provenance_ref="prov-002",
    )
    assert str(s2.url) == "https://example.com/study"

    # Invalid without either
    with pytest.raises(ValidationError, match="requires at least one of 'url' or 'identifier'"):
        SourceRecord(
            id="src-003",
            evidence_type=EvidenceType.LEGAL_TEXT,
            access=AccessLevel.UNAVAILABLE,
            provenance_ref="prov-003",
        )


def test_formulation_bridge_and_lab_validation_records() -> None:
    bridge = FormulationEvidenceBridge(
        bridge_id="bridge-001",
        studied_material="Pure Niacinamide API 99%",
        proposed_product="eDerma Hydro-Gel Niacinamide 5%",
        identity_comparability="match",
        concentration_comparability="mismatch",
        vehicle_comparability="unknown",
        route_comparability="match",
        exposure_comparability="match",
        duration_comparability="match",
        overall_relevance=EvidenceRelevance.BRIDGE_REQUIRED,
        scientific_rationale="API studied at 10% in aqueous solution; finished formulation delivers 5% in hydrogel.",
        limits_and_conditions=["Topical delivery requires penetration confirmation."],
        requires_expert_review=True,
    )
    assert bridge.requires_expert_review is True
    assert bridge.overall_relevance == "bridge_required"

    lab = LabValidation(
        report_id="lab-rep-101",
        issuer_lab_name="Dermatest GmbH",
        test_method="HRIPT (Human Repeated Insult Patch Test)",
        sample_or_batch_id="batch-2026-09",
        raw_results={"irritation_score": 0.0, "sensitization_rate": "0/50"},
        units="index",
        decision_rule="Zero sensitization across 50 subjects qualifies for hypoallergenic certificate.",
        validation_outcome="VALIDATED",
    )
    assert lab.validation_outcome == "VALIDATED"


# ==============================================================================
# Semantic Invariants & TraceBundle Tests (Tasks 8, 10)
# ==============================================================================


def test_valid_trace_bundle_fixture_passes() -> None:
    fixtures = load_fixtures()
    bundle_data = fixtures["valid_trace_bundle"]
    bundle = TraceBundle.model_validate(bundle_data)
    assert bundle.tenant_id == "tenant-derma-01"
    assert len(bundle.claims) == 1
    assert len(bundle.evidence) == 1
    assert len(bundle.mappings) == 1
    assert bundle.mappings[0].bridge_ref == "bridge-niacinamide-serum-01"


def test_semantic_invariant_missing_bridge_fails() -> None:
    fixtures = load_fixtures()
    invalid_data = fixtures["invalid_missing_bridge_case"]
    with pytest.raises(ValidationError, match="requires a valid 'bridge_ref'"):
        TraceBundle.model_validate(invalid_data)


def test_semantic_invariant_prohibited_claim_fails() -> None:
    fixtures = load_fixtures()
    invalid_data = fixtures["invalid_prohibited_claim_case"]
    with pytest.raises(ValidationError, match="contains prohibited pattern"):
        TraceBundle.model_validate(invalid_data)


def test_referential_integrity_unknown_source_fails() -> None:
    fixtures = load_fixtures()
    bundle_data = dict(fixtures["valid_trace_bundle"])
    # Point evidence to non-existent source
    bundle_data["evidence"] = [
        {
            "id": "ev-broken",
            "source_id": "non-existent-source-id",
            "snapshot_ref": "snap-001",
            "location": "Page 1",
            "subject": "finished_product",
            "outcome": "Outcome",
            "assessment_ref": "assess-001",
            "activity_ref": "act-001",
        }
    ]
    bundle_data["mappings"] = [
        {
            "id": "map-broken",
            "claim_id": "claim-001",
            "evidence_id": "ev-broken",
            "rule_ids": ["rule-eu-655-evidential-support"],
            "relation": "supports",
            "relevance": "direct",
            "limitations": [],
            "activity_ref": "act-001",
        }
    ]
    with pytest.raises(ValidationError, match="references unknown source 'non-existent-source-id'"):
        TraceBundle.model_validate(bundle_data)


def test_referential_integrity_unknown_claim_in_mapping_fails() -> None:
    fixtures = load_fixtures()
    bundle_data = dict(fixtures["valid_trace_bundle"])
    bundle_data["mappings"] = [
        {
            "id": "map-broken",
            "claim_id": "unknown-claim-id",
            "evidence_id": "ev-001",
            "rule_ids": ["rule-eu-655-evidential-support"],
            "relation": "supports",
            "relevance": "bridge_required",
            "bridge_ref": "bridge-01",
            "limitations": [],
            "activity_ref": "act-001",
        }
    ]
    with pytest.raises(ValidationError, match="references unknown claim 'unknown-claim-id'"):
        TraceBundle.model_validate(bundle_data)


def test_gap_unknown_affected_id_fails() -> None:
    fixtures = load_fixtures()
    bundle_data = dict(fixtures["valid_trace_bundle"])
    bundle_data["gaps"] = [
        {
            "id": "gap-broken",
            "affected_ids": ["totally-unknown-id"],
            "reason": "Missing testing",
            "blocking": True,
            "activity_ref": "act-001",
        }
    ]
    with pytest.raises(ValidationError, match="references unknown affected ID 'totally-unknown-id'"):
        TraceBundle.model_validate(bundle_data)


# ==============================================================================
# JSON Schema Export Test (Task 9)
# ==============================================================================


def test_export_trace_bundle_json_schema() -> None:
    schema = export_trace_bundle_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:enterprise-os:w-prod:trace-bundle:1.0"
    assert "properties" in schema
    assert "claims" in schema["properties"]
    assert "evidence" in schema["properties"]
    assert "sources" in schema["properties"]
    assert "mappings" in schema["properties"]
    assert "gaps" in schema["properties"]


def test_product_evidence_payload_complete_assembly() -> None:
    fixtures = load_fixtures()
    bundle = TraceBundle.model_validate(fixtures["valid_trace_bundle"])
    payload = ProductEvidencePayload(
        tenant_id="tenant-derma-01",
        product_id="prod-ederma-001",
        product_name="eDerma Barrier Serum",
        product_version="v2.0",
        trace_bundle=bundle,
        dossier_validation=DossierValidation(
            validator_version="1.0",
            reference_integrity_pass=True,
            structural_status="VALID",
        ),
    )
    assert payload.product_name == "eDerma Barrier Serum"
    assert payload.trace_bundle.tenant_id == "tenant-derma-01"
    digest = payload.compute_hash()
    assert len(digest) == 64
