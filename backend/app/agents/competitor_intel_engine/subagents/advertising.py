"""COMP-ADS: Competitor Advertising & Transparency Specialist Sub-Agent.

Extracts official transparency library metadata, creative assets, disclosed date horizons,
and reach ranges without fabricating spend, performance, targeting, or campaign termination.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.agents.competitor_intel_engine.profiles import (
    ADS_PROFILE,
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


def parse_ad_transparency_data(
    raw_payload: dict[str, Any],
    attempt_id: str,
) -> tuple[list[Observation], list[Finding], CoverageRecord, list[dict[str, Any]]]:
    """Parse ad transparency records under strict truth and disclosure boundaries.

    - Reach ranges remain ranges; no invented single-point impressions.
    - No fabricated spend, targeting, or campaign ROI estimates.
    - Disappeared ad is not inferred as campaign termination.
    - Pagination truncation returns partial coverage with explicit limitation.
    """
    observations: list[Observation] = []
    findings: list[Finding] = []
    failures: list[dict[str, Any]] = []

    ads_data = raw_payload.get("ads", [])
    total_found = raw_payload.get("total_count", len(ads_data))
    is_truncated = raw_payload.get("is_truncated", False)
    queried_entity = raw_payload.get("advertiser", raw_payload.get("competitor", "Unknown"))
    source_id = raw_payload.get("source_id", "src-ad-transparency")

    # Reject requests/records attempting to fabricate spend or private targeting
    if "fabricated_spend" in raw_payload or "inferred_budget" in raw_payload:
        failures.append({
            "code": FailureCode.POLICY_DENIED,
            "message": "Direct inference of ad spend from public library is forbidden.",
        })

    for idx, ad in enumerate(ads_data):
        ad_id = ad.get("ad_id") or f"ad-{attempt_id}-{idx}"
        advertiser_id = ad.get("advertiser_id") or queried_entity

        # Reach range preservation
        reach_range = ad.get("reach_range") or ad.get("impressions_range")
        disclosed_targeting = ad.get("disclosed_targeting")

        # Disallow fake exact spend
        spend_est = ad.get("estimated_spend")
        if spend_est is not None:
            failures.append({
                "code": FailureCode.POLICY_DENIED,
                "ad_id": ad_id,
                "message": "Disallowed inferred spend in ad payload; suppressed.",
            })

        obs = Observation(
            observation_id=f"obs-{attempt_id}-{ad_id}",
            predicate="ad_metadata",
            typed_value={
                "ad_id": ad_id,
                "advertiser_id": advertiser_id,
                "first_observed_at": ad.get("first_observed_at", datetime.now(UTC).isoformat()),
                "status": ad.get("status", "active"),
                "reach_range": str(reach_range) if reach_range else "undisclosed",
                "disclosed_targeting": disclosed_targeting or {},
                "ad_copy": ad.get("copy", ""),
            },
            subject_id=advertiser_id,
            supporting_evidence_id=f"ev-ad-{ad_id}",
            locator=f"transparency://ad/{ad_id}",
            observation_kind="observed",
            limitations=["Public transparency library snapshot; spend and performance unobserved."],
        )
        observations.append(obs)

    coverage = CoverageRecord(
        coverage_id=f"cov-{attempt_id}",
        source_id=source_id,
        queried_entity=queried_entity,
        capture_start=datetime.now(UTC),
        capture_end=datetime.now(UTC),
        status=CoverageStatus.PARTIAL if is_truncated else CoverageStatus.COMPLETE_FOR_QUERY,
        pages_or_records_obtained=len(ads_data),
        provider_declared_total=total_found,
        depth_cursor_exhausted=not is_truncated,
        limitations=["Pagination truncated at limit."] if is_truncated else [],
    )

    return observations, findings, coverage, failures


class CompetitorAdvertisingAgent:
    """Specialist sub-agent for Competitor Advertising metadata (COMP-ADS)."""

    SPECIALIST_ROLE = CompetitorRole.ADS
    SPECIALIST_ID = "w_comp.ads"

    def __init__(self, profile: SpecialistModelProfile | None = None) -> None:
        self._profile = profile or ADS_PROFILE

    @property
    def role(self) -> CompetitorRole:
        return self.SPECIALIST_ROLE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    async def execute_ads_attempt(
        self,
        sandbox_client: Any,
        attempt_input: CompetitorAttemptInput,
        egress_grant: SandboxEgressGrant | None = None,
    ) -> SpecialistResult:
        """Execute bounded ads attempt and parse disclosed metadata envelope."""
        res: SpecialistResult = await dispatch_competitor_specialist_attempt(
            sandbox_client,
            attempt_input,
            egress_grant=egress_grant,
        )

        obs, findings, coverage, failures = parse_ad_transparency_data(
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
