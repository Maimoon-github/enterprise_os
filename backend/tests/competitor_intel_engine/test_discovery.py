"""Tests for COMP-DISCOVERY specialist, entity resolution, and source admissibility."""

from datetime import UTC, datetime, timedelta

import pytest

from app.agents.competitor_intel_engine.subagents.discovery import (
    CompetitorDiscoveryAgent,
    resolve_entity,
    validate_source_policy,
)
from app.schemas.competitor_intel import (
    CompetitorAttemptInput,
    CompetitorEntity,
    CompetitorRole,
    FailureCode,
    SourcePolicyRecord,
)
from app.schemas.sandbox import SandboxEgressGrant


def test_same_name_unrelated_brands_not_merged():
    """Verify same-name brands with different domains remain distinct and marked ambiguous."""
    confirmed = CompetitorEntity(
        entity_id="ent-acme-hw",
        names=["Acme"],
        domains=["acmehardware.com"],
        resolution_state="confirmed",
    )

    candidate_record = {
        "entity_id": "ent-acme-sw",
        "names": ["Acme"],
        "domains": ["acmesoftware.io"],
        "relationship_kind": "competitor",
    }

    resolved = resolve_entity(candidate_record, confirmed_watchlist=[confirmed])
    # Must NOT merge into ent-acme-hw
    assert resolved.entity_id != confirmed.entity_id
    assert resolved.resolution_state == "ambiguous"
    assert confirmed.entity_id in resolved.unresolved_alternatives


def test_parent_subsidiary_and_reseller_distinction():
    """Verify corporate hierarchies and reseller relationships are explicitly preserved."""
    parent_record = {
        "name": "MegaCorp",
        "domains": ["megacorp.com"],
        "relationship_kind": "parent",
    }
    subsidiary_record = {
        "name": "SubBrand",
        "domains": ["subbrand.com"],
        "relationship_kind": "subsidiary",
    }
    reseller_record = {
        "name": "DiscountRetail",
        "domains": ["discountretail.com"],
        "relationship_kind": "reseller",
    }

    p_ent = resolve_entity(parent_record)
    s_ent = resolve_entity(subsidiary_record)
    r_ent = resolve_entity(reseller_record)

    assert p_ent.relationship_kind == "parent"
    assert s_ent.relationship_kind == "subsidiary"
    assert r_ent.relationship_kind == "reseller"


def test_source_deduplication_and_domain_merging():
    """Verify matching confirmed entity domain updates and deduplicates metadata."""
    confirmed = CompetitorEntity(
        entity_id="ent-brand-1",
        names=["AlphaCorp"],
        domains=["alphacorp.com"],
        platform_ids={"google_ads": "g-123"},
        resolution_state="confirmed",
    )

    duplicate_record = {
        "name": "Alpha Corp International",
        "domains": ["alphacorp.com", "alphacorp.eu"],
        "platform_ids": {"meta_ads": "m-456"},
    }

    resolved = resolve_entity(duplicate_record, confirmed_watchlist=[confirmed])
    assert resolved.entity_id == "ent-brand-1"
    assert resolved.resolution_state == "confirmed"
    assert "alphacorp.eu" in resolved.domains
    assert resolved.platform_ids == {"google_ads": "g-123", "meta_ads": "m-456"}


def test_unapproved_newly_found_domain_is_candidate():
    """Verify newly discovered unapproved domain is marked candidate, requiring IE admission."""
    new_record = {
        "name": "NewCompetitor",
        "domains": ["newcompetitor.com"],
    }
    resolved = resolve_entity(new_record, confirmed_watchlist=[])
    assert resolved.resolution_state == "candidate"


