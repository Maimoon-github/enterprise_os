"""Tests for Competitor Intel Engine reasoning profiles and LLM session isolation."""

from app.agents.competitor_intel_engine.profiles import (
    ALL_COMPETITOR_PROFILES,
    create_competitor_llm_client,
    get_competitor_profile,
)
from app.schemas.competitor_intel import CompetitorRole
from app.schemas.sandbox import NetworkPolicy


def test_seven_unique_profiles_exist():
    """Verify exactly seven profiles exist with unique IDs and roles."""
    assert len(ALL_COMPETITOR_PROFILES) == 7
    roles = {p.role for p in ALL_COMPETITOR_PROFILES.values()}
    assert roles == set(CompetitorRole)

    profile_ids = {p.profile_id for p in ALL_COMPETITOR_PROFILES.values()}
    assert len(profile_ids) == 7

    # Verify digests are unique
    digests = {p.compute_digest() for p in ALL_COMPETITOR_PROFILES.values()}
    assert len(digests) == 7


def test_coordinator_profile_has_no_execution_or_network():
    """Verify W_COMP coordinator has empty operations, empty tools, and disabled network."""
    coord = get_competitor_profile(CompetitorRole.COORDINATOR)
    assert coord.allowed_operations == ()
    assert coord.allowed_tools == ()
    assert coord.network_policy == NetworkPolicy.DISABLED


def test_synthesis_profile_has_disabled_network():
    """Verify COMP-SYNTH has zero research-network egress."""
    synth = get_competitor_profile(CompetitorRole.SYNTHESIS)
    assert synth.network_policy == NetworkPolicy.DISABLED
    assert synth.allowed_operations == ("evidence_synthesize",)


def test_llm_client_instance_and_session_isolation():
    """Verify every client creation yields a distinct instance and unique identity."""
    p_disc = get_competitor_profile(CompetitorRole.DISCOVERY)
    p_ads = get_competitor_profile(CompetitorRole.ADS)

    client_disc_1 = create_competitor_llm_client(p_disc, attempt_id="att-001", tenant_id="t1")
    client_disc_2 = create_competitor_llm_client(p_disc, attempt_id="att-002", tenant_id="t1")
    client_ads_1 = create_competitor_llm_client(p_ads, attempt_id="att-001", tenant_id="t1")
    client_disc_t2 = create_competitor_llm_client(p_disc, attempt_id="att-001", tenant_id="t2")

    # Distinct objects
    assert client_disc_1 is not client_disc_2
    assert client_disc_1 is not client_ads_1

    # Distinct identities preventing cross-session or cross-tenant leakage
    assert client_disc_1.agent_identity != client_disc_2.agent_identity
    assert client_disc_1.agent_identity != client_ads_1.agent_identity
    assert client_disc_1.agent_identity != client_disc_t2.agent_identity

    assert "tenant-t1" in str(client_disc_1.agent_identity)
    assert "tenant-t2" in str(client_disc_t2.agent_identity)
    assert "att-001" in str(client_disc_1.agent_identity)
    assert "att-002" in str(client_disc_2.agent_identity)
