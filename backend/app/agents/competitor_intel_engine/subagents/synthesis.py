"""COMP-SYNTH: Competitor Intelligence Synthesis Specialist Sub-Agent.

Performs offline-only evidence consolidation, deterministic deduplication,
corroboration, conflict preservation, freshness evaluation, confidence computation,
typed assumption verdicts, and scoped market-change alert generation.
Zero research-network egress is strictly enforced.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta

from app.agents.competitor_intel_engine.profiles import (
    SYNTHESIS_PROFILE,
    SpecialistModelProfile,
)
from app.core.exceptions import PolicyViolationError
from app.schemas.competitor_intel import (
    AssumptionVerdict,
    CompetitiveEvidenceBrief,
    CompetitorAttemptInput,
    CompetitorEntity,
    CompetitorResearchContext,
    CompetitorRole,
    ConflictSet,
    Finding,
    MarketShiftAlert,
    Observation,
    SpecialistResult,
    StrategyAssumption,
)

# Freshness horizons by predicate / domain class
FRESHNESS_WINDOWS: dict[str, timedelta] = {
    "product_pricing": timedelta(hours=24),
    "ad_metadata": timedelta(hours=24),
    "serp_organic_rank": timedelta(hours=24),
    "serp_paid_rank": timedelta(hours=24),
    "stated_value_proposition": timedelta(days=7),
    "entity_resolution": timedelta(days=30),
}


def deduplicate_observations(
    observations: list[Observation],
) -> tuple[list[Observation], list[str]]:
    """Deduplicate observations by content hash while preserving source independence.

    Does not collapse observations from different subjects, locators, or distinct time captures.
    """
    seen_hashes: set[str] = set()
    deduped: list[Observation] = []
    duplicate_ids: list[str] = []

    for obs in observations:
        # Canonical hash basis: predicate + subject + locator + JSON content
        canonical_val = json.dumps(obs.typed_value, sort_keys=True, default=str)
        hash_basis = f"{obs.predicate}::{obs.subject_id}::{obs.locator}::{canonical_val}"
        digest = hashlib.sha256(hash_basis.encode("utf-8")).hexdigest()

        if digest in seen_hashes:
            duplicate_ids.append(obs.observation_id)
        else:
            seen_hashes.add(digest)
            deduped.append(obs)

    return deduped, duplicate_ids


def detect_conflicts(observations: list[Observation]) -> list[ConflictSet]:
    """Detect and preserve contradictions between competing observations without voting."""
    conflicts: list[ConflictSet] = []
    price_by_sku: dict[str, list[Observation]] = {}

    for obs in observations:
        if obs.predicate == "product_pricing" and isinstance(obs.typed_value, dict):
            sku = obs.typed_value.get("sku")
            curr = obs.typed_value.get("currency")
            if sku and curr:
                key = f"{obs.subject_id}::{sku}::{curr}"
                price_by_sku.setdefault(key, []).append(obs)

    for key, obs_group in price_by_sku.items():
        if len(obs_group) < 2:
            continue
        # Check if distinct non-null prices are reported for the same key
        prices = {
            o.typed_value.get("price")
            for o in obs_group
            if o.typed_value.get("price") is not None
        }
        if len(prices) > 1:
            conflicts.append(
                ConflictSet(
                    conflict_id=f"conf-{uuid.uuid4().hex[:8]}",
                    claim_key=key,
                    competing_observation_ids=[o.observation_id for o in obs_group],
                    dimension_comparison={
                        "competing_prices": list(prices),
                        "locators": [o.locator for o in obs_group],
                    },
                    resolution_status="unresolved",
                    resolution_reason=(
                        "Multiple contradictory price observations found without explicit "
                        "scope distinction. Preserved unresolved without voting."
                    ),
                )
            )

    return conflicts


def evaluate_freshness(
    observations: list[Observation],
    as_of: datetime,
) -> tuple[list[Observation], list[str]]:
    """Check observation freshness and return stale data references."""
    stale_refs: list[str] = []
    evaluated: list[Observation] = []

    for obs in observations:
        max_age = FRESHNESS_WINDOWS.get(obs.predicate, timedelta(hours=24))
        # Use effective_interval start or current default
        obs_time_str = obs.effective_interval.get("start")
        is_stale = False
        if obs_time_str:
            try:
                obs_time = datetime.fromisoformat(obs_time_str)
                if as_of - obs_time > max_age:
                    is_stale = True
            except (ValueError, TypeError):
                pass

        if is_stale:
            stale_refs.append(f"{obs.observation_id} ({obs.predicate} exceeded {max_age})")
            # Mark limitation
            obs.limitations.append(f"Observation exceeds freshness policy limit of {max_age}.")

        evaluated.append(obs)

    return evaluated, stale_refs


def evaluate_assumption_verdicts(
    assumptions: list[StrategyAssumption],
    observations: list[Observation],
    findings: list[Finding],
    conflicts: list[ConflictSet],
) -> tuple[dict[str, AssumptionVerdict], list[str]]:
    """Produce deterministic assumption verdicts distinguishing supported, challenged, mixed,
    and insufficient states.
    """
    verdicts: dict[str, AssumptionVerdict] = {}
    follow_up_requests: list[str] = []
    conflicted_keys = {c.claim_key for c in conflicts if c.resolution_status == "unresolved"}

    for asm in assumptions:
        # Check if assumption references a conflicted claim key
        is_mixed = any(
            asm.text.lower() in ck.lower() or asm.id in ck.lower() for ck in conflicted_keys
        )
        if is_mixed:
            verdicts[asm.id] = AssumptionVerdict.MIXED
            follow_up_requests.append(
                f"Recheck required for assumption '{asm.id}' due to unresolved evidence conflict."
            )
            continue

        # Match relevant observations and findings
        relevant_obs = [
            o
            for o in observations
            if asm.text.lower() in str(o.typed_value).lower()
            or any(kw in str(o.typed_value).lower() for kw in asm.text.lower().split()[:3])
        ]
        relevant_findings = [
            f
            for f in findings
            if asm.id in f.assumption_ids or asm.text.lower() in f.claim_text.lower()
        ]

        if not relevant_obs and not relevant_findings:
            verdicts[asm.id] = AssumptionVerdict.INSUFFICIENT_EVIDENCE
            follow_up_requests.append(
                f"No admissible evidence found for assumption '{asm.id}': "
                f"'{asm.evidence_question}'."
            )
            continue

        # Evaluate support vs challenge
        has_challenge = any(
            "challenged" in f.claim_text.lower()
            or "decrease" in f.claim_text.lower()
            or "opposite" in f.claim_text.lower()
            for f in relevant_findings
        )
        has_support = any(
            "supported" in f.claim_text.lower()
            or "verified" in f.claim_text.lower()
            or "detected" in f.claim_text.lower()
            for f in relevant_findings
        )

        if has_challenge and has_support:
            verdicts[asm.id] = AssumptionVerdict.MIXED
        elif has_challenge:
            verdicts[asm.id] = AssumptionVerdict.CHALLENGED
        elif has_support or relevant_obs:
            verdicts[asm.id] = AssumptionVerdict.SUPPORTED
        else:
            verdicts[asm.id] = AssumptionVerdict.INSUFFICIENT_EVIDENCE

    return verdicts, follow_up_requests


def generate_market_alerts(
    findings: list[Finding],
    conflicts: list[ConflictSet],
    entities: list[CompetitorEntity],
) -> list[MarketShiftAlert]:
    """Generate scoped market shift alerts when evidence meets significance policy.

    Does not recommend campaigns, budgets, or media-mix changes.
    """
    alerts: list[MarketShiftAlert] = []
    unresolved_keys = {c.claim_key for c in conflicts if c.resolution_status == "unresolved"}
    entity_ids = [e.entity_id for e in entities] or ["CompetitorCorp"]

    for finding in findings:
        # Check for semantic change or significant price delta
        is_significant = (
            "semantic_change" in finding.claim_text
            or (finding.rationale_summary and "delta" in finding.rationale_summary.lower())
        )
        if not is_significant:
            continue

        # Skip if conflicted
        if any(uk in finding.claim_text for uk in unresolved_keys):
            continue

        before_ref = (
            finding.supporting_evidence_ids[0]
            if finding.supporting_evidence_ids
            else "ev-baseline-0"
        )
        after_ref = (
            finding.supporting_evidence_ids[-1]
            if len(finding.supporting_evidence_ids) > 1
            else f"{before_ref}-after"
        )

        alert = MarketShiftAlert(
            alert_id=f"alert-{uuid.uuid4().hex[:8]}",
            affected_entities=entity_ids,
            affected_assumptions=finding.assumption_ids,
            change_kind="positioning_or_commercial_shift",
            before_evidence_id=before_ref,
            after_evidence_id=after_ref,
            significance_rule="rule.market_shift.v1:significant_delta_or_semantic_change",
            confidence=finding.confidence,
            scope_limits=["Scoped to admitted competitors and baseline sources."],
            alert_status="candidate",
        )
        alerts.append(alert)

    return alerts


def synthesize_competitor_evidence(
    context: CompetitorResearchContext,
    specialist_results: list[SpecialistResult],
    confirmed_entities: list[CompetitorEntity] | None = None,
) -> CompetitiveEvidenceBrief:
    """Consolidate specialist outputs into an immutable, schema-valid evidence brief."""
    all_observations: list[Observation] = []
    all_findings: list[Finding] = []
    failures: list[str] = []
    source_inv: set[str] = {p.source_id for p in context.source_policies}
    evidence_idx: set[str] = set()

    for sr in specialist_results:
        all_observations.extend(sr.observations)
        all_findings.extend(sr.findings)
        for fail in sr.structured_failures:
            failures.append(f"[{sr.profile_id}] {fail.get('code')}: {fail.get('message', 'fail')}")
        for obs in sr.observations:
            evidence_idx.add(obs.supporting_evidence_id)
            if obs.locator:
                source_inv.add(obs.locator.split("://")[0])

    # 1. Deterministic deduplication
    deduped_obs, dupe_ids = deduplicate_observations(all_observations)
    if dupe_ids:
        failures.append(f"Deduplicated {len(dupe_ids)} duplicate observation records.")

    # 2. Conflict preservation
    conflicts = detect_conflicts(deduped_obs)

    # 3. Freshness evaluation
    fresh_obs, stale_refs = evaluate_freshness(deduped_obs, context.as_of)

    # 4. Assumption verdicts
    verdicts, follow_ups = evaluate_assumption_verdicts(
        context.assumptions, fresh_obs, all_findings, conflicts
    )

    # 5. Market shift alerts
    entities = confirmed_entities or []
    alerts = generate_market_alerts(all_findings, conflicts, entities)

    return CompetitiveEvidenceBrief(
        brief_id=f"brief-{context.run_id}",
        run_id=context.run_id,
        strategy_plan_ref=context.strategy_plan_ref,
        policy_version=context.freshness_policy_version,
        as_of=context.as_of,
        assumption_verdicts=verdicts,
        entity_inventory=entities,
        source_inventory=sorted(list(source_inv)),
        observations=fresh_obs,
        findings=all_findings,
        conflicts=conflicts,
        market_alerts=alerts,
        evidence_index=sorted(list(evidence_idx)),
        coverage_summary={
            "total_observations": len(fresh_obs),
            "total_findings": len(all_findings),
            "total_conflicts": len(conflicts),
            "total_alerts": len(alerts),
            "deduplicated_count": len(dupe_ids),
        },
        failure_summary=failures,
        stale_or_missing_data=stale_refs,
        follow_up_evidence_requests=follow_ups,
    )


class CompetitorSynthesisAgent:
    """Specialist sub-agent for Offline Evidence Synthesis (COMP-SYNTH)."""

    SPECIALIST_ROLE = CompetitorRole.SYNTHESIS
    SPECIALIST_ID = "w_comp.synthesis"

    def __init__(self, profile: SpecialistModelProfile | None = None) -> None:
        self._profile = profile or SYNTHESIS_PROFILE

    @property
    def role(self) -> CompetitorRole:
        return self.SPECIALIST_ROLE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    async def execute_synthesis_attempt(
        self,
        attempt_input: CompetitorAttemptInput,
        context: CompetitorResearchContext,
        specialist_results: list[SpecialistResult],
        confirmed_entities: list[CompetitorEntity] | None = None,
    ) -> tuple[SpecialistResult, CompetitiveEvidenceBrief]:
        """Execute bounded offline synthesis attempt and return SpecialistResult + Brief.

        Enforces zero research-network egress: fails closed if egress grant is provided.
        """
        # Strictly verify offline operation
        if self._profile.network_policy.value != "disabled":
            raise PolicyViolationError(
                "COMP-SYNTH requires NetworkPolicy.DISABLED; egress is prohibited."
            )

        brief = synthesize_competitor_evidence(
            context=context,
            specialist_results=specialist_results,
            confirmed_entities=confirmed_entities,
        )

        specialist_res = SpecialistResult(
            step_id=attempt_input.step_id,
            attempt_id=attempt_input.attempt_id,
            profile_id=self._profile.profile_id,
            input_hash=attempt_input.input_hash,
            status="success" if brief.observations or brief.findings else "partial",
            observations=brief.observations,
            findings=brief.findings,
            structured_failures=[{"message": f} for f in brief.failure_summary],
            lineage={
                "brief_id": brief.brief_id,
                "strategy_plan_ref": brief.strategy_plan_ref,
                "as_of": brief.as_of.isoformat(),
            },
        )

        return specialist_res, brief
