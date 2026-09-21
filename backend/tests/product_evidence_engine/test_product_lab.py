"""PE-05: Formulation and Laboratory Audit Specialist Tests.

Verifies:
1. ProductSpecification handling for version, material identity, concentration/unit/basis,
   supplier/spec refs, process/packaging/intended-use context, and explicit statuses (supplied, normalized, proposed, missing).
2. Deterministic measurement normalization retaining original value/unit, conversion formula,
   assumptions, precision, and uncertainty.
3. Density-dependent conversions requiring supplied positive density; failing closed when absent.
4. Non-detect and LOD/LOQ preservation; non-detect is NEVER treated as zero.
5. FormulationEvidenceBridge across 10 comparability dimensions (identity, concentration,
   vehicle, route, exposure, population, duration, endpoint, manufacturing, packaging).
6. Prohibition of ingredient evidence transfer to finished product without an explicit bridge.
7. Preservation of changed supplier extract, concentration, vehicle, process, formula, and batch.
8. LabValidation audit for report/version/hash, lab identity, sample/batch linkage, method/version,
   dates, chain of custody, analyte/endpoints, LOD/LOQ, uncertainty, limit source, and decision rules.
9. Rejection of report validation based on visual appearance (signatures/logos) alone.
10. Accreditation verification tied to valid scope and dates; out-of-scope accreditation rejected.
11. Comparison against limits only when limit source, unit/basis, batch, and decision rule are established.
12. Strict Model-A offline isolation (network_policy: DISABLED); zero direct DB, CMS, RAG, or parent runtime access.
13. S_VAL dispatch and structured result formatting conforming to PE-02/PE-05 contracts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib.util
import json
from pathlib import Path
from typing import Any
import pytest

from app.agents.product_evidence_engine.product_evidence import PRODUCT_LAB_PROFILE
from app.agents.product_evidence_engine.subagents.product_lab import ProductLabAgent
from app.core.exceptions import SandboxInvocationError
from app.integrations.sandbox.capabilities import (
    PRODUCT_SPECIALIST_POLICIES,
    validate_capability_access,
)
from app.schemas.agent_contracts import ProductSpecification
from app.schemas.governance import WorkerRole
from app.schemas.product_evidence import (
    EvidenceRelevance,
    FormulationEvidenceBridge,
    LabValidation,
    NormalizedMeasurement,
    ProductEvidenceTask,
    SpecialistResult,
    SpecialistResultStatus,
    SpecialistRole,
    SpecialistTask,
)
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxInvocationMandate,
)


@pytest.fixture
def evidence_fixture_data() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "fixtures" / "evidence_cases.json"
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def lab_case_data(evidence_fixture_data: dict[str, Any]) -> dict[str, Any]:
    return evidence_fixture_data["product_lab_case"]


@pytest.fixture
def product_lab_agent() -> ProductLabAgent:
    return ProductLabAgent()


@pytest.fixture
def parent_task() -> ProductEvidenceTask:
    return ProductEvidenceTask(
        task_id="pe-task-lab-001",
        tenant_id="tenant-derma-01",
        run_id="run-lab-001",
        parent_grant_ref="grant-derma-001",
        parent_grant_hash="hash-derma-001",
        context_version="1.0",
        context_hash="ctx-lab-001",
        product_version="2.0",
        allowed_s_val_operations=["validate_formulation", "audit_lab_report", "verify_test_methods"],
        budget_limit_tokens=8000,
        deadline_utc=datetime.now(UTC) + timedelta(hours=2),
    )


def _load_run_s_val():
    root = Path(__file__).resolve().parents[3]
    script_path = root / "sandbox" / "docker" / "hardened" / "skills" / "s-val" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("s_val_run", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_s_val


# ==============================================================================
# 1. ProductSpecification Handling (Task 3)
# ==============================================================================


def test_product_specification_completeness_and_status(
    product_lab_agent: ProductLabAgent, lab_case_data: dict[str, Any]
) -> None:
    """ProductSpecification captures version, ingredients with explicit status, and context."""
    spec_data = lab_case_data["product_specification"]
    spec = product_lab_agent.build_product_specification(
        product_id=spec_data["product_id"],
        product_name=spec_data["product_name"],
        tenant_id=spec_data["tenant_id"],
        formulation_id=spec_data["formulation_id"],
        version=spec_data["version"],
        ingredients=spec_data["ingredients"],
        process_context=spec_data["process_context"],
        packaging_context=spec_data["packaging_context"],
        intended_use_context=spec_data["intended_use_context"],
    )

    assert isinstance(spec, ProductSpecification)
    assert spec.product_id == "prod-derma-serum-v2"
    assert spec.version == "2.0"
    assert spec.validation_status == "VALIDATED"
    assert len(spec.ingredients) == 3
    assert spec.ingredients[0]["material_identity"] == "Niacinamide (USP Grade)"
    assert spec.ingredients[0]["status"] == "supplied"
    assert spec.ingredients[0]["concentration"] == 5.0
    assert spec.ingredients[0]["composition_basis"] == "w/w"
    assert spec.normalized_attributes["process_context"] == spec_data["process_context"]
    assert spec.normalized_attributes["packaging_context"] == spec_data["packaging_context"]
    assert len(spec.missing_attributes) == 0


def test_product_specification_missing_attributes_marked(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Missing context or missing ingredient concentrations are explicitly surfaced and flagged."""
    spec = product_lab_agent.build_product_specification(
        product_id="prod-incomplete",
        product_name="Incomplete Serum",
        tenant_id="tenant-derma-01",
        ingredients=[
            {"material_identity": "Active A", "concentration": None, "status": "missing"},
            {"material_identity": "", "concentration": 2.0},  # Empty identity
        ],
        process_context=None,  # Missing
        packaging_context="Pump bottle",
        intended_use_context=None,  # Missing
    )

    assert spec.validation_status == "NEEDS_REVIEW"
    assert "process_context" in spec.missing_attributes
    assert "intended_use_context" in spec.missing_attributes
    assert "ingredient[1].material_identity" in spec.missing_attributes
    assert len(spec.ingredients) == 1
    assert spec.ingredients[0]["status"] == "missing"


