"""Tests for COMP-PRICE specialist, decimal pricing, and comparability."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.agents.competitor_intel_engine.subagents.pricing import (
    CompetitorPricingAgent,
    parse_pricing_data,
)
from app.schemas.competitor_intel import (
    CompetitorAttemptInput,
    CompetitorRole,
    FailureCode,
)
from app.schemas.sandbox import SandboxEgressGrant


def test_price_exact_decimal_and_null_unknown():
    """Verify exact Decimal parsing and that unknown price is null, never zero."""
    raw_payload = {
        "competitor": "SaaSCompetitor",
        "products": [
            {
                "sku": "pro-tier",
                "name": "Pro Tier Plan",
                "price": "49.99",
                "currency": "USD",
                "billing_interval": "monthly",
            },
            {
                "sku": "free-tier",
                "name": "Free Community Plan",
                "price": "0.00",
                "currency": "USD",
                "billing_interval": "monthly",
            },
            {
                "sku": "enterprise-tier",
                "name": "Custom Enterprise",
                "price": None,  # Contact sales / unstated
                "currency": "USD",
                "billing_interval": "annual",
            },
        ],
    }

    obs, findings, coverage, failures = parse_pricing_data(raw_payload, attempt_id="att-price-1")

    # Three products parsed: unknown price remains null, never zero
    assert len(obs) == 3
    pro_obs = next(o for o in obs if o.typed_value["sku"] == "pro-tier")
    assert pro_obs.typed_value["price"] == "49.99"
    assert pro_obs.typed_value["currency"] == "USD"
    assert Decimal(pro_obs.typed_value["price"]) == Decimal("49.99")

    free_obs = next(o for o in obs if o.typed_value["sku"] == "free-tier")
    assert free_obs.typed_value["price"] == "0.00"
    assert Decimal(free_obs.typed_value["price"]) == Decimal("0.00")

    ent_obs = next(o for o in obs if o.typed_value["sku"] == "enterprise-tier")
    assert ent_obs.typed_value["price"] is None
    assert ent_obs.typed_value["price"] != Decimal("0.00")

    # Unknown price is also recorded in failures with PRICE_NOT_DISCLOSED
    assert any(
        f.get("code") == FailureCode.PRICE_NOT_DISCLOSED and f.get("sku") == "enterprise-tier"
        for f in failures
    )


def test_price_comparability_and_currency_mismatch():
    """Verify comparability fails on missing currency or invalid baseline."""
    raw_payload = {
        "competitor": "RetailCompetitor",
        "products": [
            {
                "sku": "prod-unknown-curr",
                "price": "100.00",
                "currency": "UNKNOWN",
            },
            {
                "sku": "prod-delta-zero-base",
                "price": "25.00",
                "baseline_price": "0.00",  # baseline is 0: percentage delta is undefined
                "currency": "USD",
            },
            {
                "sku": "prod-delta-valid",
                "price": "120.00",
                "baseline_price": "100.00",
                "currency": "USD",
            },
        ],
    }

    obs, findings, coverage, failures = parse_pricing_data(raw_payload, attempt_id="att-price-2")

    # Unknown currency triggers failure
    assert any(
        f.get("code") == FailureCode.CURRENCY_UNKNOWN and f.get("sku") == "prod-unknown-curr"
        for f in failures
    )

    # Valid delta: (120 - 100) / 100 = 20.00%
    valid_obs = next(o for o in obs if o.typed_value["sku"] == "prod-delta-valid")
    assert valid_obs.typed_value["percentage_delta"] == "20.00%"

    # Zero baseline: delta percentage must be None (undefined), not divide-by-zero
    zero_base_obs = next(o for o in obs if o.typed_value["sku"] == "prod-delta-zero-base")
    assert zero_base_obs.typed_value["percentage_delta"] is None


@pytest.mark.asyncio
async def test_pricing_agent_execute_attempt():
    """Verify pricing specialist executes attempt and parses normalized pricing envelope."""
    agent = CompetitorPricingAgent()

    class MockSandboxClient:
        async def invoke(self, mandate):
            class MockResult:
                success = True
                error = None
                sanitized_output = {"benchmark_price": "49.00"}
                execution_id = "exec-price-001"

            return MockResult()

    attempt_input = CompetitorAttemptInput(
        grant_id="grant-price-1",
        task_id="task-price-1",
        tenant_id="tenant-alpha",
        run_id="run-price-001",
        step_id="step-price-1",
        attempt_id="att-price-001",
        role=CompetitorRole.PRICE,
        profile_id="w_comp.price.v1",
        llm_instance_id="llm-price-001",
        approved_operation_ids=["pricing_table_extract"],
        context_slice={
            "competitor": "TierCorp",
            "products": [
                {
                    "sku": "tier-standard",
                    "price": "49.00",
                    "currency": "USD",
                    "billing_interval": "monthly",
                }
            ],
        },
        input_hash="b" * 64,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )

    egress_grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-price-1",
        specialist_id="COMP-PRICE",
        allowed_domains=["pricing.tiercorp.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    res = await agent.execute_price_attempt(
        MockSandboxClient(),
        attempt_input,
        egress_grant=egress_grant,
    )

    assert res.status == "success"
    # Observations from sandbox mock benchmark + context_slice parsed product
    assert len(res.observations) == 2
    parsed_sku = next(
        o
        for o in res.observations
        if isinstance(o.typed_value, dict) and o.typed_value.get("sku") == "tier-standard"
    )
    assert parsed_sku.typed_value["price"] == "49.00"
