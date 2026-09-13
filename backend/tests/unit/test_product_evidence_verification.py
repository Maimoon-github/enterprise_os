"""Unit tests for T16: Product Formulation, Evidence & Compliance Verification (W_PROD + S_VAL)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agents.product_evidence import ProductEvidenceAgent
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.micro_tools import execute_s_val
from app.schemas.agent_contracts import (
    ClaimValidationStatus,
    ClaimsDossier,
    ProductSpecification,
    TaskGrant,
)
from app.schemas.governance import TenantScope, WorkerRole
from tests.conftest import FakeSandboxClient


def test_s_val_valid_formulation_and_supported_claim() -> None:
    """Valid formulation and matching clinical evidence produces SUPPORTED claim and VALIDATED specification."""
    payload = {
        "task_id": "task-val-101",
        "tenant_id": "acme_beauty",
        "product_id": "prod-serum-v2",
        "product_name": "HydraGlow Advanced Serum",
        "formulation": json.dumps({
            "formulation_id": "form-hg-002",
            "version": "2.1",
            "category": "dermatological_serum",
            "dosage_form": "liquid_topical",
            "attributes": {
                "ph_level": "5.5",
                "shelf_life_months": 24,
                "target_skin_types": ["dry", "sensitive"],
            },
            "ingredients": [
                {"name": "Water/Aqua", "percentage": 78.5, "function": "solvent"},
                {"name": "Hyaluronic Acid", "percentage": 2.0, "function": "active_humectant"},
                {"name": "Niacinamide", "percentage": 5.0, "function": "active_brightener"},
                {"name": "Glycerin", "percentage": 10.0, "function": "humectant"},
                {"name": "Phenoxyethanol", "percentage": 0.5, "function": "preservative"},
                {"name": "Botanical Extracts", "percentage": 4.0, "function": "active_soothing"},
            ],
        }),
        "claims": json.dumps([
            {
                "id": "claim-hg-1",
                "text": "Clinically proven to increase skin hydration by 42% over 28 days. *Results based on clinical trial of 50 participants.",
                "category": "clinical_efficacy",
                "evidence_ids": ["doc-clin-001"],
            }
        ]),
        "evidence": json.dumps([
            {
                "doc_id": "doc-clin-001",
                "text": "Double-blind clinical study with 50 female participants demonstrated a 42% increase in epidermal hydration after 28 days of twice-daily topical application. Hyaluronic acid and niacinamide combination confirmed statistically significant improvement (p < 0.01).",
                "source": "clinical_trial_dossier_ct2026_44.pdf",
                "provenance_hash": "a1b2c3d4e5f67890",
                "is_stale": False,
                "contradicts": False,
            }
        ]),
        "required_disclaimer": "*Results based on clinical trial",
    }

    result = execute_s_val(payload)

    assert result["status"] == "success"
    assert result["is_compliant"] == "True"
    assert float(result["compliance_score"]) >= 0.9

    # Verify Product Specification JSON
    spec_data = json.loads(result["product_specification"])
    spec = ProductSpecification.model_validate(spec_data)
    assert spec.product_id == "prod-serum-v2"
    assert spec.product_name == "HydraGlow Advanced Serum"
    assert spec.validation_status == "VALIDATED"
    assert len(spec.ingredients) == 6
    assert "doc-clin-001" in spec.supporting_evidence_references

    # Verify Claims Dossier JSON
    dossier_data = json.loads(result["claims_dossier"])
    dossier = ClaimsDossier.model_validate(dossier_data)
    assert dossier.total_claims == 1
    assert dossier.supported_claims == 1
    assert dossier.rejected_claims == 0
    assert dossier.summary_status == "APPROVED"

    claim_entry = dossier.claims[0]
    assert claim_entry.claim_id == "claim-hg-1"
    assert claim_entry.validation_status == ClaimValidationStatus.SUPPORTED
    assert claim_entry.confidence >= 0.8
    assert "doc-clin-001" in claim_entry.evidence_references


def test_s_val_unsupported_claim_insufficient_evidence() -> None:
    """A claim lacking supporting evidence in the authorized context is classified as INSUFFICIENT_EVIDENCE."""
    payload = {
        "task_id": "task-val-102",
        "tenant_id": "acme_beauty",
        "product_id": "prod-serum-v2",
        "claims": json.dumps([
            {
                "id": "claim-unsupported",
                "text": "Reduces deep forehead wrinkles in under 48 hours.",
                "category": "anti_aging",
            }
        ]),
        "evidence": json.dumps([
            {
                "doc_id": "doc-moisturize-only",
                "text": "Formula maintains skin surface barrier hydration.",
                "source": "lab_notes_2026.pdf",
            }
        ]),
    }

    result = execute_s_val(payload)

    dossier = ClaimsDossier.model_validate_json(result["claims_dossier"])
    assert dossier.total_claims == 1
    assert dossier.supported_claims == 0
    assert dossier.insufficient_claims == 1
    assert dossier.summary_status == "FLAGGED"

    claim = dossier.claims[0]
    assert claim.validation_status == ClaimValidationStatus.INSUFFICIENT_EVIDENCE
    assert claim.confidence <= 0.2
    assert any("No supporting evidence" in w for w in claim.limitations_or_warnings)


def test_s_val_contradictory_evidence_classified_conflicting() -> None:
    """When clinical evidence contradicts the proposed marketing claim, it must be classified as CONFLICTING_EVIDENCE."""
    payload = {
        "task_id": "task-val-103",
        "tenant_id": "acme_wellness",
        "product_id": "prod-joint-relief",
        "claims": json.dumps([
            {
                "id": "claim-joint",
                "text": "Significantly accelerates joint cartilage regeneration and relieves joint pain in 7 days.",
                "category": "clinical_efficacy",
                "evidence_ids": ["doc-joint-study"],
            }
        ]),
        "evidence": json.dumps([
            {
                "doc_id": "doc-joint-study",
                "text": "Independent randomized trial failed to show significant cartilage regeneration. No statistically meaningful difference from placebo observed in 7-day joint pain endpoint; adverse reaction reported in 8% of patients.",
                "contradicts": True,
            }
        ]),
    }

    result = execute_s_val(payload)

    assert result["is_compliant"] == "False"
    dossier = ClaimsDossier.model_validate_json(result["claims_dossier"])
    assert dossier.conflicting_claims == 1
    assert dossier.supported_claims == 0

    claim = dossier.claims[0]
    assert claim.validation_status == ClaimValidationStatus.CONFLICTING_EVIDENCE
    assert "doc-joint-study" in claim.contradicting_evidence_references
    assert claim.confidence <= 0.3


def test_s_val_stale_evidence_requires_review() -> None:
    """Evidence marked as stale or expired results in REQUIRES_REVIEW and must not be approved."""
    payload = {
        "task_id": "task-val-104",
        "tenant_id": "acme_pharma",
        "product_id": "prod-vitamin-d",
        "claims": json.dumps([
            {
                "id": "claim-d3",
                "text": "Clinically proven to maintain healthy vitamin D levels.",
                "evidence_ids": ["doc-stale-2018"],
            }
        ]),
        "evidence": json.dumps([
            {
                "doc_id": "doc-stale-2018",
                "text": "Study from 2018 confirmed vitamin D levels in elderly patients.",
                "is_stale": True,
            }
        ]),
    }

    result = execute_s_val(payload)

    dossier = ClaimsDossier.model_validate_json(result["claims_dossier"])
    assert dossier.supported_claims == 0
    assert dossier.requires_review_claims == 1

    claim = dossier.claims[0]
    assert claim.validation_status == ClaimValidationStatus.REQUIRES_REVIEW
    assert any("stale" in w.lower() for w in claim.limitations_or_warnings)


def test_s_val_prohibited_absolutes_rejected() -> None:
    """Claims claiming cures, 100% guarantees, or permanent elimination are REJECTED."""
    payload = {
        "task_id": "task-val-105",
        "tenant_id": "acme_care",
        "claims": json.dumps([
            {
                "id": "claim-cure",
                "text": "Our revolutionary formula cures arthritis and 100% guaranteed prevents all joint inflammation.",
            }
        ]),
    }

    result = execute_s_val(payload)

    assert result["is_compliant"] == "False"
    dossier = ClaimsDossier.model_validate_json(result["claims_dossier"])
    assert dossier.rejected_claims == 1
    assert dossier.supported_claims == 0
    assert dossier.summary_status == "REJECTED"

    claim = dossier.claims[0]
    assert claim.validation_status == ClaimValidationStatus.REJECTED
    assert claim.confidence == 0.0
    assert any("Prohibited absolute" in v for v in claim.violations)


def test_s_val_quantitative_claim_lacks_disclaimer_requires_review() -> None:
    """A quantitative claim (e.g. 50% faster) missing a statutory disclaimer footnote is flagged."""
    payload = {
        "task_id": "task-val-106",
        "claim": "Proven to increase cell renewal by 55% in two weeks.",
        "required_disclaimer": "*Results based on in-vitro lab testing.",
    }

    result = execute_s_val(payload)

    violations = json.loads(result["violations"])
    assert any("statutory disclaimer" in v.lower() for v in violations)
    dossier = ClaimsDossier.model_validate_json(result["claims_dossier"])
    assert dossier.claims[0].validation_status in (
        ClaimValidationStatus.REQUIRES_REVIEW,
        ClaimValidationStatus.REJECTED,
    )


def test_s_val_formulation_percentage_overflow() -> None:
    """Formulation whose ingredient percentages exceed 100% is flagged with INCOMPLETE_SPECIFICATION."""
    payload = {
        "task_id": "task-val-107",
        "product_id": "prod-bad-formula",
        "formulation": json.dumps({
            "product_id": "prod-bad-formula",
            "product_name": "Overloaded Formula",
            "ingredients": [
                {"name": "Base", "percentage": 80.0},
                {"name": "Active A", "percentage": 30.0},
                {"name": "Active B", "percentage": 15.0},
            ],
        }),
    }

    result = execute_s_val(payload)

    spec = ProductSpecification.model_validate_json(result["product_specification"])
    assert spec.validation_status == "INCOMPLETE_SPECIFICATION"
    assert any("exceeds 100.0%" in v for v in spec.compliance_findings)


def test_s_val_negative_ingredient_concentration() -> None:
    """Negative ingredient concentration is detected as a violation."""
    payload = {
        "task_id": "task-val-108",
        "product_id": "prod-neg-ing",
        "formulation": json.dumps({
            "product_id": "prod-neg-ing",
            "product_name": "Erroneous Formula",
            "ingredients": [
                {"name": "Water", "percentage": 105.0},
                {"name": "Contaminant", "percentage": -5.0},
            ],
        }),
    }

    result = execute_s_val(payload)

    violations = json.loads(result["violations"])
    assert any("Negative ingredient concentration" in v for v in violations)


def test_s_val_malformed_input_fails_safely() -> None:
    """Malformed or empty JSON payloads in S_VAL do not crash and return a structured fallback."""
    payload = {
        "task_id": "task-val-err",
        "claims": "not-valid-json-{{{",
        "formulation": "also-not-valid-json",
    }

    result = execute_s_val(payload)

    assert "task_id" in result
    assert "claims_dossier" in result
    assert "product_specification" in result
    dossier = ClaimsDossier.model_validate_json(result["claims_dossier"])
    assert dossier.total_claims == 1


def test_w_prod_tenant_scope_mismatch_fails_closed() -> None:
    """W_PROD fails closed if evidence belonging to another tenant is injected into context."""
    agent = ProductEvidenceAgent(FakeSandboxClient())
    grant = TaskGrant(
        task_id="task-prod-tenant-1",
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        tenant_scope=TenantScope(tenant_id="tenant_alpha"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    # Context contains off-tenant evidence
    context: dict[str, object] = {
        "evidence": [
            {"doc_id": "ev-foreign", "tenant_id": "tenant_beta", "text": "Foreign proprietary trial"}
        ]
    }

    with pytest.raises(ValueError, match="Tenant isolation breach in evidence context"):
        agent.build_payload(grant, context)


@pytest.mark.asyncio
async def test_w_prod_sandbox_execution_failure_returns_zero_confidence() -> None:
    """When the sandbox execution fails, W_PROD returns an EvidenceEnvelope with zero confidence and risk note."""
    failing_sandbox = FakeSandboxClient(should_fail=True)
    agent = ProductEvidenceAgent(failing_sandbox)
    grant = TaskGrant(
        task_id="task-prod-fail",
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    envelope = await agent.run(grant, context={})

    assert envelope.task_id == "task-prod-fail"
    assert envelope.confidence.point_estimate == 0.0
    assert any("failure" in r.lower() or "failed" in r.lower() for r in envelope.unresolved_risks_or_assumptions)


@pytest.mark.asyncio
async def test_w_prod_full_verification_and_envelope_generation() -> None:
    """Full execution of W_PROD using real SandboxClient produces verified artifacts and typed models."""
    sandbox_client = SandboxClient()
    agent = ProductEvidenceAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-wprod-live",
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        tenant_scope=TenantScope(tenant_id="luxe_care"),
        brand_id="luxe_care",
        objective="Verify anti-aging formulation and clinical claims",
        validated_evidence=[
            {
                "doc_id": "ev-pep-10",
                "tenant_id": "luxe_care",
                "text": "Study of Matrixyl 3000 peptide complex in Luxe Care serum showed 35% wrinkle reduction over 60 days in human trial.",
                "source": "clinical_study_2026.pdf",
            }
        ],
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    context: dict[str, object] = {
        "product_id": "prod-luxe-01",
        "product_name": "Luxe Peptide Restorative Serum",
        "formulation": {
            "formulation_id": "form-luxe-01",
            "version": "1.0",
            "attributes": {"category": "anti_aging_serum", "volume_ml": 50},
            "ingredients": [
                {"name": "Water", "percentage": 85.0},
                {"name": "Matrixyl 3000 Peptide", "percentage": 5.0},
                {"name": "Hyaluronic Acid", "percentage": 2.0},
                {"name": "Excipients", "percentage": 8.0},
            ],
        },
        "claims": [
            {
                "id": "claim-pep",
                "text": "Peptide complex demonstrated 35% wrinkle reduction over 60 days. *Results based on human clinical trial.",
                "category": "clinical_efficacy",
                "evidence_ids": ["ev-pep-10"],
            }
        ],
        "required_disclaimer": "*Results based on human clinical trial.",
    }

    envelope = await agent.run(grant, context)

    assert envelope.task_id == "task-wprod-live"
    assert envelope.worker_role == WorkerRole.PRODUCT_EVIDENCE
    assert envelope.confidence.point_estimate >= 0.85

    # Check generated artifacts
    assert "dossier:task-wprod-live" in envelope.generated_artifacts
    assert "spec:task-wprod-live" in envelope.generated_artifacts

    # Check typed models extraction
    spec = agent.extract_product_specification(envelope)
    assert spec is not None
    assert spec.product_id == "prod-luxe-01"
    assert spec.validation_status == "VALIDATED"

    dossier = agent.extract_claims_dossier(envelope)
    assert dossier is not None
    assert dossier.total_claims == 1
    assert dossier.supported_claims == 1
    assert dossier.claims[0].validation_status == ClaimValidationStatus.SUPPORTED
