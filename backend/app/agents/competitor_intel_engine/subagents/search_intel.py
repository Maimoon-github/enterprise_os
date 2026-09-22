"""COMP-SEARCH: Competitor SERP & Search Intelligence Specialist Sub-Agent.

Captures query-specific search ranking rows, organic vs. paid separation, and
provider visibility estimates. Unobserved results at search depth are never
equated to unranked; content gaps require an authoritative brand inventory baseline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.agents.competitor_intel_engine.profiles import (
    SEARCH_PROFILE,
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


def parse_search_data(
    raw_payload: dict[str, Any],
    attempt_id: str,
) -> tuple[list[Observation], list[Finding], CoverageRecord, list[dict[str, Any]]]:
    """Parse SERP and keyword rankings with organic/paid separation and estimate labeling."""
    observations: list[Observation] = []
    findings: list[Finding] = []
    failures: list[dict[str, Any]] = []

    serp_rows = raw_payload.get("serp_rows", [])
    provider_metrics = raw_payload.get("provider_metrics", {})
    brand_inventory = raw_payload.get("brand_page_inventory")
    query = raw_payload.get("query", "unknown")
    provider = raw_payload.get("provider", "google")
    depth_limit = raw_payload.get("depth_limit", 10)
    source_id = raw_payload.get("source_id", "src-search-api")

    # 1. Parse individual ranking rows
    for row in serp_rows:
        rank = row.get("rank")
        result_type = row.get("result_type", "organic")  # organic or paid
        url = row.get("url", "")
        domain = row.get("domain", "")

        obs = Observation(
            observation_id=f"obs-{attempt_id}-rank-{rank}",
            predicate=f"serp_{result_type}_rank",
            typed_value={
                "query": query,
                "rank": rank,
                "result_type": result_type,
                "url": url,
                "domain": domain,
                "provider": provider,
            },
            subject_id=domain or query,
            supporting_evidence_id=f"ev-serp-{query}-{rank}",
            locator=f"serp://{provider}/{query}/pos/{rank}",
            observation_kind="observed",
            limitations=[f"Observed at depth limit {depth_limit}."],
        )
        observations.append(obs)

    # 2. Provider estimates (Volume, Keyword Difficulty)
    if provider_metrics:
        for metric_name, val in provider_metrics.items():
            obs_est = Observation(
                observation_id=f"obs-{attempt_id}-est-{metric_name}",
                predicate=f"provider_estimate_{metric_name}",
                typed_value=val,
                subject_id=query,
                supporting_evidence_id=f"ev-est-{query}-{metric_name}",
                locator=f"provider://{provider}/metrics/{metric_name}",
                observation_kind="provider_estimate",
                limitations=["Third-party provider estimate; sampled traffic only."],
            )
            observations.append(obs_est)

    # 3. Content-gap evaluation
    if raw_payload.get("check_content_gap", False) and not brand_inventory:
        failures.append({
            "code": FailureCode.BASELINE_MISSING,
            "query": query,
            "message": (
                "Own-brand page inventory missing; competitor evidence captured, "
                "but confirmed brand content gap cannot be established."
            ),
        })

    coverage = CoverageRecord(
        coverage_id=f"cov-{attempt_id}",
        source_id=source_id,
        queried_entity=query,
        capture_start=datetime.now(UTC),
        capture_end=datetime.now(UTC),
        status=CoverageStatus.COMPLETE_FOR_QUERY if serp_rows else CoverageStatus.PARTIAL,
        pages_or_records_obtained=len(serp_rows),
        limitations=[f"Sampled at depth {depth_limit}; unobserved results != unranked."],
    )

    return observations, findings, coverage, failures


class CompetitorSearchIntelAgent:
    """Specialist sub-agent for Competitor Search and SERP Intelligence (COMP-SEARCH)."""

    SPECIALIST_ROLE = CompetitorRole.SEARCH
    SPECIALIST_ID = "w_comp.search"

    def __init__(self, profile: SpecialistModelProfile | None = None) -> None:
        self._profile = profile or SEARCH_PROFILE

    @property
    def role(self) -> CompetitorRole:
        return self.SPECIALIST_ROLE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    async def execute_search_attempt(
        self,
        sandbox_client: Any,
        attempt_input: CompetitorAttemptInput,
        egress_grant: SandboxEgressGrant | None = None,
    ) -> SpecialistResult:
        """Execute bounded search attempt and parse SERP rankings envelope."""
        res: SpecialistResult = await dispatch_competitor_specialist_attempt(
            sandbox_client,
            attempt_input,
            egress_grant=egress_grant,
        )

        obs, findings, coverage, failures = parse_search_data(
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
