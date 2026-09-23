"""Focused contract and boundary tests for CV-01: Customer Voice Boundaries and Data Contracts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.agents.customer_voice import CustomerVoiceAgent
from app.core.exceptions import PolicyViolationError, SandboxInvocationError
from app.integrations.sandbox.capabilities import (
    get_capability_for_role,
    validate_capability_access,
)
from app.schemas.agent_contracts import (
    AnonymizedSentimentVector,
    ConfidenceInterval,
    CustomerVoiceAnalysisResult,
    CustomerVoiceItem,
    EvidenceEnvelope,
    ObjectionProfile,
    SentimentClassification,
    TaskGrant,
)
from app.schemas.customer_voice import (
    VOICE_WORKFLOW_SEQUENCE,
    AspectSentimentFinding,
    CustomerVoicePayload,
    CustomerVoiceTask,
    EvidenceSpan,
    FeedbackRecord,
    JourneyComparison,
    NeedObjectionFinding,
    SurveyMethodology,
    TopicFinding,
    VoiceQAReport,
    VoiceSpecialistResult,
    VoiceSpecialistTask,
    VoiceWorkflowStage,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from tests.conftest import FakeSandboxClient


def test_w_voice_is_zero_sandbox_coordinator() -> None:
    """W_VOICE class has capability = None and rejects sandbox client injection."""
    assert CustomerVoiceAgent.capability is None

    fake_client = FakeSandboxClient()
    with pytest.raises(PolicyViolationError, match="zero-sandbox"):
        CustomerVoiceAgent(sandbox_client=fake_client)

    agent = CustomerVoiceAgent()
    assert agent.capability is None
    assert agent._sandbox_client is None


def test_w_voice_build_payload_raises_policy_violation() -> None:
    """W_VOICE cannot formulate sandbox payloads as it has zero sandbox capability."""
    agent = CustomerVoiceAgent()
    grant = TaskGrant(
        task_id="task-zero-sbx",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        tenant_scope=TenantScope(tenant_id="tenant-1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    with pytest.raises(PolicyViolationError, match="zero sandbox capability"):
        agent.build_payload(grant, {"items": []})


def test_w_voice_coordinator_rejected_by_sandbox_capability_registry() -> None:
    """Invoking sandbox directly as W_VOICE coordinator fails closed."""
    with pytest.raises(SandboxInvocationError, match="zero sandbox authority"):
        validate_capability_access(
            capability=SandboxCapability.PARSE,
            worker_id="W_VOICE",
            operation="default",
        )

    with pytest.raises(SandboxInvocationError, match="zero sandbox authority"):
        validate_capability_access(
            capability=SandboxCapability.PARSE,
            specialist_id="W_VOICE",
            operation="default",
        )

    # get_capability_for_role does not grant direct sandbox to CUSTOMER_VOICE
    with pytest.raises(SandboxInvocationError, match="No sandbox capability authorized"):
        get_capability_for_role(WorkerRole.CUSTOMER_VOICE)


def test_missing_customer_evidence_never_fabricates_default_text() -> None:
    """Absence of feedback items does not fall back to synthetic 'Customer reviews and feedback.' text."""
    agent = CustomerVoiceAgent()
    grant = TaskGrant(
        task_id="task-no-evidence",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    # Normalization returns empty items list, never invented strings
    product_id, items = agent._normalize_context(grant, {})
    assert items == []

    product_id, items = agent._normalize_context(grant, {"query": "Tell me customer sentiment"})
    assert items == []


@pytest.mark.asyncio
async def test_missing_customer_evidence_produces_incomplete_envelope() -> None:
    """Missing customer evidence returns explicit incomplete/needs-context envelope with zero confidence."""
    agent = CustomerVoiceAgent()
    grant = TaskGrant(
        task_id="task-missing-ev",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    envelope = await agent.run(grant, {})
    assert envelope.task_id == "task-missing-ev"
    assert envelope.confidence.point_estimate == 0.0
    assert envelope.proposed_state_changes.get("status") == "needs_context"
    assert any("Missing customer voice evidence" in r for r in envelope.unresolved_risks_or_assumptions)


def test_evidence_span_strict_validation() -> None:
    """EvidenceSpan requires valid offsets and strict fields."""
    span = EvidenceSpan(
        record_id="rec-001",
        sanitized_text_hash=hashlib.sha256(b"sanitized").hexdigest(),
        start_offset=10,
        end_offset=35,
        span_hash=hashlib.sha256(b"shipping was delayed").hexdigest(),
        source_ref="ticket-9982",
        exact_quote="shipping was delayed",
    )
    assert span.start_offset == 10
    assert span.end_offset == 35

    with pytest.raises(ValidationError):
        EvidenceSpan.model_validate(
            {
                "record_id": "rec-001",
                "sanitized_text_hash": "hash",
                "start_offset": -1,  # Invalid
                "end_offset": 10,
                "span_hash": "hash",
                "source_ref": "src",
            }
        )


def test_survey_methodology_disclosure_contract() -> None:
    """SurveyMethodology preserves AAPOR collection mode, sample size, response rate, and weighting."""
    methodology = SurveyMethodology(
        methodology_id="survey-nps-q3",
        population_definition="Subscribed enterprise customers in NA",
        sampling_method="stratified_random",
        sampling_frame="Active CRM customer database",
        collection_mode="web",
        fieldwork_dates=("2026-07-01", "2026-07-15"),
        questionnaire_version="v2.4",
        invited_or_eligible_n=5000,
        completed_n=750,
        response_rate=0.15,
        response_rate_definition="AAPOR RR1",
        weighting_method="post_stratification",
        weight_variables=["tier", "geography"],
        design_effect=1.25,
        precision_method="95% CI (+/- 3.2%)",
    )
    assert methodology.completed_n == 750
    assert methodology.response_rate == 0.15
    assert methodology.design_effect == 1.25


def test_topic_finding_distinguishes_observed_share_from_prevalence() -> None:
    """TopicFinding separates observed sample proportion from population prevalence."""
    topic = TopicFinding(
        topic_id="topic-battery",
        label="Battery Depletion",
        observed_count=42,
        observed_share_of_analyzed_corpus=0.28,
        outlier_or_unassigned_rate=0.04,
        trend="not_assessed",
        inference_scope="observed_feedback_only",
        population_representativeness="not_established",
    )
    assert topic.observed_count == 42
    assert topic.observed_share_of_analyzed_corpus == 0.28
    assert topic.weighted_survey_estimate is None
    assert topic.trend == "not_assessed"
    assert topic.inference_scope == "observed_feedback_only"


def test_aspect_sentiment_finding_and_calibration() -> None:
    """AspectSentimentFinding enforces aspect granularity and explicit calibration indicator."""
    finding = AspectSentimentFinding(
        aspect="billing_transparency",
        polarity="NEGATIVE",
        model_score=-0.82,
        score_is_calibrated=False,
        emotion=["frustration"],
        evidence_spans=[],
        model_version="absa-deberta-v1",
        locale="en",
        uncertainty_reason="Uncalibrated raw model output score",
    )
    assert finding.aspect == "billing_transparency"
    assert finding.score_is_calibrated is False


def test_journey_comparison_requires_descriptive_disclaimer() -> None:
    """JourneyComparison prohibits causal claims and requires descriptive disclaimer."""
    journey = JourneyComparison(
        comparison_id="comp-01",
        channel_or_touchpoint_a="mobile_app",
        channel_or_touchpoint_b="desktop_portal",
        metric_or_dimension="objection_frequency",
        comparison_summary="Observed 30% higher login objections on mobile than desktop.",
    )
    assert journey.comparison_type == "descriptive_comparison"
    assert "Descriptive comparison only. No causal relationship inferred." in journey.causal_claim_disclaimer


def test_voice_qa_report_non_mutating_contract() -> None:
    """VoiceQAReport verifies input and output hashes match and enforces verdict."""
    input_hash = hashlib.sha256(b"corpus-payload").hexdigest()
    qa = VoiceQAReport(
        status="PASS",
        residual_pii_check=True,
        evidence_traceability_check=True,
        bias_check=True,
        contradiction_check=True,
        coverage_check=True,
        schema_validity_check=True,
        candidate_input_hash=input_hash,
        candidate_output_hash=input_hash,  # Non-mutating: hash before == hash after
        findings=["All checks passed clean."],
        reidentification_risk="de_identified_residual_risk_retained",
    )
    assert qa.status == "PASS"
    assert qa.candidate_input_hash == qa.candidate_output_hash


def test_fixed_workflow_sequence_definition() -> None:
    """Fixed Voice DAG sequence is encoded as contract metadata."""
    assert VOICE_WORKFLOW_SEQUENCE[0] == VoiceWorkflowStage.DISCOVERY
    parallel_middle = VOICE_WORKFLOW_SEQUENCE[1]
    assert isinstance(parallel_middle, tuple)
    assert VoiceWorkflowStage.THEMES in parallel_middle
    assert VoiceWorkflowStage.SENTIMENT in parallel_middle
    assert VoiceWorkflowStage.NEEDS in parallel_middle
    assert VOICE_WORKFLOW_SEQUENCE[2] == VoiceWorkflowStage.JOURNEY
    assert VOICE_WORKFLOW_SEQUENCE[3] == VoiceWorkflowStage.QA
    assert VOICE_WORKFLOW_SEQUENCE[4] == VoiceWorkflowStage.SYNTHESIS


def test_customer_voice_payload_and_legacy_compatibility() -> None:
    """CustomerVoicePayload carries typed findings and preserves legacy extraction helpers."""
    agent = CustomerVoiceAgent()

    payload = CustomerVoicePayload(
        task_id="task-final-1",
        tenant_id="tenant-alpha",
        product_ref="prod-123",
        records_analyzed=10,
        inference_scope="observed_feedback_only",
        population_representativeness="not_established",
        reidentification_risk_disclosure="De-identified text carries non-zero residual re-identification risk (NIST IR 8053).",
    )
    assert payload.records_analyzed == 10

    legacy_analysis = CustomerVoiceAnalysisResult(
        analysis_id="cva-1",
        tenant_id="tenant-alpha",
        total_items_analyzed=10,
    )

    envelope = EvidenceEnvelope(
        task_id="task-final-1",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        confidence=ConfidenceInterval(point_estimate=0.85, lower_bound=0.75, upper_bound=0.95),
        evidence=["Analysis complete"],
        payload={
            "customer_voice_payload": payload.model_dump_json(),
            "customer_voice_analysis": legacy_analysis.model_dump_json(),
        },
        findings=["Findings"],
        generated_artifacts=["voice:task-final-1"],
        supporting_evidence=["items_count:10"],
        provenance={"agent": "W_VOICE", "capability": "NONE", "status": "completed"},
        proposed_state_changes={"status": "completed", "capability": "NONE"},
    )

    extracted_payload = agent.extract_customer_voice_payload(envelope)
    assert extracted_payload is not None
    assert extracted_payload.records_analyzed == 10

    extracted_legacy = agent.extract_customer_voice_analysis(envelope)
    assert extracted_legacy is not None
    assert extracted_legacy.total_items_analyzed == 10
