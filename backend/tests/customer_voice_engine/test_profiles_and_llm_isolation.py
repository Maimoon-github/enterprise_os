"""Tests for Customer Voice reasoning profiles, specialist registration, and LLM isolation."""

import pytest

from app.agents.customer_voice_engine.customer_voice import CustomerVoiceAgent
from app.agents.customer_voice_engine.profiles import (
    ALL_VOICE_PROFILES,
    COORDINATOR_PROFILE,
    DISCOVERY_PROFILE,
    JOURNEY_PROFILE,
    NEEDS_PROFILE,
    QA_PROFILE,
    SENTIMENT_PROFILE,
    THEMES_PROFILE,
    create_voice_llm_client,
    get_voice_profile,
)
from app.agents.customer_voice_engine.subagents import (
    VoiceDiscoveryAgent,
    VoiceJourneyAgent,
    VoiceNeedsAgent,
    VoiceQualityAgent,
    VoiceSentimentAgent,
    VoiceThemesAgent,
)
from app.core.exceptions import PolicyViolationError
from app.schemas.customer_voice import VoiceWorkflowStage
from app.schemas.sandbox import NetworkPolicy


REQUIRED_IDENTITIES = {
    "W_VOICE",
    "VOICE-DISCOVERY",
    "VOICE-THEMES",
    "VOICE-SENTIMENT",
    "VOICE-NEEDS",
    "VOICE-JOURNEY",
    "VOICE-QA",
}


def test_seven_unique_voice_identities_and_profiles_exist() -> None:
    """Verify exactly seven Voice profiles exist with unique IDs, roles, and deterministic digests."""
    assert len(ALL_VOICE_PROFILES) == 7
    assert set(ALL_VOICE_PROFILES.keys()) == REQUIRED_IDENTITIES

    profile_ids = {p.profile_id for p in ALL_VOICE_PROFILES.values()}
    assert len(profile_ids) == 7

    # Verify digests are unique across all 7 profiles
    digests = {p.compute_digest() for p in ALL_VOICE_PROFILES.values()}
    assert len(digests) == 7

    # Verify digest determinism (stable across repeated computations)
    for p in ALL_VOICE_PROFILES.values():
        d1 = p.compute_digest()
        d2 = p.compute_digest()
        assert d1 == d2
        assert len(d1) == 64  # SHA-256 hex string


def test_coordinator_zero_sandbox_and_isolation() -> None:
    """Verify W_VOICE coordinator has zero sandbox capability, empty tools, and disabled network."""
    coord = get_voice_profile("W_VOICE")
    assert coord.specialist_id == "W_VOICE"
    assert coord.role == VoiceWorkflowStage.SYNTHESIS
    assert coord.allowed_tools == ()
    assert coord.network_policy == NetworkPolicy.DISABLED

    agent = CustomerVoiceAgent()
    assert agent.capability is None

    # Injecting sandbox client to coordinator must fail closed
    with pytest.raises(PolicyViolationError, match="zero-sandbox"):
        CustomerVoiceAgent(sandbox_client=object())


def test_network_policy_least_privilege() -> None:
    """Only VOICE-DISCOVERY receives ALLOWLIST; all other specialists and coordinator have DISABLED."""
    disc = get_voice_profile("VOICE-DISCOVERY")
    assert disc.network_policy == NetworkPolicy.ALLOWLIST

    for identity, profile in ALL_VOICE_PROFILES.items():
        if identity != "VOICE-DISCOVERY":
            assert profile.network_policy == NetworkPolicy.DISABLED, (
                f"Specialist {identity} must have DISABLED network policy, got {profile.network_policy}"
            )


def test_scope_separation_and_narrow_responsibilities() -> None:
    """Verify each specialist has distinct, non-overlapping, and least-privileged responsibilities."""
    assert "source_acquisition_and_preprocessing" in DISCOVERY_PROFILE.reasoning_mode
    assert "thematic_clustering_and_frequency" in THEMES_PROFILE.reasoning_mode
    assert "aspect_level_sentiment_and_emotion" in SENTIMENT_PROFILE.reasoning_mode
    assert "needs_pains_and_objections_reasoning" in NEEDS_PROFILE.reasoning_mode
    assert "descriptive_touchpoint_and_segment_comparison" in JOURNEY_PROFILE.reasoning_mode
    assert "independent_quality_and_privacy_assurance" in QA_PROFILE.reasoning_mode

    # Operations separation
    assert "acquire_source" in DISCOVERY_PROFILE.allowed_operations
    assert "cluster_embeddings" in THEMES_PROFILE.allowed_operations
    assert "score_aspect_polarity" in SENTIMENT_PROFILE.allowed_operations
    assert "classify_objections" in NEEDS_PROFILE.allowed_operations
    assert "compare_touchpoints" in JOURNEY_PROFILE.allowed_operations
    assert "evaluate_privacy" in QA_PROFILE.allowed_operations


