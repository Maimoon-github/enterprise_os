"""Tests for CV-06: Journey Analysis, QA, Provenance, and Final Synthesis.

Validates:
- VOICE-JOURNEY: descriptive comparisons, explicit segments, non-causal disclaimer, evidence grounding.
- VOICE-QA: independent evaluation, non-mutation guarantee, residual-PII block, broken-traceability block.
- Synthesis-only-after-PASS: W_VOICE gate blocks synthesis if QA fails, produces full envelope on PASS.
- W3C PROV lineage: complete entity/activity/agent/relation graph recorded via ProvenanceRecorder.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
import pytest

from app.agents.customer_voice_engine.customer_voice import CustomerVoiceAgent
from app.agents.customer_voice_engine.subagents.journey import VoiceJourneyAgent
from app.agents.customer_voice_engine.subagents.quality import VoiceQualityAgent
from tests.conftest import FakeProvenanceRepository
from app.schemas.agent_contracts import TaskGrant, TenantScope, WorkerRole
from app.schemas.customer_voice import (
    CustomerVoicePayload,
    CustomerVoiceTask,
    JourneyComparison,
    VoiceQAReport,
    VoiceSpecialistResult,
    VoiceWorkflowStage,
)
from app.services.provenance import ProvenanceRecorder


@pytest.fixture
def frozen_voice_corpus():
    """Sanitized records and valid evidence spans."""
    records = [
        {
            "opaque_record_id": "rec-001",
            "sanitized_text": "The delivery was delayed and transit tracking package took two weeks to arrive.",
            "source_type": "review",
            "locale": "en",
            "detected_language": "en",
        },
        {
            "opaque_record_id": "rec-002",
            "sanitized_text": "I was placed on hold for an hour. Support agent was unresponsive to my ticket.",
            "source_type": "support_ticket",
            "locale": "en",
            "detected_language": "en",
        },
    ]
    spans = [
        {
            "record_id": "rec-001",
            "sanitized_text_hash": "hash_rec_001",
            "start_offset": 4,
            "end_offset": 24,
            "span_hash": "hash001",
            "source_ref": "rev-1",
            "exact_quote": "delivery was delayed",
        },
        {
            "record_id": "rec-002",
            "sanitized_text_hash": "hash_rec_002",
            "start_offset": 35,
            "end_offset": 65,
            "span_hash": "hash002",
            "source_ref": "ticket-1",
            "exact_quote": "Support agent was unresponsive",
        },
    ]
    return records, spans


@pytest.mark.asyncio
async def test_voice_journey_descriptive_comparisons_and_non_causal_contract(frozen_voice_corpus):
    """VOICE-JOURNEY produces descriptive comparisons with mandatory non-causal disclaimer."""
    records, spans = frozen_voice_corpus
    agent = VoiceJourneyAgent()
    task = CustomerVoiceTask(
        task_id="task-journey-01",
        tenant_id="tenant-acme",
        objective="channel_journey_comparison",
        source_refs=["rec-001", "rec-002"],
        workflow_stage=VoiceWorkflowStage.JOURNEY,
    )

    result = await agent.execute(
        task=task,
        records=records,
        evidence_spans=spans,
        segments=["enterprise_users", "tier_1"],
        time_interval="2026-Q3",
    )

    assert isinstance(result, VoiceSpecialistResult)
    assert result.specialist_id == "VOICE-JOURNEY"
    assert result.stage == VoiceWorkflowStage.JOURNEY
    assert result.success is True
    assert len(result.findings) > 0

    for comp in result.findings:
        assert isinstance(comp, JourneyComparison)
        assert comp.comparison_type == "descriptive_comparison"
        assert comp.causal_claim_disclaimer == "Descriptive comparison only. No causal relationship inferred."
        assert "enterprise_users" in comp.segment_refs
        assert comp.time_interval == "2026-Q3"
        assert len(comp.evidence_spans) > 0


@pytest.mark.asyncio
async def test_voice_qa_non_mutation_guarantee(frozen_voice_corpus):
    """VOICE-QA verifies candidate inputs are not mutated and pre/post hashes match."""
    records, spans = frozen_voice_corpus
    records_copy = copy.deepcopy(records)
    spans_copy = copy.deepcopy(spans)

    agent = VoiceQualityAgent()
    task = CustomerVoiceTask(
        task_id="task-qa-01",
        tenant_id="tenant-acme",
        objective="quality_evaluation",
        source_refs=["rec-001", "rec-002"],
        workflow_stage=VoiceWorkflowStage.QA,
    )

    result = await agent.execute(
        task=task,
        records=records,
        evidence_spans=spans,
        corpus_hash="canonical_corpus_hash_12345",
    )

    assert result.success is True
    assert result.qa_report is not None
    qa = result.qa_report
    assert isinstance(qa, VoiceQAReport)
    assert qa.status == "PASS"
    assert qa.candidate_input_hash == qa.candidate_output_hash == "canonical_corpus_hash_12345"

    # Strict immutability check
    assert records == records_copy
    assert spans == spans_copy


@pytest.mark.asyncio
async def test_voice_qa_blocks_residual_pii(frozen_voice_corpus):
    """VOICE-QA returns BLOCK when residual unredacted PII is present in candidate data."""
    _, spans = frozen_voice_corpus
    # Unredacted email in text
    leaked_records = [
        {
            "opaque_record_id": "rec-leak",
            "sanitized_text": "Customer contact john.doe@leakedcompany.com had an issue.",
            "source_type": "review",
            "locale": "en",
        }
    ]

    agent = VoiceQualityAgent()
    task = CustomerVoiceTask(
        task_id="task-qa-pii",
        tenant_id="tenant-acme",
        objective="qa_pii_check",
        source_refs=["rec-leak"],
        workflow_stage=VoiceWorkflowStage.QA,
    )

    result = await agent.execute(task=task, records=leaked_records, evidence_spans=spans)

    assert result.success is False
    qa = result.qa_report
    assert qa.status == "BLOCK"
    assert qa.residual_pii_check is False
    assert any("Residual PII" in r for r in qa.block_reasons)


@pytest.mark.asyncio
async def test_voice_qa_blocks_broken_evidence_traceability(frozen_voice_corpus):
    """VOICE-QA returns BLOCK when evidence spans do not resolve to known corpus records."""
    records, _ = frozen_voice_corpus
    # Span points to a non-existent record
    broken_spans = [
        {
            "record_id": "non-existent-rec",
            "sanitized_text_hash": "hash_xyz",
            "start_offset": 0,
            "end_offset": 10,
            "span_hash": "hash_fake",
            "source_ref": "fake_ref",
            "exact_quote": "non-existent",
        }
    ]

    agent = VoiceQualityAgent()
    task = CustomerVoiceTask(
        task_id="task-qa-trace",
        tenant_id="tenant-acme",
        objective="qa_traceability_check",
        source_refs=["rec-001"],
        workflow_stage=VoiceWorkflowStage.QA,
    )

    result = await agent.execute(task=task, records=records, evidence_spans=broken_spans)

    assert result.success is False
    qa = result.qa_report
    assert qa.status == "BLOCK"
    assert qa.evidence_traceability_check is False
    assert any("Broken evidence traceability" in r for r in qa.block_reasons)


@pytest.mark.asyncio
async def test_synthesis_only_after_qa_pass_enforced():
    """W_VOICE halts synthesis and fails closed if QA returns BLOCK."""
    agent = CustomerVoiceAgent()

    # Raw feedback with leaked PII that causes QA to BLOCK
    grant = TaskGrant(
        grant_id="grant-block-test",
        task_id="task-block-test",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        tenant_scope=TenantScope(tenant_id="tenant-123"),
        objective="synthesis_gate_test",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    # Bypass discovery sanitization by mocking a QA agent that blocks
    class BlockingQAAgent:
        SPECIALIST_ID = "VOICE-QA"
        ROLE = VoiceWorkflowStage.QA

        async def execute(self, *args, **kwargs):
            return VoiceSpecialistResult(
                specialist_id="VOICE-QA",
                task_id="task-block-test",
                stage=VoiceWorkflowStage.QA,
                success=False,
                input_hash="fake_hash",
                output_hash="fake_hash",
                qa_report=VoiceQAReport(
                    status="BLOCK",
                    residual_pii_check=False,
                    candidate_input_hash="fake_hash",
                    candidate_output_hash="fake_hash",
                    findings=["Material privacy defect"],
                    block_reasons=["Unsafe PII detected."],
                ),
            )

    agent.qa_agent = BlockingQAAgent()

    context = {
        "items": [
            {"item_id": "item-1", "text": "Valid review text here.", "source_type": "review", "tenant_id": "tenant-123"}
        ]
    }

    envelope = await agent.run(grant=grant, context=context)

    # Synthesis must be halted
    assert envelope.confidence.point_estimate == 0.0
    assert "customer_voice_payload" not in envelope.payload
    assert envelope.payload.get("status") == "block"
    assert envelope.payload.get("qa_verdict") == "BLOCK"
    assert envelope.proposed_state_changes.get("status") == "blocked"


@pytest.mark.asyncio
async def test_w3c_prov_lineage_and_full_synthesis_after_qa_pass():
    """Complete end-to-end CV-06 synthesis with W3C PROV lineage recorded to ProvenanceRecorder."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)
    agent = CustomerVoiceAgent(provenance_recorder=recorder)

    grant = TaskGrant(
        grant_id="grant-cv06-pass",
        task_id="task-cv06-pass",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        tenant_scope=TenantScope(tenant_id="tenant-456"),
        objective="full_synthesis_lineage",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    context = {
        "items": [
            {
                "item_id": "item-rev-1",
                "text": "Shipping was fast and delivery was excellent. Easy setup.",
                "source_type": "review",
                "tenant_id": "tenant-456",
            },
            {
                "item_id": "item-ticket-1",
                "text": "Support response was delayed. Ticket remained open on hold.",
                "source_type": "support_ticket",
                "tenant_id": "tenant-456",
            },
        ],
        "product_id": "prod-xyz",
        "segments": ["active_subscribers"],
        "time_interval": "2026-Q3",
    }

    envelope = await agent.run(grant=grant, context=context)

    # Verify Envelope
    assert envelope.task_id == "task-cv06-pass"
    assert envelope.confidence.point_estimate > 0.0

    # Verify CustomerVoicePayload
    payload = CustomerVoicePayload.model_validate_json(envelope.payload["customer_voice_payload"])
    assert payload.records_analyzed == 2
    assert len(payload.topics) > 0
    assert len(payload.aspect_sentiment) > 0
    assert len(payload.needs_and_objections) > 0
    assert len(payload.journey_comparisons) > 0
    assert payload.qa_report is not None
    assert payload.qa_report.status == "PASS"

    # Verify W3C PROV lineage
    prov_chain = repo._chains.get("tenant-456", [])
    assert len(prov_chain) == 1
    rec = prov_chain[0]
    assert rec.entity_id == "payload:task-cv06-pass"
    assert rec.agent == "W_VOICE"
    assert "entity" in rec.w3c_prov
    assert "activity" in rec.w3c_prov
    assert "wasGeneratedBy" in rec.w3c_prov
    assert "used" in rec.w3c_prov
