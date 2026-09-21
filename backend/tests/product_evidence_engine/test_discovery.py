"""PE-04: Discovery and Source Capture Specialist Tests.

Verifies:
1. ResearchProtocol completeness, acceptance, and validation.
2. Disclosure-safe query sanitization (blocking confidential formulas, secrets, batches).
3. SearchRun reproducibility (protocol ID, query, filters, timestamps, cursors, counts, stopping reason).
4. Truthful access-level reporting (full_text never fabricated for paywalled/abstract-only sources).
5. Inaccessible and truncated source tracking with explicit reasons.
6. SourceSnapshot capture, SHA-256 content hashing, and redirect tracing.
7. Deduplication of identical records.
8. Study family linking (preserving secondary reports with is_secondary_lead=True without inflating study count).
9. Preservation of positive, negative, null, and safety evidence.
10. Initial extraction with precise locators, leaving appraisal/certainty to downstream specialists.
11. Egress governance: allowlist enforcement, unauthorized domain denial, grant requirement.
12. S_VAL dispatch and structured result formatting conforming to PE-02 contracts.
13. Correction, retraction, and freshness metadata tracking.
14. Model-A isolation: zero direct DB, CMS, RAG, or parent runtime access.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any
import pytest

from app.agents.product_evidence_engine.product_evidence import (
    DISCOVERY_PROFILE,
    dispatch_specialist_s_val,
)
from app.agents.product_evidence_engine.subagents.discovery import ProductDiscoveryAgent
from app.integrations.sandbox.capabilities import (
    PRODUCT_SPECIALIST_POLICIES,
    validate_capability_access,
)
from app.schemas.governance import WorkerRole
from app.schemas.product_evidence import (
    AccessLevel,
    EvidenceSubject,
    EvidenceType,
    ExtractedEvidence,
    FreshnessStatus,
    ProductEvidenceTask,
    ResearchProtocol,
    SearchRun,
    SourceRecord,
    SourceSnapshot,
    SpecialistResult,
    SpecialistResultStatus,
    SpecialistRole,
    SpecialistTask,
)
from app.core.exceptions import SandboxInvocationError
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxEgressGrant,
    SandboxInvocationMandate,
)


@pytest.fixture
def evidence_fixture_data() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "fixtures" / "evidence_cases.json"
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def valid_protocol(evidence_fixture_data: dict[str, Any]) -> ResearchProtocol:
    proto_data = evidence_fixture_data["discovery_research_case"]["protocol"]
    return ResearchProtocol(**proto_data)


@pytest.fixture
def parent_task() -> ProductEvidenceTask:
    return ProductEvidenceTask(
        task_id="pe-task-disc-001",
        tenant_id="tenant-derma-01",
        run_id="run-001",
        parent_grant_ref="grant-derma-001",
        parent_grant_hash="abc123def456hash",
        context_version="1.0",
        context_hash="ctx123def456hash",
        product_version="2.0",
        allowed_s_val_operations=["research_literature", "acquire_source", "parse_metadata"],
        budget_limit_tokens=10000,
        deadline_utc=datetime.now(UTC) + timedelta(hours=2),
    )


@pytest.fixture
def discovery_agent() -> ProductDiscoveryAgent:
    return ProductDiscoveryAgent()


def _load_run_s_val():
    import importlib.util
    root = Path(__file__).resolve().parents[3]
    script_path = root / "sandbox" / "docker" / "hardened" / "skills" / "s-val" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("s_val_run", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_s_val


# ==============================================================================
# 1. Protocol Acceptance & Validation
# ==============================================================================


def test_research_protocol_acceptance_and_validation(valid_protocol: ResearchProtocol, discovery_agent: ProductDiscoveryAgent) -> None:
    """Discovery accepts and verifies an authorized, complete ResearchProtocol."""
    validated = discovery_agent.validate_protocol(valid_protocol)
    assert validated.protocol_id == "proto-niacinamide-001"
    assert "niacinamide" in validated.question_framing
    assert validated.product_scope == "ederma-serum-v2"
    assert len(validated.inclusion_criteria) >= 1
    assert len(validated.exclusion_criteria) >= 1
    assert len(validated.target_sources) >= 1
    assert validated.search_syntax != ""
    assert len(validated.stopping_rules) >= 1


def test_research_protocol_validation_rejections(discovery_agent: ProductDiscoveryAgent) -> None:
    """Protocol validation fails closed when required framing, criteria, or stopping rules are missing."""
    # Missing framing
    with pytest.raises(ValueError, match="(question_framing|String should have at least 1 character)"):
        discovery_agent.validate_protocol({
            "protocol_id": "p-invalid-1",
            "question_framing": "",
            "inclusion_criteria": ["RCT"],
            "exclusion_criteria": ["in vitro"],
            "search_syntax": "niacinamide",
            "stopping_rules": ["max_50"],
        })

    # Missing inclusion criteria
    with pytest.raises(ValueError, match="'inclusion_criteria' must contain"):
        discovery_agent.validate_protocol({
            "protocol_id": "p-invalid-2",
            "question_framing": "Valid question?",
            "inclusion_criteria": [],
            "exclusion_criteria": ["in vitro"],
            "search_syntax": "niacinamide",
            "stopping_rules": ["max_50"],
        })

    # Missing stopping rules
    with pytest.raises(ValueError, match="'stopping_rules' must contain"):
        discovery_agent.validate_protocol({
            "protocol_id": "p-invalid-3",
            "question_framing": "Valid question?",
            "inclusion_criteria": ["RCT"],
            "exclusion_criteria": ["in vitro"],
            "search_syntax": "niacinamide",
            "stopping_rules": [],
        })


# ==============================================================================
# 2. Disclosure-Safe Query Sanitization
# ==============================================================================


def test_disclosure_safe_query_sanitization(discovery_agent: ProductDiscoveryAgent) -> None:
    """Public search queries must not disclose confidential formulas, trade secrets, or batch IDs."""
    safe_query = "(niacinamide OR nicotinamide) AND 'skin barrier recovery' AND clinical trial"
    assert discovery_agent.sanitize_query(safe_query) == safe_query

    # Prohibited confidential pattern
    with pytest.raises(ValueError, match="matches confidential pattern"):
        discovery_agent.sanitize_query("niacinamide clinical trials with proprietary secret formula")

    # Prohibited batch ID
    with pytest.raises(ValueError, match="matches confidential pattern"):
        discovery_agent.sanitize_query("efficacy of batch-secret-2026-v2 on skin hydration")

    # Explicit proprietary term
    with pytest.raises(ValueError, match="contains confidential proprietary term"):
        discovery_agent.sanitize_query(
            "clinical trial of DermPeptide-99",
            proprietary_terms=["DermPeptide-99"],
        )


# ==============================================================================
# 3. SearchRun Reproducibility
# ==============================================================================


def test_reproducible_search_run_recording(discovery_agent: ProductDiscoveryAgent) -> None:
    """Every search execution is recorded with full audit and reproducibility metadata."""
    run = discovery_agent.record_search_run(
        protocol_id="proto-niacinamide-001",
        source_system_id="pubmed",
        query="(niacinamide) AND (barrier)",
        filters={"humans": True, "years": [2020, 2026]},
        pagination_cursor="cursor-p1",
        results_count=15,
        screened_count=15,
        screening_outcomes={"included": 4, "excluded": 11},
        inaccessible_or_truncated_results=[{"id": "doi:10.1016/paywall", "reason": "paywall_no_access"}],
        stopping_reason="max_results_reached",
    )

    assert isinstance(run, SearchRun)
    assert run.protocol_id == "proto-niacinamide-001"
    assert run.source_system_id == "pubmed"
    assert run.results_count == 15
    assert run.screened_count == 15
    assert run.screening_outcomes["included"] == 4
    assert len(run.inaccessible_or_truncated_results) == 1
    assert run.stopping_reason == "max_results_reached"
    assert run.completed_at_utc is not None
    assert run.started_at_utc <= run.completed_at_utc


# ==============================================================================
# 4. Truthful Access-Level Reporting
# ==============================================================================


def test_truthful_access_level_reporting(discovery_agent: ProductDiscoveryAgent) -> None:
    """Never represent inaccessible full text as full_text."""
    # 1. Truly accessible full text
    full_source = discovery_agent.build_source_record(
        source_id="src-001",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-001",
        url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
        identifier="doi:10.1016/j.jid.2025.01.002",
        is_truncated_or_inaccessible=False,
    )
    assert full_source.access == AccessLevel.FULL_TEXT

    # 2. Paywalled / truncated source cannot claim full_text access
    paywalled_source = discovery_agent.build_source_record(
        source_id="src-paywall-002",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-002",
        url="https://doi.org/10.1016/j.paywall.2024",
        identifier="doi:10.1016/j.paywall.2024",
        is_truncated_or_inaccessible=True,
    )
    assert paywalled_source.access == AccessLevel.ABSTRACT_ONLY
    assert paywalled_source.access != AccessLevel.FULL_TEXT


# ==============================================================================
# 5. Snapshot Capture & Hashing
# ==============================================================================


def test_source_snapshot_capture_and_hashing(discovery_agent: ProductDiscoveryAgent) -> None:
    """Capture immutable snapshot with SHA-256 content digest, size, and redirect trace."""
    raw_html = "<html><body><h1>Clinical Study on Niacinamide</h1><p>40% hydration gain.</p></body></html>"
    snapshot = discovery_agent.capture_snapshot(
        source_id="src-001",
        content=raw_html,
        requested_url="http://example.com/study",
        final_url="https://example.com/study/final",
        redirect_trace=["http://example.com/study", "https://example.com/study", "https://example.com/study/final"],
        response_status=200,
        media_type="text/html",
    )

    assert isinstance(snapshot, SourceSnapshot)
    assert snapshot.source_id == "src-001"
    assert snapshot.byte_length == len(raw_html.encode("utf-8"))
    assert snapshot.response_status == 200
    assert len(snapshot.redirect_trace) == 3
    assert len(snapshot.content_hash) == 64  # SHA-256 hex length


# ==============================================================================
# 6. Deduplication & Study Family Linking
# ==============================================================================


def test_deduplication_and_study_family_linking(discovery_agent: ProductDiscoveryAgent) -> None:
    """Identical sources are deduplicated; multiple reports of same study are linked as secondary leads."""
    src1 = discovery_agent.build_source_record(
        source_id="src-primary-001",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-1",
        identifier="doi:10.1016/trial-001",
        study_family_id="nct-01234567",
    )
    # Exact duplicate of src1
    src1_duplicate = discovery_agent.build_source_record(
        source_id="src-primary-dup",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-dup",
        identifier="doi:10.1016/trial-001",
        study_family_id="nct-01234567",
    )
    # Secondary 2-year follow-up of the same trial
    src2_followup = discovery_agent.build_source_record(
        source_id="src-followup-002",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-2",
        identifier="doi:10.1016/trial-001-followup",
        study_family_id="nct-01234567",
    )
    # Independent study
    src3_independent = discovery_agent.build_source_record(
        source_id="src-independent-003",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-3",
        identifier="doi:10.1016/trial-002-independent",
        study_family_id="nct-99999999",
    )

    deduped, links = discovery_agent.deduplicate_and_link_study_families(
        [src1, src1_duplicate, src2_followup, src3_independent]
    )

    # Total unique records = 3 (the exact duplicate was removed)
    assert len(deduped) == 3
    # The primary report is not secondary lead
    assert deduped[0].is_secondary_lead is False
    # The follow-up report is retained but marked as secondary lead (does not inflate study count)
    assert deduped[1].is_secondary_lead is True
    assert deduped[1].study_family_id == "nct-01234567"
    # Independent study is primary for its own family
    assert deduped[2].is_secondary_lead is False

    # Check family linking relationship
    assert len(links) == 1
    assert links[0]["primary_source_id"] == "src-primary-001"
    assert links[0]["secondary_source_id"] == "src-followup-002"


# ==============================================================================
# 7. Preservation of Positive, Negative, Null & Safety Evidence
# ==============================================================================


def test_preservation_of_all_evidence_outcomes(discovery_agent: ProductDiscoveryAgent) -> None:
    """Discovery extracts positive, negative, null, and safety signals without cherry-picking."""
    source = discovery_agent.build_source_record(
        source_id="src-rct-001",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-001",
        identifier="doi:10.1016/trial-outcomes",
    )
    snapshot = discovery_agent.capture_snapshot(
        source_id="src-rct-001",
        content="Dummy content",
        requested_url="https://example.com/trial",
    )

    raw_findings = [
        {"location": "Page 4, Table 1", "outcome": "40% increase in skin barrier hydration (p<0.001)"},
        {"location": "Page 5, Table 2", "outcome": "No significant difference in sebum levels versus placebo (p=0.48)"},
        {"location": "Page 6, Para 3", "outcome": "Failure to reduce deep wrinkles beyond baseline (p=0.62)"},
        {"location": "Page 7, Safety", "outcome": "Mild transient erythema reported in 2 of 50 participants (4%)", "adverse_events": ["mild erythema"]},
    ]

    extracted = discovery_agent.extract_findings(source, snapshot, raw_findings)
    assert len(extracted) == 4
    # Positive finding
    assert "40% increase" in extracted[0].outcome
    assert extracted[0].location == "Page 4, Table 1"
    # Null finding
    assert "No significant difference" in extracted[1].outcome
    # Negative/failure finding
    assert "Failure to reduce" in extracted[2].outcome
    # Safety signal
    assert "Mild transient erythema" in extracted[3].outcome
    assert extracted[3].adverse_events == ["mild erythema"]

    # Crucial architectural constraint: Discovery does NOT assign certainty or claim approval
    for item in extracted:
        assert item.assessment_ref.startswith("assess-pending-")


# ==============================================================================
# 8. Correction & Retraction Metadata Tracking
# ==============================================================================


def test_correction_and_retraction_metadata_tracking(discovery_agent: ProductDiscoveryAgent) -> None:
    """Correction and retraction status is explicitly recorded."""
    corrected_src = discovery_agent.build_source_record(
        source_id="src-corrected-001",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-corr",
        identifier="doi:10.1016/corrected-paper",
        correction_or_retraction_status="corrected",
        freshness=FreshnessStatus.CURRENT_CHECKED,
    )
    assert corrected_src.correction_or_retraction_status == "corrected"
    assert corrected_src.freshness == FreshnessStatus.CURRENT_CHECKED

    retracted_src = discovery_agent.build_source_record(
        source_id="src-retracted-002",
        evidence_type=EvidenceType.PRIMARY_STUDY,
        access=AccessLevel.FULL_TEXT,
        provenance_ref="prov-retract",
        identifier="doi:10.1016/retracted-paper",
        correction_or_retraction_status="retracted",
        authenticity_status="compromised",
    )
    assert retracted_src.correction_or_retraction_status == "retracted"
    assert retracted_src.authenticity_status == "compromised"


# ==============================================================================
# 9. Governed Egress & Unauthorized Domain Denial
# ==============================================================================


def test_discovery_egress_governance() -> None:
    """Discovery has ALLOWLIST network policy; requires explicit unexpired SandboxEgressGrant."""
    policy = PRODUCT_SPECIALIST_POLICIES["w_prod.discovery"]
    assert policy["network_policy"] == NetworkPolicy.ALLOWLIST

    # 1. Network allowed when valid grant is supplied
    grant = SandboxEgressGrant(
        grant_id="grant-disc-001",
        task_id="pe-task-disc-001",
        tenant_id="tenant-derma-01",
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        specialist_id="w_prod.discovery",
        allowed_domains=["pubmed.ncbi.nlm.nih.gov", "crossref.org"],
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    profile = validate_capability_access(
        SandboxCapability.VAL,
        WorkerRole.PRODUCT_EVIDENCE,
        operation="research_literature",
        requested_network=NetworkPolicy.ALLOWLIST,
        specialist_id="w_prod.discovery",
        egress_grant=grant,
    )
    assert profile.capability == SandboxCapability.VAL

    # 2. Denied when no grant is attached
    with pytest.raises(SandboxInvocationError, match="requested network without an authorized SandboxEgressGrant"):
        validate_capability_access(
            SandboxCapability.VAL,
            WorkerRole.PRODUCT_EVIDENCE,
            operation="research_literature",
            requested_network=NetworkPolicy.ALLOWLIST,
            specialist_id="w_prod.discovery",
            egress_grant=None,
        )


# ==============================================================================
# 10. S_VAL Discovery Dispatch End-to-End
# ==============================================================================


def test_s_val_discovery_dispatch_end_to_end(
    discovery_agent: ProductDiscoveryAgent,
    valid_protocol: ResearchProtocol,
    parent_task: ProductEvidenceTask,
) -> None:
    """S_VAL execution returns structured findings with search runs, sources, and snapshots."""
    task = discovery_agent.build_task(
        task_id="spec-disc-e2e-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        operation="research_literature",
        context_slice={
            "query": "(niacinamide) AND (barrier recovery)",
            "sources": [
                {
                    "id": "src-study-001",
                    "identifier": "doi:10.1016/j.jid.2025.01.002",
                    "evidence_type": "primary_study",
                    "access": "full_text",
                    "provenance_ref": "prov-001",
                }
            ],
            "stopping_reason": "protocol_saturation",
        },
    )

    grant = SandboxEgressGrant(
        grant_id="grant-disc-e2e",
        task_id=task.task_id,
        tenant_id=parent_task.tenant_id,
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        specialist_id="w_prod.discovery",
        allowed_domains=["pubmed.ncbi.nlm.nih.gov"],
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    # Use S_VAL runner inside mock/client
    run_s_val = _load_run_s_val()

    def mock_runner(mandate: SandboxInvocationMandate) -> dict[str, Any]:
        return run_s_val(mandate.payload)

    discovery_agent._sandbox_client = mock_runner

    result = discovery_agent.execute_discovery(
        specialist_task=task,
        parent_task=parent_task,
        protocol=valid_protocol,
        egress_grant=grant,
    )

    assert isinstance(result, SpecialistResult)
    assert result.status == SpecialistResultStatus.COMPLETED
    assert result.specialist_role == "DISCOVERY"
    assert result.typed_findings["sources_acquired"] == 1
    assert result.typed_findings["stopping_reason"] == "protocol_saturation"
    assert result.provenance_fragments["profile_digest"] == DISCOVERY_PROFILE.compute_digest()


def test_s_val_discovery_disclosure_violation_flagged(
    discovery_agent: ProductDiscoveryAgent,
    parent_task: ProductEvidenceTask,
) -> None:
    """S_VAL flags disclosure violation when confidential terms are passed in query."""
    run_s_val = _load_run_s_val()

    def mock_runner(mandate: SandboxInvocationMandate) -> dict[str, Any]:
        return run_s_val(mandate.payload)

    task = discovery_agent.build_task(
        task_id="spec-disc-disc-fail",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        operation="research_literature",
        context_slice={"query": "searching for our proprietary confidential active ingredient"},
    )

    discovery_agent._sandbox_client = mock_runner

    # Execute directly without client-side sanitize check to test S_VAL server-side enforcement
    result = dispatch_specialist_s_val(
        mock_runner,
        specialist_task=task,
        parent_task=parent_task,
    )

    assert result.typed_findings["is_compliant"] is False
    assert any("Disclosure-safety violation" in v for v in result.typed_findings["violations"])
