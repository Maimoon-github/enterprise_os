"""COMP-POSITION: Competitor Positioning & Messaging Specialist Sub-Agent.

Captures verbatim value propositions, feature claims, and messaging changes from
approved competitor landing pages. Enforces strict epistemic separation between
'competitor states X' and X being true; rejects sentiment, reviews, and creative generation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.agents.competitor_intel_engine.profiles import (
    POSITION_PROFILE,
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

# Forbidden task requests outside W_COMP scope
FORBIDDEN_OPERATIONS = frozenset({
    "sentiment_analysis",
    "review_mining",
    "persona_generation",
    "creative_generation",
    "copy_generation",
})


def parse_positioning_data(
    raw_payload: dict[str, Any],
    attempt_id: str,
) -> tuple[list[Observation], list[Finding], CoverageRecord, list[dict[str, Any]]]:
    """Parse messaging and value proposition spans with truth separation and scope restrictions.

    - Rejects customer reviews, sentiment, personas, or creative generation.
    - Stated claims are recorded as statements made by competitor, not objective facts.
    - Compares against baseline for semantic vs cosmetic differences.
    """
    observations: list[Observation] = []
    findings: list[Finding] = []
    failures: list[dict[str, Any]] = []

    requested_op = raw_payload.get("operation", "")
    if requested_op in FORBIDDEN_OPERATIONS or raw_payload.get("include_customer_reviews"):
        failures.append({
            "code": FailureCode.ROLE_DENIED,
            "message": (
                f"Operation '{requested_op}' (or review/sentiment analysis) "
                "is forbidden for W_COMP. Creative and customer voice tasks "
                "belong to W_CREAT / W_VOICE."
            ),
        })
        coverage = CoverageRecord(
            coverage_id=f"cov-{attempt_id}",
            source_id="src-positioning",
            queried_entity="unknown",
            capture_start=datetime.now(UTC),
            capture_end=datetime.now(UTC),
            status=CoverageStatus.DENIED,
            pages_or_records_obtained=0,
            limitations=["Forbidden operation rejected fail-closed."],
        )
        return observations, findings, coverage, failures

    messages = raw_payload.get("messaging_spans", [])
    queried_entity = raw_payload.get("competitor", "Unknown")
    baseline_spans = raw_payload.get("baseline_messaging", {})
    source_id = raw_payload.get("source_id", "src-public-page")

    for idx, item in enumerate(messages):
        span_id = item.get("id") or f"span-{attempt_id}-{idx}"
        claim_text = item.get("verbatim_text") or item.get("stated_claim", "")
        placement = item.get("placement", "hero_banner")
        page_url = item.get("page_url", "https://competitor.com")

        # Baseline comparison
        baseline_text = baseline_spans.get(placement)
        is_changed = False
        change_kind = "unobserved"

        if baseline_text:
            if baseline_text.strip().lower() != claim_text.strip().lower():
                is_changed = True
                change_kind = (
                    "semantic_change"
                    if len(claim_text) != len(baseline_text)
                    else "cosmetic"
                )
        elif baseline_spans:
            is_changed = True
            change_kind = "new_placement"

        obs = Observation(
            observation_id=f"obs-{attempt_id}-{span_id}",
            predicate="stated_value_proposition",
            typed_value={
                "verbatim_claim": claim_text,
                "placement": placement,
                "page_url": page_url,
                "is_changed": is_changed,
                "change_kind": change_kind,
                "truth_status": "competitor_statement_only",
            },
            subject_id=queried_entity,
            supporting_evidence_id=f"ev-pos-{span_id}",
            locator=f"dom://{placement}",
            observation_kind="observed",
            limitations=[
                "Captures what competitor states; does not verify underlying product efficacy."
            ],
        )
        observations.append(obs)

        if is_changed:
            findings.append(
                Finding(
                    finding_id=f"find-{attempt_id}-{span_id}",
                    claim_text=(
                        f"Competitor stated change at '{placement}': "
                        f"detected {change_kind} messaging change."
                    ),
                    finding_kind="derived_fact",
                    supporting_evidence_ids=[f"ev-pos-{span_id}"],
                    rationale_summary=(
                        f"Compared against baseline messaging for placement '{placement}'."
                    ),
                )
            )

    coverage = CoverageRecord(
        coverage_id=f"cov-{attempt_id}",
        source_id=source_id,
        queried_entity=queried_entity,
        capture_start=datetime.now(UTC),
        capture_end=datetime.now(UTC),
        status=CoverageStatus.COMPLETE_FOR_QUERY if observations else CoverageStatus.PARTIAL,
        pages_or_records_obtained=len(observations),
        limitations=["Scoped to admitted landing pages."],
    )

    return observations, findings, coverage, failures


class CompetitorPositioningAgent:
    """Specialist sub-agent for Competitor Messaging and Positioning (COMP-POSITION)."""

    SPECIALIST_ROLE = CompetitorRole.POSITION
    SPECIALIST_ID = "w_comp.position"

    def __init__(self, profile: SpecialistModelProfile | None = None) -> None:
        self._profile = profile or POSITION_PROFILE

    @property
    def role(self) -> CompetitorRole:
        return self.SPECIALIST_ROLE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    async def execute_position_attempt(
        self,
        sandbox_client: Any,
        attempt_input: CompetitorAttemptInput,
        egress_grant: SandboxEgressGrant | None = None,
    ) -> SpecialistResult:
        """Execute bounded positioning attempt and parse messaging claims envelope."""
        res: SpecialistResult = await dispatch_competitor_specialist_attempt(
            sandbox_client,
            attempt_input,
            egress_grant=egress_grant,
        )

        obs, findings, coverage, failures = parse_positioning_data(
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
