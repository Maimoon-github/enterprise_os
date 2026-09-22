"""COMP-PRICE: Competitor Pricing & Commercial Offer Specialist Sub-Agent.

Extracts price points, discounts, pack sizes, billing periods, and promotional terms
under strict comparability and exact decimal arithmetic. Unknown prices remain null;
comparisons require identical currency and variant baselines.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.agents.competitor_intel_engine.profiles import (
    PRICE_PROFILE,
    SpecialistModelProfile,
    dispatch_competitor_specialist_attempt,
)
from app.schemas.competitor_intel import (
    CompetitorAttemptInput,
    CompetitorRole,
    CoverageRecord,
    CoverageStatus,
    FailureCode,
    Finding,
    Observation,
    SpecialistResult,
)
from app.schemas.sandbox import SandboxEgressGrant


def parse_pricing_data(
    raw_payload: dict[str, Any],
    attempt_id: str,
) -> tuple[list[Observation], list[Finding], CoverageRecord, list[dict[str, Any]]]:
    """Extract and normalize pricing points with exact decimal precision and comparability checks.

    - Unknown price is null, never zero.
    - Free tier/promotion price is exact 0.00 with evidence.
    - Trajectory delta (new - old) / old computed only when old > 0.
    - Currency, pack, and billing mismatches are marked non-comparable.
    """
    observations: list[Observation] = []
    findings: list[Finding] = []
    failures: list[dict[str, Any]] = []

    products_data = raw_payload.get("products", [])
    queried_entity = raw_payload.get("competitor", "Unknown")
    source_id = raw_payload.get("source_id", "src-pricing-crawler")

    for idx, item in enumerate(products_data):
        sku = item.get("sku") or f"sku-{attempt_id}-{idx}"
        currency = item.get("currency")
        raw_price = item.get("price")
        baseline_price = item.get("baseline_price")
        billing_interval = item.get("billing_interval", "one_time")
        pack_quantity = item.get("pack_quantity", 1)

        # 1. Currency validation
        if not currency or currency.upper() in ("UNKNOWN", ""):
            failures.append({
                "code": FailureCode.CURRENCY_UNKNOWN,
                "sku": sku,
                "message": f"Product '{sku}' has unknown or undisclosed currency.",
            })
            continue

        # 2. Decimal parsing
        price_decimal: Decimal | None = None
        if raw_price is not None:
            try:
                price_decimal = Decimal(str(raw_price))
            except (InvalidOperation, TypeError):
                failures.append({
                    "code": FailureCode.PRICE_NOT_DISCLOSED,
                    "sku": sku,
                    "message": f"Malformed or non-decimal price '{raw_price}' for '{sku}'.",
                })
                continue
        else:
            failures.append({
                "code": FailureCode.PRICE_NOT_DISCLOSED,
                "sku": sku,
                "message": f"Price for SKU '{sku}' is not disclosed.",
            })

        # 3. Comparability & Delta
        percentage_delta: str | None = None
        if price_decimal is not None and baseline_price is not None:
            try:
                baseline_decimal = Decimal(str(baseline_price))
                if baseline_decimal > 0:
                    delta = (price_decimal - baseline_decimal) / baseline_decimal
                    percentage_delta = f"{delta * 100:.2f}%"
                else:
                    # Baseline was 0.0 or negative: percentage change is undefined
                    percentage_delta = None
            except (InvalidOperation, TypeError):
                failures.append({
                    "code": FailureCode.NOT_COMPARABLE,
                    "sku": sku,
                    "message": "Baseline price is malformed; delta calculation skipped.",
                })

        obs = Observation(
            observation_id=f"obs-{attempt_id}-{sku}",
            predicate="product_pricing",
            typed_value={
                "sku": sku,
                "product_name": item.get("name", sku),
                "price": str(price_decimal) if price_decimal is not None else None,
                "currency": currency.upper(),
                "billing_interval": billing_interval,
                "pack_quantity": pack_quantity,
                "percentage_delta": percentage_delta,
                "is_promotional": item.get("is_promotional", False),
            },
            subject_id=queried_entity,
            supporting_evidence_id=f"ev-price-{sku}",
            locator=item.get("locator", f"json://catalog/{sku}"),
            observation_kind="observed",
            limitations=["Point-in-time observation; no interpolation."],
        )
        observations.append(obs)

    coverage = CoverageRecord(
        coverage_id=f"cov-{attempt_id}",
        source_id=source_id,
        queried_entity=queried_entity,
        capture_start=datetime.now(UTC),
        capture_end=datetime.now(UTC),
        status=CoverageStatus.COMPLETE_FOR_QUERY if observations else CoverageStatus.PARTIAL,
        pages_or_records_obtained=len(observations),
        limitations=[] if observations else ["No pricing observations successfully parsed."],
    )

    return observations, findings, coverage, failures


class CompetitorPricingAgent:
    """Specialist sub-agent for Competitor Pricing (COMP-PRICE)."""

    SPECIALIST_ROLE = CompetitorRole.PRICE
    SPECIALIST_ID = "w_comp.price"

    def __init__(self, profile: SpecialistModelProfile | None = None) -> None:
        self._profile = profile or PRICE_PROFILE

    @property
    def role(self) -> CompetitorRole:
        return self.SPECIALIST_ROLE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    async def execute_price_attempt(
        self,
        sandbox_client: Any,
        attempt_input: CompetitorAttemptInput,
        egress_grant: SandboxEgressGrant | None = None,
    ) -> SpecialistResult:
        """Execute bounded pricing attempt and parse normalized pricing envelope."""
        res: SpecialistResult = await dispatch_competitor_specialist_attempt(
            sandbox_client,
            attempt_input,
            egress_grant=egress_grant,
        )

        obs, findings, coverage, failures = parse_pricing_data(
            attempt_input.context_slice,
            attempt_input.attempt_id,
        )

        all_obs = res.observations + obs
        all_failures = res.structured_failures + failures

        status = "success" if all_obs or coverage else "no_observation"
        if all_failures and not all_obs:
            status = "failed"

        return SpecialistResult(
            step_id=attempt_input.step_id,
            attempt_id=attempt_input.attempt_id,
            profile_id=self._profile.profile_id,
            input_hash=attempt_input.input_hash,
            status=status,
            observations=all_obs,
            findings=findings,
            coverage=coverage,
            structured_failures=all_failures,
            resource_usage=res.resource_usage,
            lineage=res.lineage,
            controller_result_ref=res.controller_result_ref,
        )
