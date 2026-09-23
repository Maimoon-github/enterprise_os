"""Tests for seven distinct LLM profile identities and session isolation."""

from __future__ import annotations

import pytest

from app.agents.learning_performance_engine.profiles import (
    LEARNING_PROFILES,
    PARENT_PROFILE,
    TELEMETRY_PROFILE,
    ATTRIBUTION_PROFILE,
    INCREMENTALITY_PROFILE,
    FATIGUE_PROFILE,
    DECAY_PROFILE,
    QUALITY_PROFILE,
    create_learning_llm_client,
    get_learning_profile,
)
from app.core.exceptions import SandboxInvocationError


def test_seven_immutable_profiles_exist_with_unique_digests() -> None:
    expected_principals = [
        "W_LEARN",
        "LEARN-TELEMETRY",
        "LEARN-ATTRIBUTION",
        "LEARN-INCREMENTALITY",
        "LEARN-FATIGUE",
        "LEARN-DECAY",
        "LEARN-QA",
    ]
    digests = set()
    for principal in expected_principals:
        profile = get_learning_profile(principal)
        assert profile.specialist_id == principal
        digest = profile.compute_digest()
        assert len(digest) == 64
        digests.add(digest)

    # All 7 profiles must have distinct SHA-256 canonical digests
    assert len(digests) == 7


def test_unknown_principal_fails_closed() -> None:
    with pytest.raises(KeyError, match="Unauthorized or unknown Learning principal"):
        get_learning_profile("LEARN-UNAUTHORIZED-SPECIALIST")


def test_parent_coordinator_has_zero_sandbox_tools() -> None:
    parent = get_learning_profile("W_LEARN")
    assert len(parent.allowed_tools) == 0


def test_fresh_client_and_session_isolation_per_attempt_and_retry() -> None:
    profile = get_learning_profile("LEARN-ATTRIBUTION")

    # Initial attempt
    client_1, record_1 = create_learning_llm_client(
        profile,
        tenant_id="tenant-alpha",
        attempt_id="att-1",
        session_id="sess-1",
    )

    # Retry attempt
    client_2, record_2 = create_learning_llm_client(
        profile,
        tenant_id="tenant-alpha",
        attempt_id="att-2",
        session_id="sess-2",
    )

    # Must be distinct client instances
    assert client_1 is not client_2
    assert record_1.client_instance_id != record_2.client_instance_id
    assert record_1.attempt_id != record_2.attempt_id
    assert record_1.session_id != record_2.session_id
    assert client_1.agent_identity != client_2.agent_identity
    assert client_1.agent_identity is not None
    assert "tenant-alpha" in client_1.agent_identity
    assert record_1.profile_digest == record_2.profile_digest


@pytest.mark.asyncio
async def test_parent_cannot_invoke_sandbox_attempt() -> None:
    from unittest.mock import AsyncMock
    from app.agents.learning_performance_engine.profiles import dispatch_learning_specialist_attempt

    fake_sandbox = AsyncMock()
    with pytest.raises(SandboxInvocationError, match="zero sandbox authority"):
        await dispatch_learning_specialist_attempt(
            sandbox_client=fake_sandbox,
            specialist_id="W_LEARN",
            tenant_id="tenant-alpha",
            task_id="task-1",
            step_id="step-1",
            operation="synthesize",
            payload={},
        )