# ==============================================================================
# 2. Deterministic Measurement Normalization (Tasks 4 & 5)
# ==============================================================================


def test_measurement_normalization_mass_fractions(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Mass fraction normalization retains original values, precision, and scales uncertainty."""
    # 5% to ppm -> 50,000 ppm
    norm1 = product_lab_agent.normalize_measurement(
        original_value=5.0,
        original_unit="%",
        target_unit="ppm",
        uncertainty=0.05,
        precision=2,
    )
    assert norm1.original_value == 5.0
    assert norm1.original_unit == "%"
    assert norm1.normalized_value == 50000.0
    assert norm1.normalized_unit == "ppm"
    assert norm1.uncertainty == 500.0  # 0.05% * 10000 = 500 ppm
    assert "1 % = 10000 ppm" in norm1.conversion_formula
    assert norm1.is_nondetect is False

    # 1000 mg/kg to % -> 0.1%
    norm2 = product_lab_agent.normalize_measurement(
        original_value=1000.0,
        original_unit="mg/kg",
        target_unit="%",
        precision=4,
    )
    assert norm2.normalized_value == 0.1
    assert norm2.normalized_unit == "%"


def test_measurement_normalization_density_dependent(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Volume-to-mass conversions require density and document the conversion formula and assumptions."""
    # 10.5 mg/mL in solution with density 1.05 g/mL -> 10.0 mg/g (1.0% w/w)
    norm = product_lab_agent.normalize_measurement(
        original_value=10.5,
        original_unit="mg/mL",
        target_unit="mg/g",
        density=1.05,
        precision=3,
    )
    assert norm.normalized_value == 10.0
    assert norm.normalized_unit == "mg/g"
    assert any("Supplied density 1.05 g/mL applied" in a for a in norm.assumptions)


def test_measurement_normalization_missing_density_fails_closed(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Attempting density-dependent conversion without density fails closed with ValueError."""
    with pytest.raises(ValueError, match="requires supplied positive density"):
        product_lab_agent.normalize_measurement(
            original_value=10.0,
            original_unit="mg/mL",
            target_unit="% w/w",
            density=None,
        )

    with pytest.raises(ValueError, match="requires supplied positive density"):
        product_lab_agent.normalize_measurement(
            original_value=5.0,
            original_unit="%",
            target_unit="mg/mL",
            density=0.0,
        )


def test_nondetect_never_treated_as_zero(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Non-detects are never converted to 0.0; LOD distinctions are preserved in target units."""
    # "< 0.05 mg/kg" to ppm (1 mg/kg = 1 ppm)
    norm_nd = product_lab_agent.normalize_measurement(
        original_value="< 0.05",
        original_unit="mg/kg",
        target_unit="ppm",
        lod=0.05,
    )
    assert norm_nd.is_nondetect is True
    assert norm_nd.normalized_value != 0.0
    assert norm_nd.normalized_value != "0"
    assert norm_nd.normalized_value == "< 0.05"
    assert norm_nd.lod == 0.05
    assert any("never treated as zero" in a.lower() for a in norm_nd.assumptions)

    # "ND" without numeric bound
    norm_nd_str = product_lab_agent.normalize_measurement(
        original_value="Not Detected",
        original_unit="mg/kg",
        target_unit="ppm",
    )
    assert norm_nd_str.is_nondetect is True
    assert norm_nd_str.normalized_value == "ND"
    assert norm_nd_str.normalized_value != 0.0


# ==============================================================================
# 3. Formulation Evidence Bridge (Tasks 9 & 10)
# ==============================================================================


def test_formulation_bridge_ten_dimensions_match(
    product_lab_agent: ProductLabAgent,
) -> None:
    """10-dimension comparability bridge correctly records all match dimensions."""
    dims = {
        "identity": "match",
        "concentration": "match",
        "vehicle": "match",
        "route": "match",
        "exposure": "match",
        "population": "match",
        "duration": "match",
        "endpoint": "match",
        "manufacturing": "match",
        "packaging": "match",
    }
    bridge = product_lab_agent.evaluate_formulation_bridge(
        studied_material="eDerma Hydro-Gel 5% Niacinamide",
        proposed_product="eDerma Hydro-Gel 5% Niacinamide",
        dimensions=dims,
        is_ingredient_to_finished_product=False,
    )

    assert bridge.identity_comparability == "match"
    assert bridge.concentration_comparability == "match"
    assert bridge.vehicle_comparability == "match"
    assert bridge.route_comparability == "match"
    assert bridge.exposure_comparability == "match"
    assert bridge.population_comparability == "match"
    assert bridge.duration_comparability == "match"
    assert bridge.endpoint_comparability == "match"
    assert bridge.manufacturing_comparability == "match"
    assert bridge.packaging_comparability == "match"
    assert bridge.overall_relevance == EvidenceRelevance.DIRECT
    assert bridge.requires_expert_review is False


def test_formulation_bridge_ingredient_to_finished_requires_bridge(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Ingredient evidence cannot transfer to finished product as DIRECT evidence."""
    dims = {
        "identity": "match",
        "concentration": "match",
        "vehicle": "match",
        "route": "match",
        "exposure": "match",
        "population": "match",
        "duration": "match",
        "endpoint": "match",
        "manufacturing": "match",
        "packaging": "match",
    }
    bridge = product_lab_agent.evaluate_formulation_bridge(
        studied_material="Pure Niacinamide Raw Material (99%)",
        proposed_product="eDerma Finished Serum (5% Niacinamide)",
        dimensions=dims,
        is_ingredient_to_finished_product=True,
    )

    # Must be BRIDGE_REQUIRED, never DIRECT
    assert bridge.overall_relevance == EvidenceRelevance.BRIDGE_REQUIRED


def test_formulation_bridge_invitro_endpoint_mismatch_surfaced(
    product_lab_agent: ProductLabAgent,
) -> None:
    """In-vitro cell assay offered for finished human clinical efficacy is marked NOT_RELEVANT (T15)."""
    dims = {
        "identity": "match",
        "concentration": "mismatch",
        "vehicle": "mismatch",
        "route": "not_applicable",
        "exposure": "mismatch",
        "population": "mismatch",
        "duration": "mismatch",
        "endpoint": "mismatch",  # In vitro vs human clinical
        "manufacturing": "not_applicable",
        "packaging": "not_applicable",
    }
    bridge = product_lab_agent.evaluate_formulation_bridge(
        studied_material="In vitro keratinocyte culture with 0.1% Niacinamide",
        proposed_product="Topical Finished Serum 5% Niacinamide",
        dimensions=dims,
        is_ingredient_to_finished_product=True,
    )

    assert bridge.endpoint_comparability == "mismatch"
    assert bridge.overall_relevance == EvidenceRelevance.NOT_APPLICABLE
    assert bridge.requires_expert_review is True


def test_formulation_bridge_changed_extract_or_vehicle(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Changed supplier extract, concentration, or vehicle flags mismatch and requires review (T16)."""
    dims = {
        "identity": "mismatch",  # Supplier extract changed from 99% pure to 50% hydro-glycolic
        "concentration": "mismatch",
        "vehicle": "mismatch",
        "route": "match",
        "exposure": "match",
        "population": "match",
        "duration": "match",
        "endpoint": "match",
        "manufacturing": "match",
        "packaging": "match",
    }
    bridge = product_lab_agent.evaluate_formulation_bridge(
        studied_material="Standard Aqueous Niacinamide Solution 10%",
        proposed_product="Liposomal Emulsion Niacinamide 5%",
        dimensions=dims,
        is_ingredient_to_finished_product=False,
    )

    assert bridge.identity_comparability == "mismatch"
    assert bridge.vehicle_comparability == "mismatch"
    assert bridge.overall_relevance == EvidenceRelevance.INDIRECT
    assert bridge.requires_expert_review is True


def test_formulation_bridge_invalid_dimension_fails_closed(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Invalid dimension values fail closed with ValueError."""
    dims = {"identity": "semi_comparable"}  # Invalid value
    with pytest.raises(ValueError, match="Invalid comparability value"):
        product_lab_agent.evaluate_formulation_bridge(
            studied_material="A",
            proposed_product="B",
            dimensions=dims,
        )


# ==============================================================================
# 4. Lab Validation Audits (Tasks 6, 7, 8)
# ==============================================================================


def test_lab_validation_valid_report_passes(
    product_lab_agent: ProductLabAgent, lab_case_data: dict[str, Any]
) -> None:
    """Valid lab report with verified accreditation, batch linkage, and non-detects passes."""
    report_data = lab_case_data["valid_lab_report"]
    val = product_lab_agent.validate_lab_report(
        report_data=report_data,
        expected_product_or_batch_id="batch-2026-v2-001",
    )

    assert isinstance(val, LabValidation)
    assert val.validation_outcome == "VALIDATED"
    assert val.conformity_assessment == "PASS"
    assert val.product_linkage_verified is True
    assert val.accreditation_verified is True
    assert val.accreditation_scope_covers_test is True
    assert len(val.deviations) == 0


def test_lab_validation_batch_mismatch_rejected(
    product_lab_agent: ProductLabAgent, lab_case_data: dict[str, Any]
) -> None:
    """Lab report testing legacy or different batch is rejected for the target formulation (T16)."""
    report_data = lab_case_data["batch_mismatch_report"]
    val = product_lab_agent.validate_lab_report(
        report_data=report_data,
        expected_product_or_batch_id="batch-2026-v2-001",  # Expecting v2, report has legacy-999
    )

    assert val.validation_outcome == "REJECTED"
    assert val.product_linkage_verified is False
    assert any("linkage mismatch" in d.lower() for d in val.deviations)
    assert val.conformity_assessment == "REVIEW_REQUIRED"


def test_lab_validation_unverified_visual_report_requires_review(
    product_lab_agent: ProductLabAgent, lab_case_data: dict[str, Any]
) -> None:
    """Report signatures and logos cannot produce a validation pass on visual appearance alone (T24)."""
    report_data = lab_case_data["unverified_visual_report"]
    val = product_lab_agent.validate_lab_report(report_data=report_data)

    assert val.validation_outcome != "VALIDATED"
    assert any("unverified" in d.lower() for d in val.deviations)
    assert any("signature" in r.lower() or "accreditation" in r.lower() for r in val.reviewer_requirements)


def test_lab_validation_out_of_scope_accreditation_rejected(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Accreditation where the test method is outside verified scope is flagged (T24)."""
    report_data = {
        "report_id": "rep-out-of-scope-001",
        "report_hash": "abcdef1234567890",
        "issuer_lab_name": "HydroTest Lab",
        "lab_accreditation": "ISO/IEC 17025 (Water Quality Testing)",
        "accreditation_verified": True,
        "accreditation_scope_covers_test": False,  # Out of scope!
        "test_method": "Cosmetic Preservative Challenge Test",
        "sample_or_batch_id": "batch-2026-001",
        "product_linkage_verified": True,
        "raw_results": {"Preservative Efficacy": "Pass"},
    }
    val = product_lab_agent.validate_lab_report(report_data=report_data)

    assert val.validation_outcome == "REJECTED"
    assert any("outside verified laboratory accreditation scope" in d for d in val.deviations)


def test_lab_validation_expired_accreditation_rejected(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Expired accreditation prior to test date produces deviation and review."""
    report_data = {
        "report_id": "rep-expired-001",
        "report_hash": "abcdef1234567890",
        "issuer_lab_name": "Fast Lab",
        "lab_accreditation": "ISO/IEC 17025",
        "accreditation_verified": True,
        "accreditation_scope_covers_test": True,
        "accreditation_expiry_date": "2024-01-01",
        "test_date": "2026-09-15",  # Tested long after accreditation expired
        "test_method": "HPLC Active Assay",
        "sample_or_batch_id": "batch-2026-001",
        "product_linkage_verified": True,
        "raw_results": {"Active": 5.0},
    }
    val = product_lab_agent.validate_lab_report(report_data=report_data)

    assert val.validation_outcome == "REJECTED"
    assert any("expired" in d.lower() for d in val.deviations)


def test_lab_validation_decision_rule_binary_guard_band(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Measurement in the guard-band uncertainty zone requires expert review (T25)."""
    # Limit: max 10.0 ppm. Result: 9.8 ppm. Uncertainty: +/- 0.5 ppm.
    # Acceptance limit = 10.0 - 0.5 = 9.5 ppm.
    # 9.8 is in the guard band [9.5, 10.0] -> REVIEW_REQUIRED!
    report_data = {
        "report_id": "rep-guard-band-001",
        "report_hash": "hash123",
        "issuer_lab_name": "Test Lab",
        "test_method": "ICP-MS Lead",
        "sample_or_batch_id": "batch-2026-001",
        "product_linkage_verified": True,
        "raw_results": {"Lead": 9.8},
        "uncertainty": {"Lead": 0.5},
        "specification_limits": {"Lead": {"max": 10.0, "unit": "ppm"}},
        "specification_limit_source": "USP <232>",
        "decision_rule": "binary_guard_band",
        "accreditation_verified": True,
        "accreditation_scope_covers_test": True,
    }
    val = product_lab_agent.validate_lab_report(report_data=report_data)

    assert val.conformity_assessment == "REVIEW_REQUIRED"
    assert val.validation_outcome == "DEVIATIONS_NOTED"


def test_lab_validation_nondetect_lod_exceeding_limit(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Non-detect with LOD higher than the specification limit cannot establish conformity (T25)."""
    # Limit: max 0.02 ppm. Result: "< 0.05 ppm" (LOD = 0.05).
    # Since LOD > limit, non-detect does not prove compliance!
    report_data = {
        "report_id": "rep-high-lod-001",
        "report_hash": "hash123",
        "issuer_lab_name": "Test Lab",
        "test_method": "ICP-MS Cadmium",
        "sample_or_batch_id": "batch-2026-001",
        "product_linkage_verified": True,
        "raw_results": {"Cadmium": "< 0.05"},
        "lod_loq": {"Cadmium_lod": 0.05},
        "specification_limits": {"Cadmium": {"max": 0.02, "unit": "ppm"}},
        "specification_limit_source": "EU 1223/2009",
        "decision_rule": "simple_acceptance",
        "accreditation_verified": True,
        "accreditation_scope_covers_test": True,
    }
    val = product_lab_agent.validate_lab_report(report_data=report_data)

    assert val.conformity_assessment == "REVIEW_REQUIRED"
    assert any("exceeds specification limit" in d for d in val.deviations)


def test_lab_validation_missing_limit_source_returns_unknown(
    product_lab_agent: ProductLabAgent,
) -> None:
    """Conformity evaluation without authoritative limit source returns UNKNOWN (Task 8)."""
    report_data = {
        "report_id": "rep-no-source-001",
        "report_hash": "hash123",
        "issuer_lab_name": "Test Lab",
        "test_method": "Assay",
        "sample_or_batch_id": "batch-2026-001",
        "product_linkage_verified": True,
        "raw_results": {"Active": 5.0},
        "specification_limits": {"Active": {"min": 4.5, "max": 5.5}},
        "specification_limit_source": "",  # Missing!
        "accreditation_verified": True,
        "accreditation_scope_covers_test": True,
    }
    val = product_lab_agent.validate_lab_report(report_data=report_data)

    assert val.conformity_assessment == "UNKNOWN"
    assert any("without authoritative limit source" in d for d in val.deviations)


# ==============================================================================
# 5. Offline Isolation & S_VAL Dispatch (Tasks 11, 12, 14)
# ==============================================================================


def test_product_lab_offline_isolation_policy() -> None:
    """ProductLab specialist operates under strict network_policy: DISABLED."""
    policy = PRODUCT_SPECIALIST_POLICIES["w_prod.product_lab"]
    assert policy["network_policy"] == NetworkPolicy.DISABLED
    assert "formulation_validator" in policy["allowed_tools"]
    assert "lab_report_auditor" in policy["allowed_tools"]

    # Denies network egress requests
    with pytest.raises(SandboxInvocationError, match="restricted to DENY_ALL"):
        validate_capability_access(
            SandboxCapability.VAL,
            WorkerRole.PRODUCT_EVIDENCE,
            operation="audit_lab_report",
            requested_network=NetworkPolicy.ALLOWLIST,
            specialist_id="w_prod.product_lab",
            egress_grant=None,
        )


def test_product_lab_s_val_dispatch_end_to_end(
    product_lab_agent: ProductLabAgent,
    parent_task: ProductEvidenceTask,
    lab_case_data: dict[str, Any],
) -> None:
    """ProductLab specialist dispatches to S_VAL and receives verified structured findings."""
    task = product_lab_agent.build_task(
        task_id="spec-lab-e2e-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        operation="audit_lab_report",
        context_slice={
            "report_id": "rep-eurofins-2026-098",
            "batch_id": "batch-2026-v2-001",
        },
    )

    run_s_val = _load_run_s_val()

    def mock_runner(mandate: SandboxInvocationMandate) -> dict[str, Any]:
        return run_s_val(mandate.payload)

    product_lab_agent._sandbox_client = mock_runner

    report_data = lab_case_data["valid_lab_report"]
    res: SpecialistResult = product_lab_agent.execute_lab_validation(
        specialist_task=task,
        parent_task=parent_task,
        report_data=report_data,
        expected_batch_id="batch-2026-v2-001",
    )

    assert res.status == SpecialistResultStatus.COMPLETED
    assert res.specialist_role == SpecialistRole.PRODUCT_LAB
    assert res.typed_findings["audit_outcome"] == "VALIDATED"
    assert res.typed_findings["conformity_assessment"] == "PASS"
    assert "lab_validation" in res.typed_findings
    assert res.provenance_fragments["profile_digest"] == PRODUCT_LAB_PROFILE.compute_digest()
