"""Tests for COMP-POSITION specialist, verbatim claims, and role boundaries."""

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.competitor_intel_engine.subagents.positioning import (
    CompetitorPositioningAgent,
    parse_positioning_data,
)
from app.schemas.competitor_intel import (
    CompetitorAttemptInput,
    CompetitorRole,
    CoverageStatus,
    FailureCode,
)
from app.schemas.sandbox import SandboxEgressGrant


def test_positioning_verbatim_claims_and_epistemic_truth():
    """Verify competitor claims are recorded as competitor states X, not objective truth."""
    raw_payload = {
        "competitor": "CompetitorCorp",
        "messaging_spans": [
            {
                "placement": "hero_headline",
                "stated_claim": "The fastest database in the world with zero latency",
                "offer_text": "Start free 14-day trial",
                "page_version": "v2.1",
            }
        ],
        "baseline_messaging": {
            "hero_headline": "Fast database for developers",
        },
    }

    obs, findings, coverage, failures = parse_positioning_data(
        raw_payload, attempt_id="att-pos-1"
    )

    assert len(obs) == 1
    claim_obs = obs[0]
    assert claim_obs.predicate == "stated_value_proposition"
    assert (
        claim_obs.typed_value["verbatim_claim"]
        == "The fastest database in the world with zero latency"
    )
    assert claim_obs.typed_value["change_kind"] == "semantic_change"
    assert claim_obs.typed_value["truth_status"] == "competitor_statement_only"
    assert claim_obs.limitations == [
        "Captures what competitor states; does not verify underlying product efficacy."
    ]

    # Finding highlights semantic shift without endorsing claim as fact
    assert len(findings) == 1
    assert "detected semantic_change messaging change" in findings[0].claim_text


def test_positioning_denies_reviews_sentiment_and_creative():
    """Verify COMP-POSITION denies reviews, sentiment, or creative generation requests."""
    # Forbidden operation: review mining
    raw_payload_reviews = {
        "competitor": "CompetitorCorp",
        "operation": "review_mining",
        "include_customer_reviews": True,
    }

    obs, findings, coverage, failures = parse_positioning_data(
        raw_payload_reviews, attempt_id="att-pos-2"
    )
    assert len(obs) == 0
    assert coverage.status == CoverageStatus.DENIED
    assert any(f.get("code") == FailureCode.ROLE_DENIED for f in failures)


@pytest.mark.asyncio
async def test_positioning_agent_execute_attempt():
    """Verify execute_position_attempt parses observations into SpecialistResult."""
    agent = CompetitorPositioningAgent()

    class MockSandboxClient:
        async def invoke(self, mandate):
            class MockResult:
                success = True
                error = None
                sanitized_output = {"benchmark_price": "19.99"}
                execution_id = "exec-pos-001"

            return MockResult()

    attempt_input = CompetitorAttemptInput(
        grant_id="grant-pos-1",
        task_id="task-pos-1",
        tenant_id="tenant-alpha",
        run_id="run-pos-001",
        step_id="step-pos-1",
        attempt_id="att-pos-001",
        role=CompetitorRole.POSITION,
        profile_id="w_comp.position.v1",
        llm_instance_id="llm-pos-001",
        approved_operation_ids=["messaging_capture"],
        context_slice={
            "competitor": "TargetCorp",
            "messaging_spans": [
                {
                    "placement": "pricing_header",
                    "stated_claim": "Predictable enterprise flat pricing",
                }
            ],
        },
        input_hash="d" * 64,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )

    egress_grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-pos-1",
        specialist_id="COMP-POSITION",
        allowed_domains=["targetcorp.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    res = await agent.execute_position_attempt(
        MockSandboxClient(),
        attempt_input,
        egress_grant=egress_grant,
    )

    assert res.status == "success"
    assert len(res.observations) == 2  # 1 mock sandbox price + 1 messaging claim
    claim = next(
        o
        for o in res.observations
        if isinstance(o.typed_value, dict) and o.typed_value.get("placement") == "pricing_header"
    )
    assert claim.typed_value["verbatim_claim"] == "Predictable enterprise flat pricing"
