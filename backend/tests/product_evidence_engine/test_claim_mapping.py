"""Unit and integration tests for PE-07 Claim Mapping and Asset Interpretation (w_prod.claims)."""

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import pytest

from app.agents.product_evidence_engine.product_evidence import CLAIMS_PROFILE
from app.schemas.sandbox import NetworkPolicy
from app.agents.product_evidence_engine.subagents.claims import ProductClaimsAgent
from app.schemas.product_evidence import (
    ClaimEvidenceEdge,
    ClaimKind,
    ClaimRecord,
    ClaimStatus,
    EvidenceRelevance,
    ExtractedEvidence,
    FormulationEvidenceBridge,
    MappingRelation,
    ProductEvidenceTask,
    SpecialistResultStatus,
    SpecialistRole,
)


@pytest.fixture
def evidence_cases() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "evidence_cases.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


def test_asset_context_hashing_and_version_sensitivity():
    """Task 3, 5: Changed wording, imagery, translation, qualifier, or locale creates distinct hash and version."""
    base_hash = ProductClaimsAgent.compute_asset_hash(
        wording="Reduces fine lines in 7 days.",
        imagery_ref="dropper_vial_neutral",
        qualifiers=["*when applied twice daily"],
        locale="en_US",
    )

    # 1. Wording change
    wording_hash = ProductClaimsAgent.compute_asset_hash(
        wording="Reduces fine lines and wrinkles in 7 days.",
        imagery_ref="dropper_vial_neutral",
        qualifiers=["*when applied twice daily"],
        locale="en_US",
    )
    assert base_hash != wording_hash

    # 2. Imagery change
    imagery_hash = ProductClaimsAgent.compute_asset_hash(
        wording="Reduces fine lines in 7 days.",
        imagery_ref="doctor_lab_coat_medical",
        qualifiers=["*when applied twice daily"],
        locale="en_US",
    )
    assert base_hash != imagery_hash

    # 3. Translation / Locale change
    locale_hash = ProductClaimsAgent.compute_asset_hash(
        wording="Réduit les ridules en 7 jours.",
        imagery_ref="dropper_vial_neutral",
        qualifiers=["*when applied twice daily"],
        locale="fr_FR",
    )
    assert base_hash != locale_hash

    # 4. Qualifier change
    qualifier_hash = ProductClaimsAgent.compute_asset_hash(
        wording="Reduces fine lines in 7 days.",
        imagery_ref="dropper_vial_neutral",
        qualifiers=["*in a clinical trial of 30 women"],
        locale="en_US",
    )
    assert base_hash != qualifier_hash


def test_express_vs_implied_claim_atomization(evidence_cases):
    """Task 4, 18: Atomize express propositions and record plausible implied interpretations separately."""
    sample = evidence_cases["claims_regulatory_case"]["asset_sample"]
    records = ProductClaimsAgent.atomize_asset_claims(
        wording=sample["wording"],
        asset_ref=sample["asset_ref"],
        asset_location=sample["asset_location"],
        imagery_ref=sample["imagery_ref"],
        layout=sample["layout"],
        testimonial=sample["testimonial"],
        qualifiers=sample["qualifiers"],
        channel=sample["channel"],
        locale=sample["locale"],
        audience=sample["audience"],
        product_version=sample["product_version"],
        jurisdiction=sample["jurisdiction"],
    )

    # Expect express claim + imagery implied claim + testimonial implied claim
    assert len(records) == 3

    # 1. Express Claim
    exp_record = records[0]
    assert exp_record.kind == ClaimKind.EXPLICIT
    assert "reduce wrinkles by 50% in 24 hours" in exp_record.text
    assert len(exp_record.propositions) >= 1
    assert exp_record.qualifiers == sample["qualifiers"]

    # 2. Implied Clinical Endorsement Claim from Imagery
    img_record = records[1]
    assert img_record.kind == ClaimKind.IMPLIED
    assert "clinical" in img_record.text.lower() or "medical" in img_record.text.lower()
    assert img_record.human_review_required is True

    # 3. Implied Therapeutic Claim from Testimonial
    test_record = records[2]
    assert test_record.kind == ClaimKind.IMPLIED
    assert "eczema" in test_record.text.lower()
    assert test_record.human_review_required is True


