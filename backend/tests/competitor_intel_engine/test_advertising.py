"""Tests for COMP-ADS specialist and ad transparency metadata extraction."""

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.competitor_intel_engine.subagents.advertising import (
    CompetitorAdvertisingAgent,
    parse_ad_transparency_data,
)
from app.schemas.competitor_intel import (
    CompetitorAttemptInput,
    CompetitorRole,
    CoverageStatus,
    FailureCode,
)
from app.schemas.sandbox import SandboxEgressGrant


def test_reach_ranges_remain_ranges_and_no_fabricated_spend():
    """Verify impressions/reach remain ranges and fabricated spend is rejected."""
    raw_payload = {
        "competitor": "CompetitorCorp",
        "ads": [
            {
                "ad_id": "meta-ad-101",
                "copy": "Join our platform today",
                "reach_range": "10k-50k",
                "disclosed_targeting": {"age": "18-65+", "countries": ["US"]},
                "estimated_spend": 5000.00,  # Prohibited inferred spend
            }
        ],
    }

    obs, findings, coverage, failures = parse_ad_transparency_data(
        raw_payload, attempt_id="att-ads-1"
    )
    assert len(obs) == 1
    assert obs[0].typed_value["reach_range"] == "10k-50k"
    assert "spend_usd" not in obs[0].typed_value
    assert any(f.get("code") == FailureCode.POLICY_DENIED for f in failures)


def test_ad_transparency_pagination_and_truncation():
    """Verify pagination tracking and truncation status."""
    raw_payload = {
        "ads": [{"ad_id": f"meta-ad-{i}", "copy": "Test ad"} for i in range(20)],
        "page_number": 1,
        "page_size": 20,
        "is_truncated": True,
    }

    obs, findings, coverage, failures = parse_ad_transparency_data(
        raw_payload, attempt_id="att-ads-2"
    )
    assert len(obs) == 20
    assert coverage.status == CoverageStatus.PARTIAL
    assert coverage.depth_cursor_exhausted is False
    assert "Pagination truncated at limit." in coverage.limitations


@pytest.mark.asyncio
async def test_advertising_agent_execute_attempt():
    """Verify advertising agent wraps evidence cleanly without sandbox escalation."""
    agent = CompetitorAdvertisingAgent()

    class MockSandboxClient:
        async def invoke(self, mandate):
            class MockResult:
                success = True
                error = None
                sanitized_output = {"active_ads": 15, "competitor": "AdBrand"}
                execution_id = "exec-ads-001"

            return MockResult()

    attempt_input = CompetitorAttemptInput(
        grant_id="grant-ads-1",
        task_id="task-ads-1",
        tenant_id="tenant-alpha",
        run_id="run-ads-001",
        step_id="step-ads-1",
        attempt_id="att-ads-001",
        role=CompetitorRole.ADS,
        profile_id="w_comp.ads.v1",
        llm_instance_id="llm-ads-001",
        approved_operation_ids=["transparency_query"],
        context_slice={
            "ads": [
                {
                    "ad_id": "google-ad-1",
                    "copy": "Special 20% discount",
                    "reach_range": "1k-5k",
                }
            ]
        },
        input_hash="a" * 64,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )

    egress_grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-ads-1",
        specialist_id="COMP-ADS",
        allowed_domains=["adstransparency.google.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    res = await agent.execute_ads_attempt(
        MockSandboxClient(),
        attempt_input,
        egress_grant=egress_grant,
    )

    assert res.status == "success"
    assert len(res.observations) == 1
    assert res.observations[0].typed_value["ad_id"] == "google-ad-1"
