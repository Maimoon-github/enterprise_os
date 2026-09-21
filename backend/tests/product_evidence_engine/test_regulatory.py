"""Unit and integration tests for PE-07 Regulatory Applicability and Statutory Compliance (w_prod.regulatory)."""

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import pytest

from app.agents.product_evidence_engine.product_evidence import REGULATORY_PROFILE
from app.agents.product_evidence_engine.subagents.regulatory import ProductRegulatoryAgent
from app.schemas.product_evidence import (
    ClaimKind,
    ClaimRecord,
    ClaimStatus,
    ProductEvidenceTask,
    RegulatoryRule,
    RuleApplication,
    RuleApplicationResult,
    RuleForce,
    RuleStatus,
    SpecialistResultStatus,
    SpecialistRole,
)


@pytest.fixture
def evidence_cases() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "evidence_cases.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


def test_rule_applicability_jurisdiction_and_product_class_match(evidence_cases):
    """Task 10, 12, 15: Rule applicability verified against exact jurisdiction, product class, and date."""
    eu_rule = evidence_cases["claims_regulatory_case"]["rules"]["eu_cosmetics_evidence_rule"]

    # 1. Matching EU and cosmetics
    is_app, reason, outcome = ProductRegulatoryAgent.verify_rule_currency_and_applicability(
        rule=eu_rule,
        target_jurisdiction="EU",
        target_product_class="cosmetics",
        assessment_date="2026-09-21",
    )
    assert is_app is True
    assert outcome == RuleApplicationResult.MEETS_CHECKED_REQUIREMENT

    # 2. Jurisdiction mismatch (rule is EU, target is US)
    is_app, reason, outcome = ProductRegulatoryAgent.verify_rule_currency_and_applicability(
        rule=eu_rule,
        target_jurisdiction="US",
        target_product_class="cosmetics",
        assessment_date="2026-09-21",
    )
    assert is_app is False
    assert outcome == RuleApplicationResult.NOT_APPLICABLE
    assert "Jurisdiction mismatch" in reason

    # 3. Product class mismatch (rule is cosmetics, target is dietary_supplement)
    is_app, reason, outcome = ProductRegulatoryAgent.verify_rule_currency_and_applicability(
        rule=eu_rule,
        target_jurisdiction="EU",
        target_product_class="dietary_supplement",
        assessment_date="2026-09-21",
    )
    assert is_app is False
    assert outcome == RuleApplicationResult.NOT_APPLICABLE
    assert "Product class mismatch" in reason


def test_superseded_or_unverified_rule_cannot_yield_compliance_pass(evidence_cases):
    """Task 14: Superseded or unverified rules cannot yield MEETS_CHECKED_REQUIREMENT."""
    superseded_rule = evidence_cases["claims_regulatory_case"]["rules"]["superseded_rule"]

    is_app, reason, outcome = ProductRegulatoryAgent.verify_rule_currency_and_applicability(
        rule=superseded_rule,
        target_jurisdiction="UK",
        target_product_class="cosmetics",
        assessment_date="2026-09-21",
    )
    assert is_app is False
    assert outcome != RuleApplicationResult.MEETS_CHECKED_REQUIREMENT
    assert outcome == RuleApplicationResult.NOT_APPLICABLE
    assert "superseded" in reason.lower()

    # Unverified rule
    unverified_rule = RegulatoryRule(
        id="rule-unverified-01",
        source_id="src-draft-unverified",
        location="Article 1",
        jurisdiction="US",
        product_class="cosmetics",
        force=RuleForce.REGULATION,
        status=RuleStatus.UNVERIFIED,
        activity_ref="act-reg-01",
    )
    is_app, reason, outcome = ProductRegulatoryAgent.verify_rule_currency_and_applicability(
        rule=unverified_rule,
        target_jurisdiction="US",
        target_product_class="cosmetics",
        assessment_date="2026-09-21",
    )
    assert is_app is False
    assert outcome == RuleApplicationResult.UNKNOWN
    assert "unverified" in reason.lower()


def test_future_commencement_rule_cannot_yield_compliance_pass(evidence_cases):
    """Task 14: Future commencement rule cannot yield MEETS_CHECKED_REQUIREMENT; publication != commencement."""
    future_rule = evidence_cases["claims_regulatory_case"]["rules"]["future_commencement_rule"]

    is_app, reason, outcome = ProductRegulatoryAgent.verify_rule_currency_and_applicability(
        rule=future_rule,
        target_jurisdiction="US",
        target_product_class="cosmetics",
        assessment_date="2026-09-21",
    )
    assert is_app is False
    assert outcome == RuleApplicationResult.UNKNOWN
    assert "commencement" in reason.lower() or "future" in reason.lower()


def test_guidance_vs_law_distinction_not_promoted(evidence_cases):
    """Task 11: Non-binding guidance is separately tagged and never promoted to statute."""
    guidance_rule = evidence_cases["claims_regulatory_case"]["rules"]["guidance_rule"]
    claim = ClaimRecord(
        id="claim-hydration-01",
        text="Hydrates skin surface.",
        asset_ref="asset-pdp",
        asset_location="Front",
        status=ClaimStatus.SUPPORTED_IN_SCOPE,
        activity_ref="act-01",
        interpretation_reason="Substantiated cosmetic claim",
    )

    app = ProductRegulatoryAgent.apply_rule_to_claim(
        rule=guidance_rule,
        claim=claim,
        target_jurisdiction="US",
        target_product_class="cosmetics",
        assessment_date="2026-09-21",
    )

    assert app.outcome == RuleApplicationResult.MEETS_CHECKED_REQUIREMENT
    # Reason must explicitly mention guidance is non-binding
    assert "non-binding" in app.reason.lower() or "guidance" in app.reason.lower()


