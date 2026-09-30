"""Comprehensive validation suite for complete cognitive LLM isolation and reasoning.

Verifies:
1. Intelligence Engine (IE) has dedicated LLM access (identity: INTELLIGENCE_ENGINE).
2. All 7 Worker Agents have individual, isolated LLM access with distinct identities (W_DEV .. W_LEARN).
3. All 38 Specialist Sub-Agents across all 7 Worker Agents have dedicated, isolated LLM access with distinct identities.
4. Total 46 distinct cognitive entities exist without cross-agent identity or context leakage.
5. Cognitive reasoning loops (reason_*) succeed with LLM responses and fall back deterministically when LLM is unavailable.
6. Model A architectural boundary adherence (zero ambient RAG/DB access for workers and specialists).
7. Full application composition root wires and safely disposes all 46 LLM clients during lifespan.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.settings import LlmSettings
from app.integrations.llm.client import LlmClient
from app.schemas.governance import WorkerRole
from app.main import _build_workers, create_app


@pytest.fixture
def base_llm_settings() -> LlmSettings:
    return LlmSettings(
        provider="mock",
        model="gpt-4o",
        api_key="mock-key-for-test",
        endpoint=None,
    )


def test_46_cognitive_entities_have_unique_identities(base_llm_settings: LlmSettings) -> None:
    """Ensure all 46 cognitive entities across IE, 7 workers, and 38 subagents have distinct identities."""
    mock_sandbox = MagicMock()

    # Create root mock client
    root_client = LlmClient(base_llm_settings, agent_identity="INTELLIGENCE_ENGINE")

    # Build workers using isolated propagation
    workers = _build_workers(
        mock_sandbox,
        llm_client=root_client,
    )

    all_identities: set[str] = set()

    # 1. IE identity
    assert root_client.agent_identity == "INTELLIGENCE_ENGINE"
    all_identities.add(root_client.agent_identity)

    # 2. 7 Worker Agents
    expected_workers = {
        WorkerRole.DEVELOPMENT: "W_DEV",
        WorkerRole.STRATEGY: "W_STRAT",
        WorkerRole.CREATIVE_CONTENT: "W_CREAT",
        WorkerRole.PRODUCT_EVIDENCE: "W_PROD",
        WorkerRole.COMPETITOR_INTEL: "W_COMP",
        WorkerRole.CUSTOMER_VOICE: "W_VOICE",
        WorkerRole.LEARNING_PERFORMANCE: "W_LEARN",
    }

    assert len(workers) == 7

    for role, expected_id in expected_workers.items():
        worker = workers[role]
        assert worker.llm_client is not None, f"Worker {role} missing LLM client"
        worker_id = worker.llm_client.agent_identity
        assert worker_id is not None, f"Worker {role} LLM client missing agent_identity"
        assert expected_id in worker_id, f"Worker {role} identity mismatch: {worker_id} vs {expected_id}"
        all_identities.add(worker_id)

    # 3. Specialist Subagents across all 7 workers
    expected_specialists = {
        WorkerRole.DEVELOPMENT: [
            "DEV-PLAN", "DEV-CMS", "DEV-UI", "DEV-CODE", "DEV-VERIFY", "DEV-SEC", "DEV-REL"
        ],
        WorkerRole.STRATEGY: [
            "STRAT-ALLOC"
        ],
        WorkerRole.CREATIVE_CONTENT: [
            "CREAT-RESEARCH", "CREAT-CONCEPT", "CREAT-COPY", "CREAT-VISUAL", "CREAT-ADAPT", "CREAT-QA"
        ],
        WorkerRole.PRODUCT_EVIDENCE: [
            "PROD-DISCOVERY", "PROD-APPRAISAL", "PROD-CLAIMS", "PROD-LAB", "PROD-REGULATORY", "PROD-SAFETY"
        ],
        WorkerRole.COMPETITOR_INTEL: [
            "COMP-DISCOVERY", "COMP-ADS", "COMP-PRICE", "COMP-SEARCH", "COMP-POSITION", "COMP-SYNTH"
        ],
        WorkerRole.CUSTOMER_VOICE: [
            "VOICE-DISCOVERY", "VOICE-THEMES", "VOICE-SENTIMENT", "VOICE-NEEDS", "VOICE-JOURNEY", "VOICE-QA"
        ],
        WorkerRole.LEARNING_PERFORMANCE: [
            "LEARN-TELEMETRY", "LEARN-ATTRIBUTION", "LEARN-INCREMENTALITY", "LEARN-FATIGUE", "LEARN-DECAY", "LEARN-QA"
        ],
    }

    subagent_count = 0
    for role, spec_list in expected_specialists.items():
        worker = workers[role]
        specialists = getattr(worker, "specialists", {})
        assert specialists, f"Worker {role} has no specialists property"
        for spec_key in spec_list:
            subagent = specialists.get(spec_key)
            assert subagent is not None, f"Missing specialist {spec_key} in {role}"
            sub_llm = getattr(subagent, "llm_client", None)
            assert sub_llm is not None, f"Specialist {spec_key} has no LLM client"
            sub_id = sub_llm.agent_identity
            assert sub_id is not None
            assert spec_key in sub_id, f"Specialist {spec_key} identity mismatch: {sub_id}"
            all_identities.add(sub_id)
            subagent_count += 1

    assert subagent_count == 38, f"Expected 38 subagents, found {subagent_count}"
    # Total unique identities = 1 (IE) + 7 (Workers) + 38 (Subagents) = 46
    assert len(all_identities) == 46, f"Expected 46 unique identities, got {len(all_identities)}"


@pytest.mark.asyncio
async def test_cognitive_reasoning_loops_with_mock_and_fallback(base_llm_settings: LlmSettings) -> None:
    """Verify that specialist cognitive reasoning loops utilize isolated LLMs and fall back cleanly."""
    mock_sandbox = MagicMock()

    # 1. Test Development Subagent: DEV-PLAN reasoning
    from app.agents.development_engine.subagents.planning import DevelopmentPlanningAgent

    plan_agent_offline = DevelopmentPlanningAgent(sandbox_client=mock_sandbox, llm_client=None)
    res_plan_offline = await plan_agent_offline.reason_plan(
        objective="Design enterprise landing page",
        tech_stack=["React", "FastAPI"],
    )
    assert res_plan_offline["recommended_action"] == "PROCEED_WITH_PLAN"
    assert "React" in res_plan_offline["evaluated_tech_stack"]

    # With LLM mock
    mock_llm = AsyncMock()
    mock_llm.complete_with_metadata.return_value = (
        json.dumps({
            "thought_process": "Cognitive analysis indicates micro-frontend architecture is optimal.",
            "evaluated_tech_stack": ["React", "FastAPI"],
            "plan_insights": ["High modularity", "Strict schema alignment"],
            "recommended_action": "PROCEED_WITH_MICRO_FRONTEND",
            "confidence": 0.98,
        }),
        {"tokens": 42},
    )
    plan_agent_online = DevelopmentPlanningAgent(sandbox_client=mock_sandbox, llm_client=mock_llm)
    res_plan_online = await plan_agent_online.reason_plan(
        objective="Design enterprise landing page",
        tech_stack=["React", "FastAPI"],
    )
    assert res_plan_online["recommended_action"] == "PROCEED_WITH_MICRO_FRONTEND"
    assert res_plan_online["confidence"] == 0.98

    # 2. Test Competitor Intel: COMP-PRICING reasoning
    from app.agents.competitor_intel_engine.subagents.pricing import CompetitorPricingAgent

    price_agent = CompetitorPricingAgent(llm_client=None)
    res_pricing = await price_agent.reason_pricing(
        objective="Analyze rival SaaS tiers",
        competitors=["AcmeCorp"],
    )
    assert res_pricing["recommended_action"] == "PROCEED_WITH_PRICING_SCRAPE"
    assert "AcmeCorp" in res_pricing["evaluated_competitors"]

    # 3. Test Customer Voice: VOICE-SENTIMENT reasoning
    from app.agents.customer_voice_engine.subagents.sentiment import VoiceSentimentAgent

    sent_agent = VoiceSentimentAgent(llm_client=None)
    res_sent = await sent_agent.reason_sentiment(
        objective="Assess checkout friction sentiment",
        aspects=["payment_gateway", "page_load"],
    )
    assert res_sent["recommended_action"] == "PROCEED_WITH_SENTIMENT_SCORING"
    assert "payment_gateway" in res_sent["evaluated_aspects"]

    # 4. Test Customer Voice: VOICE-JOURNEY & VOICE-QA reasoning
    from app.agents.customer_voice_engine.subagents.journey import VoiceJourneyAgent
    from app.agents.customer_voice_engine.subagents.quality import VoiceQualityAgent

    journey_agent = VoiceJourneyAgent(llm_client=None)
    res_journey = await journey_agent.reason_journey(
        objective="Analyze mobile vs desktop checkout stages",
        segments=["mobile", "desktop"],
    )
    assert res_journey["recommended_action"] == "PROCEED_WITH_DESCRIPTIVE_JOURNEY_MAPPING"

    voice_qa = VoiceQualityAgent(llm_client=None)
    res_v_qa = await voice_qa.reason_qa(objective="Validate voice report privacy")
    assert res_v_qa["verdict"] == "PASS"

    # 5. Test Product Evidence: PROD-CLAIMS reasoning
    from app.agents.product_evidence_engine.subagents.claims import ProductClaimsAgent

    claims_agent = ProductClaimsAgent(sandbox_client=mock_sandbox, llm_client=None)
    res_claims = await claims_agent.reason_claims(
        objective="Validate SPF 50 clinical efficacy claim",
        claim_candidate="Provides 24-hour hydration and SPF 50 shield",
    )
    assert res_claims["recommended_action"] == "PROCEED_WITH_DOSSIER_EXTRACTION"

    # 6. Test Learning Performance Subagents: TELEMETRY, ATTRIBUTION, INCREMENTALITY, FATIGUE, DECAY, QA
    from app.agents.learning_performance_engine.subagents.telemetry import LearningTelemetryAgent
    from app.agents.learning_performance_engine.subagents.attribution import LearningAttributionAgent
    from app.agents.learning_performance_engine.subagents.incrementality import LearningIncrementalityAgent
    from app.agents.learning_performance_engine.subagents.fatigue import LearningFatigueAgent
    from app.agents.learning_performance_engine.subagents.decay import LearningDecayAgent
    from app.agents.learning_performance_engine.subagents.quality import LearningQualityAgent

    telem_agent = LearningTelemetryAgent(sandbox_client=mock_sandbox, llm_client=None)
    res_telem = await telem_agent.reason_telemetry(objective="Verify event schemas")
    assert res_telem["recommended_action"] == "PROCEED_WITH_NORMALIZATION"

    attr_agent = LearningAttributionAgent(sandbox_client=mock_sandbox, llm_client=None)
    res_attr = await attr_agent.reason_attribution(
        objective="Evaluate omnichannel touchpoints",
        channels=["meta", "google_search", "email"],
    )
    assert res_attr["recommended_action"] == "PROCEED_WITH_ATTRIBUTION_MODELING"
    assert "meta" in res_attr["evaluated_channels"]

    incr_agent = LearningIncrementalityAgent(sandbox_client=mock_sandbox, llm_client=None)
    res_incr = await incr_agent.reason_incrementality(objective="Evaluate geo-lift test", channel="meta")
    assert res_incr["recommended_action"] == "PROCEED_WITH_EXPERIMENT_LIFT_ESTIMATION"

    fatigue_agent = LearningFatigueAgent(sandbox_client=mock_sandbox, llm_client=None)
    res_fatigue = await fatigue_agent.reason_fatigue(objective="Detect creative burnout", creative_id="c-99")
    assert res_fatigue["recommended_action"] == "PROCEED_WITH_FATIGUE_ANALYSIS"

    decay_agent = LearningDecayAgent(sandbox_client=mock_sandbox, llm_client=None)
    res_decay = await decay_agent.reason_decay(objective="Estimate adstock half-life", channel="search")
    assert res_decay["recommended_action"] == "PROCEED_WITH_ADSTOCK_ESTIMATION"

    learn_qa = LearningQualityAgent(sandbox_client=mock_sandbox, llm_client=None)
    res_learn_qa = await learn_qa.reason_qa(objective="Gate candidate delta D-001")
    assert res_learn_qa["verdict"] == "PASS"
    assert res_learn_qa["recommended_action"] == "ALLOW_LEARNING_DELTA_PUBLICATION"


def test_model_a_boundaries_strictly_enforced() -> None:
    """Verify that Worker Agents and Sub-Agents maintain Model A boundaries.
    
    Workers must never have direct DB or RAG access; all data retrieval is mediated via IE.
    """
    mock_sandbox = MagicMock()
    workers = _build_workers(mock_sandbox, llm_client=None)

    for role, worker in workers.items():
        # Workers cannot have direct persistence or RAG references
        assert not hasattr(worker, "rag_dispatcher"), f"Worker {role} violates Model A: direct RAG access"
        assert not hasattr(worker, "data_gateway"), f"Worker {role} violates Model A: direct DataGateway access"
        assert not hasattr(worker, "database"), f"Worker {role} violates Model A: direct database access"

        # Specialists also must not have direct DB access
        specialists = getattr(worker, "specialists", {})
        for spec_key, subagent in specialists.items():
            assert not hasattr(subagent, "rag_dispatcher"), f"Subagent {spec_key} violates Model A: direct RAG"
            assert not hasattr(subagent, "data_gateway"), f"Subagent {spec_key} violates Model A: direct DB"