def test_source_admissibility_terms_and_expiration():
    """Verify unverified terms and expired policy fail closed."""
    # Missing terms
    unverified_source = SourcePolicyRecord(
        source_id="src-unverified",
        source_class="official",
        permitted_purpose="transparency_query",
        terms_url="",  # missing
        terms_checked_at=None,
        policy_decision_id="pol-001",
        policy_expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    res_terms = validate_source_policy(unverified_source)
    assert res_terms.is_admissible is False
    assert res_terms.failure_code == FailureCode.SOURCE_TERMS_UNVERIFIED

    # Expired policy
    expired_source = SourcePolicyRecord(
        source_id="src-expired",
        source_class="official",
        permitted_purpose="transparency_query",
        terms_url="https://terms.example.com",
        terms_checked_at=datetime.now(UTC) - timedelta(days=40),
        policy_decision_id="pol-002",
        policy_expires_at=datetime.now(UTC) - timedelta(days=1),  # expired
    )
    res_exp = validate_source_policy(expired_source)
    assert res_exp.is_admissible is False
    assert res_exp.failure_code == FailureCode.GRANT_EXPIRED


def test_source_admissibility_robots_and_regional_coverage():
    """Verify robots denial and unsupported market are detected."""
    # Robots denial
    robots_denied_source = SourcePolicyRecord(
        source_id="src-robots-denied",
        source_class="site",
        permitted_purpose="public_page_capture",
        terms_url="https://example.com/terms",
        terms_checked_at=datetime.now(UTC),
        policy_decision_id="pol-003",
        policy_expires_at=datetime.now(UTC) + timedelta(days=30),
        robots_decision_ref="decision:robots_denied_rfc9309",
        coverage_countries=["US", "CA"],
    )
    res_robots = validate_source_policy(robots_denied_source)
    assert res_robots.is_admissible is False
    assert res_robots.failure_code == FailureCode.ROBOTS_DENIED

    # Unsupported market
    valid_eu_source = SourcePolicyRecord(
        source_id="src-eu-only",
        source_class="official",
        permitted_purpose="transparency_query",
        terms_url="https://example.com/terms",
        terms_checked_at=datetime.now(UTC),
        policy_decision_id="pol-004",
        policy_expires_at=datetime.now(UTC) + timedelta(days=30),
        coverage_countries=["FR", "DE"],
    )
    res_mkt = validate_source_policy(valid_eu_source, target_market="US")
    assert res_mkt.is_admissible is False
    assert res_mkt.failure_code == FailureCode.REGION_UNSUPPORTED

    # Valid market passes
    res_valid = validate_source_policy(valid_eu_source, target_market="DE")
    assert res_valid.is_admissible is True


@pytest.mark.asyncio
async def test_discovery_agent_execute_attempt_roundtrip():
    """Verify discovery agent executes bounded attempt and partitions watchlist delta."""
    agent = CompetitorDiscoveryAgent()

    class MockSandboxClient:
        async def invoke(self, mandate):
            class MockResult:
                success = True
                error = None
                sanitized_output = {"benchmark_price": "29.99", "competitor": "ConfirmedCorp"}
                execution_id = "exec-disc-100"

            return MockResult()

    confirmed_entry = CompetitorEntity(
        entity_id="ent-confirmed-1",
        names=["ConfirmedCorp"],
        domains=["confirmed.com"],
        resolution_state="confirmed",
    )

    attempt_input = CompetitorAttemptInput(
        grant_id="grant-disc-1",
        task_id="task-disc-1",
        tenant_id="tenant-alpha",
        run_id="run-disc-001",
        step_id="step-disc-1",
        attempt_id="att-disc-001",
        role=CompetitorRole.DISCOVERY,
        profile_id="w_comp.discovery.v1",
        llm_instance_id="llm-disc-001",
        approved_operation_ids=["public_page_capture"],
        context_slice={
            "candidate_entities": [
                {"name": "ConfirmedCorp", "domains": ["confirmed.com"]},
                {"name": "NewLeadCorp", "domains": ["newlead.com"]},
            ]
        },
        input_hash="d" * 64,
        deadline=datetime.now(UTC) + timedelta(minutes=5),
    )

    egress_grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-disc-1",
        specialist_id="COMP-DISCOVERY",
        allowed_domains=["confirmed.com", "newlead.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    res, confirmed, proposed = await agent.execute_discovery_attempt(
        MockSandboxClient(),
        attempt_input,
        egress_grant=egress_grant,
        confirmed_watchlist=[confirmed_entry],
    )

    assert res.status == "success"
    assert len(confirmed) == 1
    assert confirmed[0].entity_id == "ent-confirmed-1"
    assert confirmed[0].resolution_state == "confirmed"

    assert len(proposed) == 1
    assert proposed[0].names == ["NewLeadCorp"]
    assert proposed[0].resolution_state == "candidate"