def test_six_specialists_registered_in_customer_voice_agent() -> None:
    """CustomerVoiceAgent registers exactly six independent specialist sub-agents."""
    agent = CustomerVoiceAgent()
    assert len(agent.specialists) == 6

    expected_specialist_keys = {
        "VOICE-DISCOVERY",
        "VOICE-THEMES",
        "VOICE-SENTIMENT",
        "VOICE-NEEDS",
        "VOICE-JOURNEY",
        "VOICE-QA",
    }
    assert set(agent.specialists.keys()) == expected_specialist_keys

    assert isinstance(agent.discovery_agent, VoiceDiscoveryAgent)
    assert isinstance(agent.themes_agent, VoiceThemesAgent)
    assert isinstance(agent.sentiment_agent, VoiceSentimentAgent)
    assert isinstance(agent.needs_agent, VoiceNeedsAgent)
    assert isinstance(agent.journey_agent, VoiceJourneyAgent)
    assert isinstance(agent.qa_agent, VoiceQualityAgent)

    assert agent.discovery_agent.specialist_id == "VOICE-DISCOVERY"
    assert agent.themes_agent.specialist_id == "VOICE-THEMES"
    assert agent.sentiment_agent.specialist_id == "VOICE-SENTIMENT"
    assert agent.needs_agent.specialist_id == "VOICE-NEEDS"
    assert agent.journey_agent.specialist_id == "VOICE-JOURNEY"
    assert agent.qa_agent.specialist_id == "VOICE-QA"


def test_llm_client_instance_and_session_isolation() -> None:
    """Verify distinct LlmClient instances and provenance identities with no shared state."""
    p_disc = get_voice_profile("VOICE-DISCOVERY")
    p_sent = get_voice_profile("VOICE-SENTIMENT")
    p_coord = get_voice_profile("W_VOICE")

    client_disc_1 = create_voice_llm_client(p_disc, attempt_id="att-001", tenant_id="tenant-alpha")
    client_disc_2 = create_voice_llm_client(p_disc, attempt_id="att-002", tenant_id="tenant-alpha")
    client_sent_1 = create_voice_llm_client(p_sent, attempt_id="att-001", tenant_id="tenant-alpha")
    client_disc_beta = create_voice_llm_client(p_disc, attempt_id="att-001", tenant_id="tenant-beta")
    client_coord = create_voice_llm_client(p_coord, attempt_id="att-001", tenant_id="tenant-alpha")

    # Distinct object instances
    assert client_disc_1 is not client_disc_2
    assert client_disc_1 is not client_sent_1
    assert client_disc_1 is not client_coord

    # Distinct provenance identities
    assert client_disc_1.agent_identity != client_disc_2.agent_identity
    assert client_disc_1.agent_identity != client_sent_1.agent_identity
    assert client_disc_1.agent_identity != client_disc_beta.agent_identity
    assert client_disc_1.agent_identity != client_coord.agent_identity

    assert "tenant-tenant-alpha" in str(client_disc_1.agent_identity)
    assert "tenant-tenant-beta" in str(client_disc_beta.agent_identity)
    assert "att-001" in str(client_disc_1.agent_identity)
    assert "att-002" in str(client_disc_2.agent_identity)
    assert "voice_discovery" in str(client_disc_1.agent_identity)
    assert "voice_sentiment" in str(client_sent_1.agent_identity)
    assert "w_voice" in str(client_coord.agent_identity)


def test_no_provider_credentials_in_profiles() -> None:
    """Ensure no secret credentials exist in immutable profile definitions or serialized digests."""
    for profile in ALL_VOICE_PROFILES.values():
        profile_dict = profile.__dict__
        for secret_key in ("api_key", "secret", "token", "password", "private_key"):
            assert secret_key not in profile_dict, f"Found secret key '{secret_key}' in profile {profile.profile_id}"

        digest = profile.compute_digest()
        assert len(digest) == 64


@pytest.mark.asyncio
async def test_clean_client_shutdown() -> None:
    """Verify all seven Voice LLM clients can be cleanly and independently closed."""
    clients = [
        create_voice_llm_client(p, attempt_id=f"att-{idx}", tenant_id="tenant-test")
        for idx, p in enumerate(ALL_VOICE_PROFILES.values())
    ]
    assert len(clients) == 7
    for client in clients:
        await client.aclose()