def test_ingredient_only_evidence_without_bridge_fails_closed(evidence_cases):
    """Task 8: Finished-product claims cannot rely solely on ingredient evidence without an applicable bridge."""
    ing_ev = evidence_cases["claims_regulatory_case"]["ingredient_only_evidence"]
    claim = ClaimRecord(
        id="claim-finished-001",
        version="1.0",
        text="Clinical anti-aging face serum boosts pro-collagen synthesis by 45%.",
        kind=ClaimKind.EXPLICIT,
        asset_ref="asset-carton-01",
        asset_location="Front panel",
        product_version="ederma-serum-v2",
        jurisdiction="US",
        locale="en_US",
        interpretation_reason="Express product claim",
        status=ClaimStatus.NOT_ASSESSED,
        activity_ref="act-01",
    )

    # Map without formulation bridge
    edge, status = ProductClaimsAgent.map_claim_to_evidence(
        claim=claim,
        evidence_item=ing_ev,
        bridge=None,
    )

    assert status == ClaimStatus.INSUFFICIENT
    assert edge.relation == MappingRelation.INCONCLUSIVE
    assert edge.relevance == EvidenceRelevance.BRIDGE_REQUIRED
    assert edge.bridge_ref is None
    assert any("formulation bridge" in lim.lower() for lim in edge.limitations)
    assert claim.human_review_required is True


def test_ingredient_with_valid_bridge_passes(evidence_cases):
    """Task 8: Valid formulation bridge allows evidential linkage with bridge_ref recorded."""
    ing_ev = evidence_cases["claims_regulatory_case"]["ingredient_only_evidence"]
    claim = ClaimRecord(
        id="claim-finished-002",
        version="1.0",
        text="Serum formula containing pro-collagen matrix peptide.",
        kind=ClaimKind.EXPLICIT,
        asset_ref="asset-carton-01",
        asset_location="Front panel",
        product_version="ederma-serum-v2",
        jurisdiction="US",
        locale="en_US",
        interpretation_reason="Express product claim with valid bridge",
        status=ClaimStatus.NOT_ASSESSED,
        activity_ref="act-01",
    )
    bridge = FormulationEvidenceBridge(
        bridge_id="bridge-peptide-serum-01",
        studied_material="Matrix Peptide 2%",
        proposed_product="Finished Serum 2% Peptide",
        overall_relevance=EvidenceRelevance.BRIDGE_REQUIRED,
        scientific_rationale="Matching active concentration and topical vehicle permeability.",
        limits_and_conditions=["Topical delivery matching tested concentration."],
        requires_expert_review=False,
    )

    edge, status = ProductClaimsAgent.map_claim_to_evidence(
        claim=claim,
        evidence_item=ing_ev,
        bridge=bridge,
    )

    assert edge.bridge_ref == "bridge-peptide-serum-01"
    assert edge.relevance == EvidenceRelevance.BRIDGE_REQUIRED


def test_scope_mismatch_magnitude_duration_endpoint_retains_proposal(evidence_cases):
    """Task 7, 9: Magnitude, duration, endpoint overreach requires qualification; original claim text is never replaced."""
    ev = evidence_cases["claims_regulatory_case"]["limited_study_evidence"]
    original_text = "Clinically proven to reduce wrinkles by 50% in 24 hours."
    claim = ClaimRecord(
        id="claim-overreach-001",
        version="1.0",
        text=original_text,
        kind=ClaimKind.EXPLICIT,
        asset_ref="asset-pdp-01",
        asset_location="Front panel",
        product_version="ederma-serum-v2",
        jurisdiction="US",
        locale="en_US",
        interpretation_reason="Express overreaching claim",
        status=ClaimStatus.NOT_ASSESSED,
        activity_ref="act-01",
    )

    edge, status = ProductClaimsAgent.map_claim_to_evidence(
        claim=claim,
        evidence_item=ev,
        bridge=None,
    )

    # 1. Status is qualified support
    assert status == ClaimStatus.QUALIFIED_SUPPORT
    assert edge.relation == MappingRelation.MIXED

    # 2. Original claim text remains intact (NOT silently modified)
    assert claim.text == original_text

    # 3. Proposed narrower wording exists as a proposal
    assert "Proposed qualified wording" in claim.proposed_narrower_wording
    assert "up to 20%" in claim.proposed_narrower_wording

    # 4. Limitations detail magnitude, duration, and endpoint overreach
    assert any("magnitude" in lim.lower() for lim in edge.limitations)
    assert any("duration" in lim.lower() for lim in edge.limitations)
    assert any("endpoint" in lim.lower() for lim in edge.limitations)
    assert claim.human_review_required is True


