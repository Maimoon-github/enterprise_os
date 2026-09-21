"""PE-06: Evidence Appraisal and Safety Review Specialist Tests.

Verifies:
1. EvidenceAssessment preserves separate judgments for source integrity, risk of bias,
   relevance, precision, consistency, and certainty with explicit justifications.
2. Abstract-only / paywalled sources cannot become "low risk of bias".
3. Low-power, nonsignificant studies cannot be interpreted as proving absence of harm (T22).
4. Multiple publications/reviews sharing the same underlying study cohort are counted as ONE
   study family, preventing false consistency inflation (T19).
5. Contradictory clinical trials are preserved via ConflictRecord and never erased by synthesis
   or majority vote (T20).
6. Evidence gaps explicitly distinguish missing studies, inaccessible evidence, missing exposure,
   missing vulnerable populations, and demonstrated absence of effect.
7. SafetyAssessment binds product version, hazards, exposure scenario, vulnerable populations,
   relevant endpoints, and limitations.
8. 'no_concern_identified_in_scope' strictly requires explicit scoped boundary conditions (Task 12).
9. Severe adverse signals trigger immediate concern status, prevent clearance, and mandate escalation (T23).
10. Unrestricted "safe" declarations are strictly prohibited.
11. Qualified human reviewer involvement is mandatory for all material safety conclusions.
12. Offline isolation under network_policy: DISABLED for both appraisal and safety specialists.
13. S_VAL dispatch and structured result formatting for appraisal and safety.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib.util
import json
from pathlib import Path
from typing import Any
import pytest

from app.agents.product_evidence_engine.product_evidence import (
    APPRAISAL_PROFILE,
    SAFETY_PROFILE,
)
from app.agents.product_evidence_engine.subagents.appraisal import ProductAppraisalAgent
from app.agents.product_evidence_engine.subagents.safety import ProductSafetyAgent
from app.core.exceptions import SandboxInvocationError
from app.integrations.sandbox.capabilities import (
    PRODUCT_SPECIALIST_POLICIES,
    validate_capability_access,
)
from app.schemas.governance import WorkerRole
from app.schemas.product_evidence import (
    ConflictRecord,
    EvidenceAssessment,
    EvidenceGap,
    EvidenceRelevance,
    ProductEvidenceTask,
    SafetyAssessment,
    SafetyStatus,
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
def appraisal_safety_fixtures(evidence_fixture_data: dict[str, Any]) -> dict[str, Any]:
    return evidence_fixture_data["appraisal_safety_case"]


@pytest.fixture
def appraisal_agent() -> ProductAppraisalAgent:
    return ProductAppraisalAgent()


@pytest.fixture
def safety_agent() -> ProductSafetyAgent:
    return ProductSafetyAgent()


@pytest.fixture
def parent_task() -> ProductEvidenceTask:
    return ProductEvidenceTask(
        task_id="pe-task-app-safe-001",
        tenant_id="tenant-derma-01",
        run_id="run-app-safe-001",
        parent_grant_ref="grant-derma-001",
        parent_grant_hash="hash-derma-001",
        context_version="1.0",
        context_hash="ctx-app-safe-001",
        product_version="2.0",
        allowed_s_val_operations=["appraise_evidence", "assess_safety", "evaluate_hazards"],
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
# 1. Evidence Assessment Domains (Tasks 3, 4, 5)
# ==============================================================================


def test_evidence_assessment_domains_explicit_and_justified(
    appraisal_agent: ProductAppraisalAgent,
) -> None:
    """EvidenceAssessment maintains explicit, independent evaluations for bias, relevance, and precision."""
    assess = appraisal_agent.appraise_evidence_item(
        assessment_id="assess-rct-001",
        evidence_refs=["ev-001"],
        assessor_activity_id="act-appraise-001",
        method_version="GRADE_v1",
        source_integrity="verified",
        risk_of_bias="low",
        relevance=EvidenceRelevance.DIRECT,
        precision="precise",
        consistency="consistent",
        certainty="high",
        justification="Triple-blind randomized controlled trial with adequate concealment.",
        supporting_source_locations=["Page 4, Table 2", "Page 5, Methods"],
        study_design="Double-blind RCT",
        sample_size=120,
        p_value=0.001,
    )

    assert isinstance(assess, EvidenceAssessment)
    assert assess.risk_of_bias == "low"
    assert assess.precision == "precise"
    assert assess.certainty == "high"
    assert assess.relevance == EvidenceRelevance.DIRECT
    assert "Triple-blind" in assess.justification
    assert len(assess.supporting_source_locations) == 2


def test_paywall_or_abstract_cannot_become_low_risk_of_bias(
    appraisal_agent: ProductAppraisalAgent,
    appraisal_safety_fixtures: dict[str, Any],
) -> None:
    """An abstract-only / paywalled source cannot be granted 'low' risk of bias (T21)."""
    ev = appraisal_safety_fixtures["paywalled_abstract_evidence"]
    assess = appraisal_agent.appraise_evidence_item(
        assessment_id="assess-paywall-001",
        evidence_refs=[ev["id"]],
        assessor_activity_id="act-appraise-002",
        source_integrity="verified",
        risk_of_bias="low",  # Evaluator attempts 'low'
        certainty="high",
        is_paywalled_or_abstract_only=True,
    )

    # Must be downgraded from low
    assert assess.risk_of_bias != "low"
    assert assess.risk_of_bias == "some_concerns"
    assert assess.source_integrity == "partial"
    assert assess.certainty in ("low", "moderate")
    assert any("abstract-only" in assess.justification.lower() for _ in [1])


def test_low_power_nonsignificant_cannot_prove_absence_of_harm(
    appraisal_agent: ProductAppraisalAgent,
    appraisal_safety_fixtures: dict[str, Any],
) -> None:
    """Nonsignificant low-power study is flagged for serious imprecision and cannot prove no harm (T22)."""
    ev = appraisal_safety_fixtures["low_power_evidence"]
    assess = appraisal_agent.appraise_evidence_item(
        assessment_id="assess-low-power-001",
        evidence_refs=[ev["id"]],
        assessor_activity_id="act-appraise-003",
        precision="precise",
        certainty="high",
        sample_size=ev["sample_size"],  # n=12
        p_value=ev["p_value"],  # p=0.22
    )

    assert assess.precision == "serious_imprecision"
    assert assess.certainty != "high"
    assert any("p=0.22" in assess.justification for _ in [1])
    assert any("cannot be inferred as definitive proof of absence" in assess.justification for _ in [1])


# ==============================================================================
# 2. Body-Level Consistency & Duplicate Cohorts (Tasks 5, 6, 8; T19, T20)
# ==============================================================================


def test_duplicate_cohort_publications_do_not_inflate_consistency(
    appraisal_agent: ProductAppraisalAgent,
    appraisal_safety_fixtures: dict[str, Any],
) -> None:
    """Multiple publications from the same underlying study cohort count as ONE study family (T19)."""
    ev_items = appraisal_safety_fixtures["duplicate_cohort_evidence"]
    consistency, conflicts, stats = appraisal_agent.evaluate_body_consistency(
        evidence_items=ev_items,
        target_claim_or_endpoint="40% hydration increase",
    )

    assert stats["total_publications"] == 3
    assert stats["unique_study_families"] == 1  # Deduplicated to 1 cohort!
    assert len(conflicts) == 0


def test_conflicting_trials_preserved_in_conflict_record(
    appraisal_agent: ProductAppraisalAgent,
    appraisal_safety_fixtures: dict[str, Any],
) -> None:
    """Opposing clinical trials trigger unresolved_conflict and generate a ConflictRecord (T20)."""
    ev_items = appraisal_safety_fixtures["conflicting_trials_evidence"]
    consistency, conflicts, stats = appraisal_agent.evaluate_body_consistency(
        evidence_items=ev_items,
        target_claim_or_endpoint="Reduction in trans-epidermal water loss",
    )

    assert consistency == "unresolved_conflict"
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert isinstance(conflict, ConflictRecord)
    assert conflict.incompatibility_type == "opposing_clinical_outcomes"
    assert "ev-trial-pos-01" in conflict.conflicting_evidence_ids
    assert "ev-trial-neg-02" in conflict.conflicting_evidence_ids
    assert "majority vote synthesis prohibited" in conflict.reconciliation_attempt.lower()
    assert len(conflict.comparable_dimensions) > 0


# ==============================================================================
# 3. Evidence Gap Categorization (Task 9)
# ==============================================================================


def test_evidence_gaps_categorized_properly(
    appraisal_agent: ProductAppraisalAgent,
) -> None:
    """Evidence gaps distinguish missing studies, exposure duration gaps, and well-powered absence of effect."""
    # 1. Zero studies returned
    gaps_empty = appraisal_agent.identify_evidence_gaps("Acne vulgaris lesion reduction", [])
    assert len(gaps_empty) == 1
    assert gaps_empty[0].gap_kind == "no_study_found"
    assert gaps_empty[0].blocking is True

    # 2. Exposure duration gap
    items = [
        {"id": "ev-short-01", "duration_days": 14, "sample_size": 30},
    ]
    gaps_dur = appraisal_agent.identify_evidence_gaps(
        target_claim_or_endpoint="Long-term skin barrier reinforcement",
        acquired_evidence=items,
        expected_coverage={"required_duration_days": 60},
    )
    assert any(g.gap_kind == "missing_exposure_coverage" for g in gaps_dur)

    # 3. Well-powered study demonstrating true absence of effect
    items_absence = [
        {"id": "ev-null-01", "outcome": "No statistically significant difference in sebum rate", "sample_size": 100},
    ]
    gaps_absence = appraisal_agent.identify_evidence_gaps(
        target_claim_or_endpoint="Sebum suppression",
        acquired_evidence=items_absence,
    )
    assert any(g.gap_kind == "supports_absence_of_effect" for g in gaps_absence)
    absence_gap = [g for g in gaps_absence if g.gap_kind == "supports_absence_of_effect"][0]
    assert absence_gap.severity == "critical"
    assert absence_gap.blocking is True


# ==============================================================================
# 4. Safety Assessment & Scoped Boundaries (Tasks 10, 11, 12, 14, 15; T23)
# ==============================================================================


def test_safety_assessment_scoped_conditions_enforced(
    safety_agent: ProductSafetyAgent,
    appraisal_safety_fixtures: dict[str, Any],
) -> None:
    """A valid 'no_concern_identified_in_scope' safety assessment states exact boundary conditions."""
    data = appraisal_safety_fixtures["valid_scoped_safety"]
    assessment = safety_agent.assess_safety(
        assessment_id=data["assessment_id"],
        product_version=data["product_version"],
        hazards_evaluated=data["hazards_evaluated"],
        exposure_scenario=data["exposure_scenario"],
        vulnerable_populations_considered=data["vulnerable_populations_considered"],
        evidence_refs=data["evidence_refs"],
        adverse_signals=data["adverse_signals"],
        status=SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE,
        relevant_endpoints=data["relevant_endpoints"],
        exposure_assumptions=data["exposure_assumptions"],
        scoped_conditions=data["scoped_conditions"],
        limitations_or_uncertainties=data["limitations_or_uncertainties"],
    )

    assert isinstance(assessment, SafetyAssessment)
    assert assessment.status == SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE
    assert assessment.scoped_conditions["target_population"] == data["scoped_conditions"]["target_population"]
    assert assessment.scoped_conditions["route"] == data["scoped_conditions"]["route"]
    assert assessment.scoped_conditions["max_daily_exposure"] == data["scoped_conditions"]["max_daily_exposure"]
    assert assessment.qualified_reviewer_required is True


def test_safety_assessment_unscoped_no_concern_fails_closed(
    safety_agent: ProductSafetyAgent,
) -> None:
    """'no_concern_identified_in_scope' without explicit scoped boundary conditions fails closed."""
    with pytest.raises(ValueError, match="must state its exact boundary conditions"):
        safety_agent.assess_safety(
            assessment_id="safe-invalid-01",
            product_version="2.0",
            hazards_evaluated=["Skin irritation"],
            exposure_scenario="Topical serum",
            vulnerable_populations_considered=["Adults"],
            evidence_refs=["ev-001"],
            adverse_signals=[],
            status=SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE,
            relevant_endpoints=["Erythema"],
            scoped_conditions={},  # Empty scoped conditions!
        )


def test_severe_adverse_signal_overrides_clearance_and_escalates(
    safety_agent: ProductSafetyAgent,
    appraisal_safety_fixtures: dict[str, Any],
) -> None:
    """Severe adverse signals (sensitization / erythema grade 3) prevent clearance (T23)."""
    data = appraisal_safety_fixtures["severe_adverse_signal_case"]
    assessment = safety_agent.assess_safety(
        assessment_id=data["assessment_id"],
        product_version=data["product_version"],
        hazards_evaluated=data["hazards_evaluated"],
        exposure_scenario=data["exposure_scenario"],
        vulnerable_populations_considered=data["vulnerable_populations_considered"],
        evidence_refs=data["evidence_refs"],
        adverse_signals=data["adverse_signals"],
        status=SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE,  # Attempting to clear despite adverse signal
        relevant_endpoints=["Sensitization"],
        scoped_conditions={
            "target_population": "Adults",
            "route": "Topical",
            "max_daily_exposure": "1 g",
            "max_duration": "30 days",
        },
    )

    # Overridden to CONCERN_IDENTIFIED
    assert assessment.status == SafetyStatus.CONCERN_IDENTIFIED
    assert any("Severe adverse event signals detected" in lim for lim in assessment.limitations_or_uncertainties)
    assert assessment.qualified_reviewer_required is True


def test_vulnerable_populations_unassessed_adds_limitations(
    safety_agent: ProductSafetyAgent,
) -> None:
    """Unassessed vulnerable populations explicitly limit scope and document non-applicability (T23)."""
    assessment = safety_agent.assess_safety(
        assessment_id="safe-unassessed-vuln",
        product_version="2.0",
        hazards_evaluated=["Skin irritation"],
        exposure_scenario="Topical serum",
        vulnerable_populations_considered=[],  # Vulnerable populations omitted!
        evidence_refs=["ev-001"],
        adverse_signals=[],
        status=SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE,
        relevant_endpoints=["Erythema"],
        scoped_conditions={
            "target_population": "Adults without active eczema",
            "route": "Topical dermal",
            "max_daily_exposure": "1 g",
            "max_duration": "14 days",
        },
    )

    assert assessment.status == SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE
    assert any("Vulnerable populations" in lim for lim in assessment.limitations_or_uncertainties)
    assert assessment.scoped_conditions.get("vulnerable_populations_excluded") is True


def test_unrestricted_safe_status_prohibited(
    safety_agent: ProductSafetyAgent,
) -> None:
    """Unrestricted 'safe' declaration outside SafetyStatus enum is rejected."""
    with pytest.raises(ValueError, match="Invalid safety status"):
        safety_agent.assess_safety(
            assessment_id="safe-prohibited",
            product_version="2.0",
            hazards_evaluated=["Skin irritation"],
            exposure_scenario="Topical serum",
            vulnerable_populations_considered=["Adults"],
            evidence_refs=["ev-001"],
            adverse_signals=[],
            status="safe",  # type: ignore[arg-type] # Prohibited string!
        )


# ==============================================================================
# 5. Offline Isolation & S_VAL Dispatch (Tasks 16, 17)
# ==============================================================================


def test_appraisal_and_safety_offline_isolation_policy() -> None:
    """Appraisal and Safety operate under strict network_policy: DISABLED."""
    for spec_id in ("w_prod.appraisal", "w_prod.safety"):
        policy = PRODUCT_SPECIALIST_POLICIES[spec_id]
        assert policy["network_policy"] == NetworkPolicy.DISABLED

        # Denies network egress requests
        with pytest.raises(SandboxInvocationError, match="restricted to DENY_ALL"):
            validate_capability_access(
                SandboxCapability.VAL,
                WorkerRole.PRODUCT_EVIDENCE,
                operation="appraise_evidence" if "appraisal" in spec_id else "assess_safety",
                requested_network=NetworkPolicy.ALLOWLIST,
                specialist_id=spec_id,
                egress_grant=None,
            )


def test_appraisal_s_val_dispatch_end_to_end(
    appraisal_agent: ProductAppraisalAgent,
    parent_task: ProductEvidenceTask,
    appraisal_safety_fixtures: dict[str, Any],
) -> None:
    """Appraisal specialist dispatches to S_VAL and receives verified structured findings."""
    task = appraisal_agent.build_task(
        task_id="spec-app-e2e-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        operation="appraise_evidence",
        context_slice={"claim": "Clinically proven barrier recovery"},
    )

    run_s_val = _load_run_s_val()

    def mock_runner(mandate: SandboxInvocationMandate) -> dict[str, Any]:
        return run_s_val(mandate.payload)

    appraisal_agent._sandbox_client = mock_runner

    ev_items = appraisal_safety_fixtures["conflicting_trials_evidence"]
    res: SpecialistResult = appraisal_agent.execute_appraisal(
        specialist_task=task,
        parent_task=parent_task,
        evidence_items=ev_items,
        target_claim="Barrier recovery",
    )

    assert res.status == SpecialistResultStatus.COMPLETED
    assert res.specialist_role == SpecialistRole.APPRAISAL
    assert res.typed_findings["consistency"] == "unresolved_conflict"
    assert len(res.typed_findings["conflict_records"]) == 1
    assert res.provenance_fragments["profile_digest"] == APPRAISAL_PROFILE.compute_digest()


def test_safety_s_val_dispatch_end_to_end(
    safety_agent: ProductSafetyAgent,
    parent_task: ProductEvidenceTask,
    appraisal_safety_fixtures: dict[str, Any],
) -> None:
    """Safety specialist dispatches to S_VAL and receives verified structured findings."""
    task = safety_agent.build_task(
        task_id="spec-safe-e2e-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        operation="assess_safety",
        context_slice={"product_version": "2.0"},
    )

    run_s_val = _load_run_s_val()

    def mock_runner(mandate: SandboxInvocationMandate) -> dict[str, Any]:
        return run_s_val(mandate.payload)

    safety_agent._sandbox_client = mock_runner

    data = appraisal_safety_fixtures["valid_scoped_safety"]
    safety_assessment = safety_agent.assess_safety(
        assessment_id=data["assessment_id"],
        product_version=data["product_version"],
        hazards_evaluated=data["hazards_evaluated"],
        exposure_scenario=data["exposure_scenario"],
        vulnerable_populations_considered=data["vulnerable_populations_considered"],
        evidence_refs=data["evidence_refs"],
        adverse_signals=data["adverse_signals"],
        status=SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE,
        relevant_endpoints=data["relevant_endpoints"],
        exposure_assumptions=data["exposure_assumptions"],
        scoped_conditions=data["scoped_conditions"],
        limitations_or_uncertainties=data["limitations_or_uncertainties"],
    )

    res: SpecialistResult = safety_agent.execute_safety_review(
        specialist_task=task,
        parent_task=parent_task,
        safety_assessment=safety_assessment,
    )

    assert res.status == SpecialistResultStatus.COMPLETED
    assert res.specialist_role == SpecialistRole.SAFETY
    assert res.typed_findings["safety_status"] == "no_concern_identified_in_scope"
    assert res.typed_findings["qualified_reviewer_required"] is True
    assert res.provenance_fragments["profile_digest"] == SAFETY_PROFILE.compute_digest()
