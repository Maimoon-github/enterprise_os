"""COMP-DISCOVERY: Competitor Discovery Specialist Sub-Agent.

Conducts entity resolution, corporate relationship classification (parent, subsidiary,
reseller), source eligibility validation (terms, robots, region, quotas), and watchlist
delta proposals under strict Model A boundaries. All newly discovered entities and sources
remain PROPOSED/DISABLED until explicit IE/policy admission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.agents.competitor_intel_engine.profiles import (
    DISCOVERY_PROFILE,
    SpecialistModelProfile,
    dispatch_competitor_specialist_attempt,
)
from app.schemas.competitor_intel import (
    CompetitorAttemptInput,
    CompetitorEntity,
    CompetitorRole,
    FailureCode,
    SourcePolicyRecord,
    SpecialistResult,
)
from app.schemas.sandbox import SandboxEgressGrant


@dataclass(frozen=True)
class SourceAdmissibilityResult:
    """Outcome of source eligibility verification."""

    is_admissible: bool
    failure_code: FailureCode | None = None
    reason: str | None = None


def validate_source_policy(
    policy: SourcePolicyRecord,
    target_market: str = "US",
    as_of: datetime | None = None,
) -> SourceAdmissibilityResult:
    """Verify source admissibility before network capture is attempted.

    Enforces terms verification, policy expiration, robots compliance (RFC 9309),
    and regional coverage. Fails closed on any ambiguity.
    """
    check_time = as_of or datetime.now(UTC)

    # 1. Verify terms checked
    if not policy.terms_url or policy.terms_checked_at is None:
        return SourceAdmissibilityResult(
            is_admissible=False,
            failure_code=FailureCode.SOURCE_TERMS_UNVERIFIED,
            reason=f"Terms of service for source '{policy.source_id}' are unverified or missing.",
        )

    # 2. Check expiration
    if policy.policy_expires_at < check_time:
        return SourceAdmissibilityResult(
            is_admissible=False,
            failure_code=FailureCode.GRANT_EXPIRED,
            reason=f"Policy authorization for source '{policy.source_id}' has expired.",
        )

    # 3. Check robots protocol compliance
    if policy.robots_decision_ref and "denied" in policy.robots_decision_ref.lower():
        return SourceAdmissibilityResult(
            is_admissible=False,
            failure_code=FailureCode.ROBOTS_DENIED,
            reason=f"Robots.txt protocol denies capture access to '{policy.source_id}'.",
        )

    # 4. Check regional coverage
    if policy.coverage_countries and target_market not in policy.coverage_countries:
        return SourceAdmissibilityResult(
            is_admissible=False,
            failure_code=FailureCode.REGION_UNSUPPORTED,
            reason=(
                f"Source '{policy.source_id}' does not cover target market '{target_market}'. "
                f"Covered: {policy.coverage_countries}"
            ),
        )

    return SourceAdmissibilityResult(is_admissible=True)


def resolve_entity(
    raw_record: dict[str, Any],
    confirmed_watchlist: list[CompetitorEntity] | None = None,
) -> CompetitorEntity:
    """Resolve an entity identity, disambiguating name collisions and corporate hierarchies.

    - Same-name unrelated brands are assigned distinct IDs and not merged.
    - Parent, subsidiary, and reseller relationships are explicitly typed.
    - Newly discovered domains remain 'candidate' state until IE admission.
    """
    entity_id = raw_record.get("entity_id") or f"ent-{raw_record.get('name', 'unknown').lower()}"
    names = raw_record.get("names") or [raw_record.get("name", "Unknown")]
    domains = raw_record.get("domains") or []
    platform_ids = raw_record.get("platform_ids") or {}
    relationship_kind = raw_record.get("relationship_kind", "competitor")
    jurisdiction = raw_record.get("jurisdiction", "US")

    watchlist = confirmed_watchlist or []
    matched_confirmed: CompetitorEntity | None = None

    # Check for domain-exact match in confirmed watchlist
    for confirmed in watchlist:
        if any(d in confirmed.domains for d in domains):
            matched_confirmed = confirmed
            break

    # Check for name collision with unrelated industry/domain
    for confirmed in watchlist:
        if (
            any(n.lower() in [cn.lower() for cn in confirmed.names] for n in names)
            and matched_confirmed is None
            and confirmed.domains
            and domains
        ):
            # Name collision detected across distinct domains
            return CompetitorEntity(
                entity_id=f"{entity_id}-collision-{domains[0]}",
                names=names,
                aliases=raw_record.get("aliases", []),
                domains=domains,
                platform_ids=platform_ids,
                relationship_kind=relationship_kind,
                jurisdiction=jurisdiction,
                resolution_state="ambiguous",
                unresolved_alternatives=[confirmed.entity_id],
            )

    if matched_confirmed:
        return CompetitorEntity(
            entity_id=matched_confirmed.entity_id,
            names=list(set(matched_confirmed.names + names)),
            aliases=list(set(matched_confirmed.aliases + raw_record.get("aliases", []))),
            domains=list(set(matched_confirmed.domains + domains)),
            platform_ids={**matched_confirmed.platform_ids, **platform_ids},
            relationship_kind=relationship_kind,
            jurisdiction=jurisdiction,
            resolution_state="confirmed",
        )

    # Newly discovered unapproved entity -> candidate proposal
    return CompetitorEntity(
        entity_id=entity_id,
        names=names,
        aliases=raw_record.get("aliases", []),
        domains=domains,
        platform_ids=platform_ids,
        relationship_kind=relationship_kind,
        jurisdiction=jurisdiction,
        resolution_state="candidate",
    )


class CompetitorDiscoveryAgent:
    """Specialist sub-agent for Competitor Discovery (w_comp.discovery)."""

    SPECIALIST_ROLE = CompetitorRole.DISCOVERY
    SPECIALIST_ID = "w_comp.discovery"

    def __init__(self, profile: SpecialistModelProfile | None = None) -> None:
        self._profile = profile or DISCOVERY_PROFILE

    @property
    def role(self) -> CompetitorRole:
        return self.SPECIALIST_ROLE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    @property
    def profile(self) -> SpecialistModelProfile:
        return self._profile

    async def execute_discovery_attempt(
        self,
        sandbox_client: Any,
        attempt_input: CompetitorAttemptInput,
        egress_grant: SandboxEgressGrant | None = None,
        confirmed_watchlist: list[CompetitorEntity] | None = None,
    ) -> tuple[SpecialistResult, list[CompetitorEntity], list[CompetitorEntity]]:
        """Execute bounded discovery attempt and separate confirmed entities from proposed delta.

        Returns (SpecialistResult, confirmed_entities, proposed_watchlist_delta).
        """
        # Dispatch attempt through sandbox boundary
        res: SpecialistResult = await dispatch_competitor_specialist_attempt(
            sandbox_client,
            attempt_input,
            egress_grant=egress_grant,
        )

        context_slice = attempt_input.context_slice
        candidate_records = context_slice.get("candidate_entities", [])

        confirmed_entities: list[CompetitorEntity] = []
        proposed_delta: list[CompetitorEntity] = []

        for record in candidate_records:
            resolved = resolve_entity(record, confirmed_watchlist=confirmed_watchlist)
            if resolved.resolution_state == "confirmed":
                confirmed_entities.append(resolved)
            else:
                proposed_delta.append(resolved)

        return res, confirmed_entities, proposed_delta