def test_contradictory_evidence_marks_conflicted_and_escalates():
    """Task 6, 18: Contradictory evidence marks claim CONFLICTED and triggers review."""
    refuting_ev = {
        "id": "ev-null-01",
        "subject": "finished_product",
        "outcome": "No statistically significant difference compared to vehicle control; refutes active efficacy (p=0.62)",
    }
    claim = ClaimRecord(
        id="claim-conflicted-001",
        version="1.0",
        text="Clinically proven active barrier recovery.",
        kind=ClaimKind.EXPLICIT,
        asset_ref="asset-01",
        asset_location="Front panel",
        product_version="1.0",
        jurisdiction="US",
        locale="en_US",
        interpretation_reason="Express efficacy claim",
        status=ClaimStatus.NOT_ASSESSED,
        activity_ref="act-01",
    )

    edge, status = ProductClaimsAgent.map_claim_to_evidence(
        claim=claim,
        evidence_item=refuting_ev,
    )

    assert status == ClaimStatus.CONFLICTED
    assert edge.relation == MappingRelation.REFUTES
    assert claim.human_review_required is True


def _load_run_s_val():
    import importlib.util
    root = Path(__file__).resolve().parents[3]
    script_path = root / "sandbox" / "docker" / "hardened" / "skills" / "s-val" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("s_val_run", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "run_s_val")


def test_claims_offline_isolation_and_s_val_dispatch():
    """Task 20: w_prod.claims runs offline under network_policy: DISABLED."""
    from app.integrations.sandbox.capabilities import PRODUCT_SPECIALIST_POLICIES
    assert PRODUCT_SPECIALIST_POLICIES["w_prod.claims"]["network_policy"] == NetworkPolicy.DISABLED

    agent = ProductClaimsAgent()
    run_s_val = _load_run_s_val()
    agent._sandbox_client = lambda mandate: run_s_val(mandate.payload)

    task = agent.build_task(
        task_id="task-claims-001",
        tenant_id="tenant-derma-01",
        parent_task_id="parent-pe-001",
        operation="map_claim_evidence",
    )

    assert task.specialist_role == SpecialistRole.CLAIMS
    assert task.operation == "map_claim_evidence"
    assert task.delegated_token_limit <= CLAIMS_PROFILE.budget_limit_tokens

    parent_task = ProductEvidenceTask(
        task_id="parent-pe-001",
        tenant_id="tenant-derma-01",
        run_id="run-001",
        parent_grant_ref="grant-derma-001",
        parent_grant_hash="hash-derma-001",
        context_version="1.0",
        context_hash="ctx-claims-001",
        product_version="ederma-serum-v2",
        allowed_s_val_operations=["map_claim_evidence", "extract_claims"],
        budget_limit_tokens=8000,
        deadline_utc=datetime.now(UTC) + timedelta(hours=2),
    )

    # Dispatch via S_VAL
    res = agent.execute_claim_mapping(
        specialist_task=task,
        parent_task=parent_task,
        claims=[
            ClaimRecord(
                id="claim-001",
                text="Hydrates skin for 2 hours.",
                asset_ref="asset-01",
                asset_location="Front",
                status=ClaimStatus.SUPPORTED_IN_SCOPE,
                activity_ref="act-01",
                interpretation_reason="Supported claim",
            )
        ],
    )
    assert res.status == SpecialistResultStatus.COMPLETED
    assert res.typed_findings.get("claim_status") == "SUPPORTED_IN_SCOPE"