def test_disease_claim_on_cosmetic_fails_closed_and_escalates(evidence_cases):
    """Task 10, 18: Therapeutic/disease treatment claims on cosmetics breach statutory class and escalate."""
    prohibition_rule = evidence_cases["claims_regulatory_case"]["rules"]["eu_disease_claim_prohibition"]
    disease_claim = ClaimRecord(
        id="claim-disease-eczema-01",
        version="1.0",
        text="Fast-acting serum treats eczema and cures dermatitis permanently.",
        kind=ClaimKind.EXPLICIT,
        asset_ref="asset-carton-front",
        asset_location="Principal display panel",
        product_version="ederma-v2",
        jurisdiction="EU",
        status=ClaimStatus.SUPPORTED_IN_SCOPE,  # Even if user claimed scientific support!
        activity_ref="act-01",
        interpretation_reason="Therapeutic claim text",
    )

    app = ProductRegulatoryAgent.apply_rule_to_claim(
        rule=prohibition_rule,
        claim=disease_claim,
        target_jurisdiction="EU",
        target_product_class="cosmetics",
        assessment_date="2026-09-21",
    )

    # Must fail closed
    assert app.outcome == RuleApplicationResult.DOES_NOT_MEET_CHECKED_REQUIREMENT
    assert app.severity_if_breached == "critical"
    assert app.escalation_required is True
    assert "medicinal" in app.reason.lower() or "disease" in app.reason.lower()


def test_scientific_substantiation_separate_from_regulatory_status(evidence_cases):
    """Task 17: Scientific support and regulatory compliance remain independent status axes."""
    prohibition_rule = evidence_cases["claims_regulatory_case"]["rules"]["eu_disease_claim_prohibition"]
    claim = ClaimRecord(
        id="claim-anti-inflammatory-01",
        version="1.0",
        text="Clinically proven formula heals dermatitis.",
        kind=ClaimKind.EXPLICIT,
        asset_ref="asset-carton",
        asset_location="Front",
        status=ClaimStatus.SUPPORTED_IN_SCOPE,  # High clinical efficacy proven in RCT
        activity_ref="act-01",
        interpretation_reason="Robust RCT supports anti-inflammatory action",
    )

    app = ProductRegulatoryAgent.apply_rule_to_claim(
        rule=prohibition_rule,
        claim=claim,
        target_jurisdiction="EU",
        target_product_class="cosmetics",
        assessment_date="2026-09-21",
    )

    # Scientific status is supported, but regulatory status MUST be DOES_NOT_MEET_CHECKED_REQUIREMENT
    assert claim.status == ClaimStatus.SUPPORTED_IN_SCOPE
    assert app.outcome == RuleApplicationResult.DOES_NOT_MEET_CHECKED_REQUIREMENT


def _load_run_s_val():
    import importlib.util
    root = Path(__file__).resolve().parents[3]
    script_path = root / "sandbox" / "docker" / "hardened" / "skills" / "s-val" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("s_val_run", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "run_s_val")


def test_regulatory_s_val_dispatch_and_escalation():
    """Task 18, 20: Regulatory check dispatches via S_VAL sandbox runtime and surfaces escalations."""
    agent = ProductRegulatoryAgent()
    run_s_val = _load_run_s_val()
    agent._sandbox_client = lambda mandate: run_s_val(mandate.payload)

    task = agent.build_task(
        task_id="task-reg-001",
        tenant_id="tenant-derma-01",
        parent_task_id="parent-pe-001",
        operation="check_regulatory_rules",
    )
    parent_task = ProductEvidenceTask(
        task_id="parent-pe-001",
        tenant_id="tenant-derma-01",
        run_id="run-001",
        parent_grant_ref="grant-derma-001",
        parent_grant_hash="hash-derma-001",
        context_version="1.0",
        context_hash="ctx-reg-001",
        product_version="ederma-v2",
        allowed_s_val_operations=["check_regulatory_rules", "apply_rules"],
        budget_limit_tokens=8000,
        deadline_utc=datetime.now(UTC) + timedelta(hours=2),
    )

    # Test passing rule application
    valid_app = RuleApplication(
        application_id="app-001",
        target_id="claim-001",
        rule_id="rule-eu-655-2013",
        jurisdiction="EU",
        product_class="cosmetics",
        outcome=RuleApplicationResult.MEETS_CHECKED_REQUIREMENT,
        reason="Claim meets evidential criteria.",
        escalation_required=False,
    )

    res = agent.execute_regulatory_check(
        specialist_task=task,
        parent_task=parent_task,
        applications=[valid_app],
    )

    assert res.status == SpecialistResultStatus.COMPLETED
    assert res.typed_findings.get("regulatory_status") == "MEETS_CHECKED_REQUIREMENT"
    assert res.typed_findings.get("escalation_required") is False
