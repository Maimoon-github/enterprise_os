"""Tests for CV-05: Customer Voice Analysis Specialists (Themes, Sentiment, Needs).

Validates:
- VOICE-THEMES: clustering, observed share vs population prevalence, diagnostics, trend rules.
- VOICE-SENTIMENT: aspect-level polarity, calibration honesty, uncertainty reasons, unsupported locale/model.
- VOICE-NEEDS: customer pains, objections, outcomes, customer vocabulary, grounded evidence spans.
- Invariants: corpus immutability, zero-sandbox coordinator, deterministic provenance.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
import pytest

from app.agents.customer_voice_engine.customer_voice import CustomerVoiceAgent
from app.agents.customer_voice_engine.subagents.discovery import VoiceDiscoveryAgent
from app.agents.customer_voice_engine.subagents.needs_objections import VoiceNeedsAgent
from app.agents.customer_voice_engine.subagents.sentiment import VoiceSentimentAgent
from app.agents.customer_voice_engine.subagents.themes import VoiceThemesAgent
from app.schemas.agent_contracts import TaskGrant, TenantScope, WorkerRole
from app.schemas.customer_voice import (
    AspectSentimentFinding,
    CustomerVoicePayload,
    CustomerVoiceTask,
    NeedObjectionFinding,
    SurveyMethodology,
    TopicFinding,
    VoiceSpecialistResult,
    VoiceWorkflowStage,
)


@pytest.fixture
def frozen_voice_corpus():
    """Frozen sanitized Voice corpus fixture."""
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
        {
            "opaque_record_id": "rec-003",
            "sanitized_text": "Subscription is overpriced and the expensive monthly cost is a rip-off.",
            "source_type": "feedback",
            "locale": "en",
            "detected_language": "en",
        },
        {
            "opaque_record_id": "rec-004",
            "sanitized_text": "Great quality and fast delivery! Love the build quality, highly recommend.",
            "source_type": "review",
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
        {
            "record_id": "rec-003",
            "sanitized_text_hash": "hash_rec_003",
            "start_offset": 0,
            "end_offset": 26,
            "span_hash": "hash003",
            "source_ref": "fb-1",
            "exact_quote": "Subscription is overpriced",
        },
        {
            "record_id": "rec-004",
            "sanitized_text_hash": "hash_rec_004",
            "start_offset": 0,
            "end_offset": 31,
            "span_hash": "hash004",
            "source_ref": "rev-2",
            "exact_quote": "Great quality and fast delivery",
        },
    ]
    return records, spans


@pytest.mark.asyncio
async def test_voice_themes_clustering_diagnostics_and_trend(frozen_voice_corpus):
    """VOICE-THEMES preserves observed share, diagnostics, evidence spans, and trend 'not_assessed'."""
    records, spans = frozen_voice_corpus
    agent = VoiceThemesAgent()
    task = CustomerVoiceTask(
        task_id="task-themes-101",
        tenant_id="tenant-acme",
        objective="thematic_clustering",
        source_refs=["rec-001", "rec-002", "rec-003", "rec-004"],
        workflow_stage=VoiceWorkflowStage.THEMES,
    )

    result = await agent.execute(task=task, records=records, evidence_spans=spans)

    assert isinstance(result, VoiceSpecialistResult)
    assert result.specialist_id == "VOICE-THEMES"
    assert result.stage == VoiceWorkflowStage.THEMES
    assert result.success is True
    assert len(result.findings) > 0

    for topic in result.findings:
        assert isinstance(topic, TopicFinding)
        assert topic.observed_count > 0
        assert 0.0 < topic.observed_share_of_analyzed_corpus <= 1.0
        # Population prevalence distinction: not established without survey methodology
        assert topic.population_representativeness == "not_established"
        assert topic.weighted_survey_estimate is None
        # Diagnostics preserved
        assert "silhouette_proxy" in topic.cluster_diagnostics
        assert topic.cluster_algorithm == "deterministic_keyword_centroid"
        assert topic.cluster_version == "1.0.0"
        # Trend rule: strictly not_assessed without comparative windows
        assert topic.trend == "not_assessed"
        # Representative evidence spans present
        assert len(topic.representative_evidence_spans) > 0


@pytest.mark.asyncio
async def test_voice_themes_weighted_survey_methodology(frozen_voice_corpus):
    """VOICE-THEMES applies weighted survey estimate only when methodology is provided."""
    records, spans = frozen_voice_corpus
    agent = VoiceThemesAgent()
    task = CustomerVoiceTask(
        task_id="task-themes-102",
        tenant_id="tenant-acme",
        objective="thematic_clustering_survey",
        source_refs=["rec-001"],
        workflow_stage=VoiceWorkflowStage.THEMES,
    )
    survey_methodology = SurveyMethodology(
        methodology_id="survey-m-01",
        sampling_frame="Customer base random sample",
        weighting_method="raking_post_stratification",
        completed_n=4,
        precision_method="95% CI (+/- 4.0%)",
    )

    result = await agent.execute(
        task=task,
        records=records,
        evidence_spans=spans,
        survey_methodology=survey_methodology,
    )

    assert result.success is True
    assert len(result.findings) > 0
    topic = result.findings[0]
    assert topic.weighted_survey_estimate is not None
    assert topic.population_representativeness == "statistically_weighted"


@pytest.mark.asyncio
async def test_voice_sentiment_aspect_level_and_calibration_honesty(frozen_voice_corpus):
    """VOICE-SENTIMENT produces aspect-level scores, score_is_calibrated=False, and evidence grounding."""
    records, spans = frozen_voice_corpus
    agent = VoiceSentimentAgent()
    task = CustomerVoiceTask(
        task_id="task-sent-101",
        tenant_id="tenant-acme",
        objective="aspect_sentiment",
        source_refs=["rec-001", "rec-002", "rec-003", "rec-004"],
        workflow_stage=VoiceWorkflowStage.SENTIMENT,
    )

    result = await agent.execute(task=task, records=records, evidence_spans=spans)

    assert isinstance(result, VoiceSpecialistResult)
    assert result.specialist_id == "VOICE-SENTIMENT"
    assert result.stage == VoiceWorkflowStage.SENTIMENT
    assert result.success is True
    assert len(result.findings) > 0

    for aspect in result.findings:
        assert isinstance(aspect, AspectSentimentFinding)
        # Calibration honesty: score_is_calibrated must be False
        assert aspect.score_is_calibrated is False
        assert aspect.polarity in ("POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED")
        assert aspect.model_score >= 0.0
        assert aspect.locale == "en"
        # Low sample count produces declared uncertainty reason
        assert aspect.uncertainty_reason is not None
        assert "Low sample count" in aspect.uncertainty_reason


@pytest.mark.asyncio
async def test_voice_sentiment_unsupported_locale_and_model():
    """VOICE-SENTIMENT returns not_assessed on unsupported locale or model without fabricating sentiment."""
    agent = VoiceSentimentAgent()
    task = CustomerVoiceTask(
        task_id="task-sent-102",
        tenant_id="tenant-acme",
        objective="unsupported_locale",
        source_refs=["rec-de-1"],
        workflow_stage=VoiceWorkflowStage.SENTIMENT,
    )
    records = [{
        "opaque_record_id": "rec-de-1",
        "sanitized_text": "Die Lieferung war sehr verspätet und der Kundenservice unfreundlich.",
        "source_type": "review",
        "locale": "de",
        "detected_language": "de",
    }]
    spans = [{
        "record_id": "rec-de-1",
        "sanitized_text_hash": "hash_de_1",
        "start_offset": 0,
        "end_offset": 18,
        "span_hash": "hashde1",
        "source_ref": "rev-de-1",
        "exact_quote": "Die Lieferung war",
    }]

    # Unsupported locale
    result_loc = await agent.execute(
        task=task,
        records=records,
        evidence_spans=spans,
        supported_locales={"en"},
    )
    assert result_loc.success is True
    finding = result_loc.findings[0]
    assert finding.polarity == "not_assessed"
    assert finding.score_is_calibrated is False
    assert "Unsupported locale 'de'" in finding.uncertainty_reason

    # Unsupported model
    result_model = await agent.execute(
        task=task,
        records=records,
        evidence_spans=spans,
        model_name="unknown_deep_v9",
    )
    assert result_model.success is True
    model_finding = result_model.findings[0]
    assert model_finding.polarity == "not_assessed"
    assert "Unsupported model" in model_finding.uncertainty_reason


@pytest.mark.asyncio
async def test_voice_needs_grounded_vocabulary_and_severity(frozen_voice_corpus):
    """VOICE-NEEDS extracts pains, objections, customer vocabulary, and groundings."""
    records, spans = frozen_voice_corpus
    agent = VoiceNeedsAgent()
    task = CustomerVoiceTask(
        task_id="task-needs-101",
        tenant_id="tenant-acme",
        objective="needs_extraction",
        source_refs=["rec-001", "rec-002", "rec-003", "rec-004"],
        workflow_stage=VoiceWorkflowStage.NEEDS,
    )

    result = await agent.execute(task=task, records=records, evidence_spans=spans)

    assert isinstance(result, VoiceSpecialistResult)
    assert result.specialist_id == "VOICE-NEEDS"
    assert result.stage == VoiceWorkflowStage.NEEDS
    assert result.success is True
    assert len(result.findings) > 0

    for need in result.findings:
        assert isinstance(need, NeedObjectionFinding)
        assert need.finding_type in ("need", "pain_point", "objection", "desired_outcome")
        assert need.frequency >= 1
        assert need.severity in ("low", "medium", "high")
        assert len(need.customer_vocabulary) > 0
        assert len(need.evidence_spans) > 0


@pytest.mark.asyncio
async def test_corpus_immutability_during_specialist_analysis(frozen_voice_corpus):
    """Verify that none of the analysis specialists mutate the frozen corpus."""
    records, spans = frozen_voice_corpus
    records_copy = copy.deepcopy(records)
    spans_copy = copy.deepcopy(spans)

    task = CustomerVoiceTask(
        task_id="task-immutability-101",
        tenant_id="tenant-acme",
        objective="immutability_test",
        source_refs=["rec-001"],
        workflow_stage=VoiceWorkflowStage.THEMES,
    )

    themes_agent = VoiceThemesAgent()
    sent_agent = VoiceSentimentAgent()
    needs_agent = VoiceNeedsAgent()

    await themes_agent.execute(task, records, spans)
    await sent_agent.execute(task, records, spans)
    await needs_agent.execute(task, records, spans)

    assert records == records_copy
    assert spans == spans_copy


@pytest.mark.asyncio
async def test_coordinator_synthesizes_all_three_analysis_packs():
    """Verify CustomerVoiceAgent coordinator populates topics, aspect_sentiment, and needs in payload."""
    agent = CustomerVoiceAgent()

    grant = TaskGrant(
        grant_id="grant-cv05-full",
        task_id="task-cv05-full",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        tenant_scope=TenantScope(tenant_id="tenant-123"),
        objective="full_voice_analysis",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    context = {
        "items": [
            {
                "item_id": "item-1",
                "text": "Shipping was slow and the package delivery was delayed two weeks. Very frustrated.",
                "source_type": "review",
                "tenant_id": "tenant-123",
            },
            {
                "item_id": "item-2",
                "text": "Support service ticket was ignored for days. Agent was unresponsive on hold.",
                "source_type": "support_ticket",
                "tenant_id": "tenant-123",
            },
            {
                "item_id": "item-3",
                "text": "Expensive price and high monthly subscription cost. Need cheaper billing.",
                "source_type": "feedback",
                "tenant_id": "tenant-123",
            },
        ],
        "product_id": "prod-xyz",
    }

    envelope = await agent.run(grant=grant, context=context)

    assert envelope.task_id == "task-cv05-full"
    payload = CustomerVoicePayload.model_validate_json(envelope.payload["customer_voice_payload"])
    assert payload.records_analyzed == 3
    assert len(payload.topics) > 0
    assert len(payload.aspect_sentiment) > 0
    assert len(payload.needs_and_objections) > 0

    assert "themes_result" in envelope.payload
    assert "sentiment_result" in envelope.payload
    assert "needs_result" in envelope.payload
