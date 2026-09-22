"""Tests for COMP-SEARCH specialist, SERP capture, estimates, and baseline requirements."""

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.competitor_intel_engine.subagents.search_intel import (
    CompetitorSearchIntelAgent,
    parse_search_data,
)
from app.schemas.competitor_intel import (
    CompetitorAttemptInput,
    CompetitorRole,
    CoverageStatus,
    FailureCode,
)
from app.schemas.sandbox import SandboxEgressGrant


def test_search_organic_paid_and_estimates():
    """Verify organic vs paid separation and provider volume/KD marked as estimates."""
    raw_payload = {
        "query": "enterprise workflow engine",
        "provider": "google",
        "depth_limit": 20,
        "serp_rows": [
            {
                "rank": 1,
                "result_type": "paid",
                "url": "https://competitor.com/ad",
                "domain": "competitor.com",
            },
            {
                "rank": 2,
                "result_type": "organic",
                "url": "https://competitor.com/product",
                "domain": "competitor.com",
            },
        ],
        "provider_metrics": {
            "search_volume": 12500,
            "keyword_difficulty": 68,
        },
    }

    obs, findings, coverage, failures = parse_search_data(raw_payload, attempt_id="att-s-1")

    # 2 SERP rows + 2 provider estimates = 4 observations
    assert len(obs) == 4

    paid_obs = next(o for o in obs if o.predicate == "serp_paid_rank")
    assert paid_obs.typed_value["rank"] == 1
    assert paid_obs.typed_value["result_type"] == "paid"
    assert paid_obs.observation_kind == "observed"

    organic_obs = next(o for o in obs if o.predicate == "serp_organic_rank")
    assert organic_obs.typed_value["rank"] == 2
    assert organic_obs.typed_value["result_type"] == "organic"
    assert organic_obs.observation_kind == "observed"

    vol_obs = next(o for o in obs if o.predicate == "provider_estimate_search_volume")
    assert vol_obs.typed_value == 12500
    assert vol_obs.observation_kind == "provider_estimate"
    assert "Third-party provider estimate" in vol_obs.limitations[0]


def test_search_content_gap_requires_brand_inventory_baseline():
    """Verify content gap evaluation fails closed with BASELINE_MISSING without brand pages."""
    raw_payload = {
        "query": "logistics optimization software",
        "check_content_gap": True,
        "brand_page_inventory": None,  # Missing baseline
        "serp_rows": [
            {
                "rank": 1,
                "result_type": "organic",
                "url": "https://competitor.com/logistics",
                "domain": "competitor.com",
            }
        ],
        "depth_limit": 10,
    }

    obs, findings, coverage, failures = parse_search_data(raw_payload, attempt_id="att-s-2")
    assert any(f.get("code") == FailureCode.BASELINE_MISSING for f in failures)
    assert coverage.limitations == [
        "Sampled at depth 10; unobserved results != unranked."
    ]


@pytest.mark.asyncio
async def test_search_agent_execute_attempt():
    """Verify search specialist executes attempt and parses normalized SERP rankings envelope."""
    agent = CompetitorSearchIntelAgent()

    class MockSandboxClient:
        async def invoke(self, mandate):
            class MockResult:
                success = True
                error = None
                sanitized_output = {"benchmark_price": "29.99"}
                execution_id = "exec-search-001"

            return MockResult()

    attempt_input = CompetitorAttemptInput(
        grant_id="grant-s-1",
        task_id="task-s-1",
        tenant_id="tenant-alpha",
        run_id="run-s-001",
        step_id="step-s-1",
        attempt_id="att-s-001",
        role=CompetitorRole.SEARCH,
        profile_id="w_comp.search.v1",
        llm_instance_id="llm-search-001",
        approved_operation_ids=["serp_query"],
        context_slice={
            "query": "cloud orchestration",
            "serp_rows": [
                {
                    "rank": 3,
                    "result_type": "organic",
                    "url": "https://competitor.com/cloud",
                    "domain": "competitor.com",
                }
            ],
            "depth_limit": 50,
        },
        input_hash="c" * 64,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )

    egress_grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-s-1",
        specialist_id="COMP-SEARCH",
        allowed_domains=["search.google.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    res = await agent.execute_search_attempt(
        MockSandboxClient(),
        attempt_input,
        egress_grant=egress_grant,
    )

    assert res.status == "success"
    assert res.coverage is not None
    assert res.coverage.status == CoverageStatus.COMPLETE_FOR_QUERY
    parsed_rank = next(
        o
        for o in res.observations
        if isinstance(o.typed_value, dict) and o.typed_value.get("rank") == 3
    )
    assert parsed_rank.typed_value["url"] == "https://competitor.com/cloud"
