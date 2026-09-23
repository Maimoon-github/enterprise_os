"""Security and execution boundary tests for Learning specialists and zero-sandbox coordinator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest

from app.core.exceptions import SandboxInvocationError
from app.integrations.sandbox.capabilities import (
    AUTHORIZED_LEARNING_SPECIALISTS,
    LEARNING_SPECIALIST_POLICIES,
    validate_capability_access,
)
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxEgressGrant,
)


def test_parent_coordinator_denied_sandbox_access() -> None:
    # Explicit W_LEARN worker_id must fail closed
    with pytest.raises(SandboxInvocationError, match="W_LEARN coordinator has zero sandbox authority"):
        validate_capability_access(
            capability=SandboxCapability.ATTR,
            worker_id="W_LEARN",
            operation="calculate_attribution",
        )

    # Explicit W_LEARN specialist_id must fail closed
    with pytest.raises(SandboxInvocationError, match="W_LEARN coordinator has zero sandbox authority"):
        validate_capability_access(
            capability=SandboxCapability.ATTR,
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            specialist_id="W_LEARN",
            operation="calculate_attribution",
        )


def test_six_specialists_authorized_for_narrow_operations() -> None:
    test_cases = [
        ("LEARN-TELEMETRY", "validate_telemetry"),
        ("LEARN-TELEMETRY", "normalize_telemetry"),
        ("LEARN-ATTRIBUTION", "estimate_attribution"),
        ("LEARN-ATTRIBUTION", "calculate_roas"),
        ("LEARN-INCREMENTALITY", "validate_experiment"),
        ("LEARN-INCREMENTALITY", "propose_calibration"),
        ("LEARN-FATIGUE", "analyze_wearout"),
        ("LEARN-FATIGUE", "analyze_saturation"),
        ("LEARN-DECAY", "estimate_adstock"),
        ("LEARN-DECAY", "estimate_half_life"),
        ("LEARN-QA", "validate_learning_bundle"),
        ("LEARN-QA", "verify_provenance"),
    ]

    for spec_id, op in test_cases:
        profile = validate_capability_access(
            capability=SandboxCapability.ATTR,
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            specialist_id=spec_id,
            operation=op,
            requested_network=NetworkPolicy.DISABLED,
        )
        assert profile.capability == SandboxCapability.ATTR
        assert profile.allowed_worker == WorkerRole.LEARNING_PERFORMANCE
        assert profile.network_policy == NetworkPolicy.DISABLED
        assert op in profile.allowed_operations


def test_operation_boundary_violation_fails_closed() -> None:
    # Telemetry specialist trying to run attribution operation
    with pytest.raises(SandboxInvocationError, match="not permitted for Learning specialist 'LEARN-TELEMETRY'"):
        validate_capability_access(
            capability=SandboxCapability.ATTR,
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            specialist_id="LEARN-TELEMETRY",
            operation="estimate_attribution",
        )

    # Decay specialist trying to validate experiment
    with pytest.raises(SandboxInvocationError, match="not permitted for Learning specialist 'LEARN-DECAY'"):
        validate_capability_access(
            capability=SandboxCapability.ATTR,
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            specialist_id="LEARN-DECAY",
            operation="validate_experiment",
        )


def test_network_egress_strictly_denied_for_all_learning_specialists() -> None:
    for spec_id in AUTHORIZED_LEARNING_SPECIALISTS:
        # Requesting allowlist network must fail
        with pytest.raises(SandboxInvocationError, match="strictly restricted to DENY_ALL"):
            validate_capability_access(
                capability=SandboxCapability.ATTR,
                worker_role=WorkerRole.LEARNING_PERFORMANCE,
                specialist_id=spec_id,
                operation=LEARNING_SPECIALIST_POLICIES[spec_id]["allowed_operations"][0],
                requested_network=NetworkPolicy.ALLOWLIST,
            )

        # Attaching egress grant must fail
        grant = SandboxEgressGrant(
            grant_id="grant-test",
            tenant_id="tenant-1",
            task_id="task-1",
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            capability=SandboxCapability.ATTR,
            specialist_id=spec_id,
            allowed_domains=["api.example.com"],
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
        with pytest.raises(SandboxInvocationError, match="strictly restricted to DENY_ALL"):
            validate_capability_access(
                capability=SandboxCapability.ATTR,
                worker_role=WorkerRole.LEARNING_PERFORMANCE,
                specialist_id=spec_id,
                operation=LEARNING_SPECIALIST_POLICIES[spec_id]["allowed_operations"][0],
                egress_grant=grant,
            )


def test_unknown_learning_specialist_fails_closed() -> None:
    with pytest.raises(SandboxInvocationError, match="Unauthorized or unknown Learning specialist"):
        validate_capability_access(
            capability=SandboxCapability.ATTR,
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            specialist_id="LEARN-ROGUE-SPECIALIST",
            operation="validate_telemetry",
        )
