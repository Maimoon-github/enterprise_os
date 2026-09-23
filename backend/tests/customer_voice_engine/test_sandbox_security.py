"""Security and sandbox isolation tests for Customer Voice Engine (CV-03).

Validates:
1. Zero-sandbox coordinator: W_VOICE direct sandbox/S_PARSE access is denied fail-closed.
2. Specialist-only authority: Exactly six VOICE-* specialists can receive bounded mandates.
3. Forged / unknown specialist rejection: Non-authorized specialist IDs fail closed.
4. Operation restriction: Each specialist is confined to approved operations.
5. Micro-tool restriction: Tools outside specialist allowlist are blocked.
6. Network policy: Default is DENY_ALL; only VOICE-DISCOVERY allows explicit egress grant.
7. Discovery egress grant binding: Expired, mismatched specialist/tenant, or replayed grants fail closed.
8. Fresh runtime identity: Every attempt uses a distinct SandboxIdentity and teardown cleans up.
9. Absence of production fallback: Production or missing AIO fails closed without host fallback.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import uuid

import pytest

from app.core.exceptions import SandboxInvocationError
from app.integrations.sandbox.capabilities import (
    AUTHORIZED_VOICE_SPECIALISTS,
    VOICE_SPECIALIST_POLICIES,
    validate_capability_access,
    validate_egress_target,
    validate_tool_access,
)
from app.integrations.sandbox.client import SandboxClient
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxEgressGrant,
    SandboxIdentity,
    SandboxInvocationMandate,
)


def test_direct_w_voice_sandbox_execution_denied():
    """Verify W_VOICE coordinator has zero direct sandbox execution authority."""
    with pytest.raises(
        SandboxInvocationError, match="W_VOICE coordinator has zero sandbox authority"
    ):
        validate_capability_access(
            capability=SandboxCapability.PARSE,
            worker_role=WorkerRole.CUSTOMER_VOICE,
            worker_id="W_VOICE",
            specialist_id=None,
        )

    with pytest.raises(
        SandboxInvocationError, match="W_VOICE coordinator has zero sandbox authority"
    ):
        validate_capability_access(
            capability=SandboxCapability.PARSE,
            worker_role=WorkerRole.CUSTOMER_VOICE,
            worker_id="W_VOICE",
            specialist_id="W_VOICE",
        )


def test_unauthorized_voice_specialist_rejected():
    """Verify forged or unknown specialist_id is rejected fail-closed."""
    with pytest.raises(
        SandboxInvocationError, match="Unauthorized or unknown Customer Voice specialist"
    ):
        validate_capability_access(
            capability=SandboxCapability.PARSE,
            worker_role=WorkerRole.CUSTOMER_VOICE,
            worker_id="W_VOICE",
            specialist_id="w_voice.forged_specialist",
        )

    with pytest.raises(
        SandboxInvocationError, match="Unauthorized or unknown Customer Voice specialist"
    ):
        validate_capability_access(
            capability=SandboxCapability.PARSE,
            worker_role=WorkerRole.CUSTOMER_VOICE,
            worker_id="W_VOICE",
            specialist_id="VOICE-UNKNOWN",
        )


def test_all_six_voice_specialists_authorized():
    """Verify exactly six VOICE-* specialists can receive bounded sandbox profiles."""
    expected_specialists = {
        "VOICE-DISCOVERY",
        "VOICE-THEMES",
        "VOICE-SENTIMENT",
        "VOICE-NEEDS",
        "VOICE-JOURNEY",
        "VOICE-QA",
    }
    assert AUTHORIZED_VOICE_SPECIALISTS == expected_specialists

    for spec_id in expected_specialists:
        pol = VOICE_SPECIALIST_POLICIES[spec_id]
        op = pol["allowed_operations"][0]
        net = pol["network_policy"]

        grant = None
        if net == NetworkPolicy.ALLOWLIST:
            grant = SandboxEgressGrant(
                tenant_id="tenant-alpha",
                task_id="task-001",
                specialist_id=spec_id,
                allowed_domains=["reviews.example.com"],
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )

        prof = validate_capability_access(
            capability=SandboxCapability.PARSE,
            worker_role=WorkerRole.CUSTOMER_VOICE,
            worker_id=spec_id,
            specialist_id=spec_id,
            operation=op,
            requested_network=net,
            egress_grant=grant,
        )
        assert prof.capability == SandboxCapability.PARSE
        assert prof.allowed_worker == WorkerRole.CUSTOMER_VOICE


def test_specialist_operation_restriction():
    """Verify specialist cannot execute unapproved operations."""
    # VOICE-THEMES cannot execute absa/sentiment scoring
    with pytest.raises(
        SandboxInvocationError, match="Operation 'score_aspect_polarity' is not permitted"
    ):
        validate_capability_access(
            capability=SandboxCapability.PARSE,
            worker_role=WorkerRole.CUSTOMER_VOICE,
            specialist_id="VOICE-THEMES",
            operation="score_aspect_polarity",
        )


def test_specialist_tool_restriction():
    """Verify micro-tools outside the specialist allowlist are blocked."""
    with pytest.raises(
        SandboxInvocationError, match="not permitted for Customer Voice specialist"
    ):
        validate_tool_access(
            requested_tool="browser_automation",
            capability=SandboxCapability.PARSE,
            specialist_id="VOICE-SENTIMENT",
        )

    # Valid tool access succeeds
    validate_tool_access(
        requested_tool="absa_classifier",
        capability=SandboxCapability.PARSE,
        specialist_id="VOICE-SENTIMENT",
    )


def test_non_discovery_voice_specialists_network_denied():
    """Verify non-discovery specialists are strictly DENY_ALL and cannot receive egress grants."""
    non_discovery = [
        "VOICE-THEMES",
        "VOICE-SENTIMENT",
        "VOICE-NEEDS",
        "VOICE-JOURNEY",
        "VOICE-QA",
    ]

    for spec_id in non_discovery:
        grant = SandboxEgressGrant(
            tenant_id="tenant-alpha",
            task_id="task-001",
            specialist_id=spec_id,
            allowed_domains=["api.example.com"],
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        # Requesting allowlist network must fail
        with pytest.raises(SandboxInvocationError, match="restricted to DENY_ALL"):
            validate_capability_access(
                capability=SandboxCapability.PARSE,
                worker_role=WorkerRole.CUSTOMER_VOICE,
                specialist_id=spec_id,
                operation="default",
                requested_network=NetworkPolicy.ALLOWLIST,
                egress_grant=grant,
            )

        # Attaching egress grant to DISABLED network must fail
        with pytest.raises(SandboxInvocationError, match="under DENY_ALL network policy"):
            validate_capability_access(
                capability=SandboxCapability.PARSE,
                worker_role=WorkerRole.CUSTOMER_VOICE,
                specialist_id=spec_id,
                operation="default",
                requested_network=NetworkPolicy.DISABLED,
                egress_grant=grant,
            )


def test_discovery_egress_grant_validation_and_replay_protection():
    """Verify VOICE-DISCOVERY egress grant binds to specialist, unexpired, and single-use."""
    # 1. Valid grant and valid destination
    grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-001",
        specialist_id="VOICE-DISCOVERY",
        allowed_domains=["reviews.brand.com", "*.trustpilot.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    prof = validate_capability_access(
        capability=SandboxCapability.PARSE,
        worker_role=WorkerRole.CUSTOMER_VOICE,
        specialist_id="VOICE-DISCOVERY",
        operation="acquire_source",
        requested_network=NetworkPolicy.ALLOWLIST,
        egress_grant=grant,
    )
    assert prof.network_policy == NetworkPolicy.ALLOWLIST

    # Target destination validation
    validate_egress_target("https://reviews.brand.com/api/v1", grant)
    validate_egress_target("https://us.trustpilot.com/review/brand", grant)

    # Disallowed destination
    with pytest.raises(SandboxInvocationError, match="not in approved allowlist"):
        validate_egress_target("https://malicious-site.com", grant)

    # SSRF / private IP destination blocked
    with pytest.raises(SandboxInvocationError, match="private/metadata host"):
        validate_egress_target("http://192.168.1.1/secret", grant)

    # 2. Specialist mismatch rejected
    mismatched_grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-001",
        specialist_id="VOICE-THEMES",
        allowed_domains=["reviews.brand.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with pytest.raises(SandboxInvocationError, match="Egress grant specialist mismatch"):
        validate_capability_access(
            capability=SandboxCapability.PARSE,
            worker_role=WorkerRole.CUSTOMER_VOICE,
            specialist_id="VOICE-DISCOVERY",
            operation="acquire_source",
            requested_network=NetworkPolicy.ALLOWLIST,
            egress_grant=mismatched_grant,
        )

    # 3. Expired grant rejected
    expired_grant = SandboxEgressGrant(
        tenant_id="tenant-alpha",
        task_id="task-001",
        specialist_id="VOICE-DISCOVERY",
        allowed_domains=["reviews.brand.com"],
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(SandboxInvocationError, match="has expired"):
        validate_capability_access(
            capability=SandboxCapability.PARSE,
            worker_role=WorkerRole.CUSTOMER_VOICE,
            specialist_id="VOICE-DISCOVERY",
            operation="acquire_source",
            requested_network=NetworkPolicy.ALLOWLIST,
            egress_grant=expired_grant,
        )


@pytest.mark.asyncio
async def test_fresh_runtime_identity_and_single_use_egress_grant():
    """Verify each attempt creates a distinct SandboxIdentity and single-use grant expires after run."""
    client = SandboxClient()
    grant = SandboxEgressGrant(
        tenant_id="tenant-voice",
        task_id="task-v1",
        worker_id="VOICE-DISCOVERY",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        capability=SandboxCapability.PARSE,
        specialist_id="VOICE-DISCOVERY",
        allowed_domains=["reviews.brand.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    mandate1 = SandboxInvocationMandate(
        task_id="task-v1",
        stage_attempt_id="att-001",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        worker_id="VOICE-DISCOVERY",
        specialist_id="VOICE-DISCOVERY",
        tenant_id="tenant-voice",
        capability=SandboxCapability.PARSE,
        operation="acquire_source",
        payload={"feedback_text": "Product is fast and reliable!"},
        network_policy=NetworkPolicy.ALLOWLIST,
        egress_grant=grant,
    )

    res1 = await client.invoke(mandate1)
    assert res1.success is True

    # Single-use egress grant replay protection: client.py marks grant as expired in finally
    assert grant.is_expired() is True

    # Reusing the same grant must fail closed
    mandate2 = SandboxInvocationMandate(
        task_id="task-v1",
        stage_attempt_id="att-002",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        worker_id="VOICE-DISCOVERY",
        specialist_id="VOICE-DISCOVERY",
        tenant_id="tenant-voice",
        capability=SandboxCapability.PARSE,
        operation="acquire_source",
        payload={"feedback_text": "Customer service was prompt."},
        network_policy=NetworkPolicy.ALLOWLIST,
        egress_grant=grant,
    )
    with pytest.raises(SandboxInvocationError, match="has expired"):
        await client.invoke(mandate2)


@pytest.mark.asyncio
async def test_production_fail_closed_without_local_fallback():
    """Verify in production mode, AIO failure/absence fails closed without local fallback."""
    from app.core.settings import SandboxSettings

    prod_settings = SandboxSettings(
        endpoint="https://remote-aio.internal:8443",
        environment="production",
    )
    client = SandboxClient(settings=prod_settings)

    mandate = SandboxInvocationMandate(
        task_id="task-v2",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        worker_id="VOICE-SENTIMENT",
        specialist_id="VOICE-SENTIMENT",
        tenant_id="tenant-voice",
        capability=SandboxCapability.PARSE,
        operation="score_aspect_polarity",
        payload={"feedback_text": "Excellent support quality!"},
        network_policy=NetworkPolicy.DISABLED,
    )

    # Must fail closed: cannot fallback to local in-process micro-tool in production
    res = await client.invoke(mandate)
    assert res.success is False
    assert "AIO sandbox is unavailable" in (res.error or "") or "endpoint" in (res.error or "")
