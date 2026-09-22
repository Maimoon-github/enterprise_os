"""Security and sandbox isolation tests for Competitor Intel Engine (COMP-03)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import SandboxInvocationError
from app.integrations.sandbox.capabilities import (
    validate_capability_access,
    validate_tool_access,
)
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxEgressGrant


def test_direct_w_comp_sandbox_execution_denied():
    """Verify W_COMP coordinator has zero sandbox execution authority."""
    # Attempting to invoke sandbox directly with coordinator worker_id
    with pytest.raises(
        SandboxInvocationError, match="W_COMP coordinator has zero sandbox authority"
    ):
        validate_capability_access(
            capability=SandboxCapability.SCRAPE,
            worker_role=WorkerRole.COMPETITOR_INTEL,
            worker_id="W_COMP",
            specialist_id=None,
        )

    # Explicit specialist_id="W_COMP" also denied
    with pytest.raises(
        SandboxInvocationError, match="W_COMP coordinator has zero sandbox authority"
    ):
        validate_capability_access(
            capability=SandboxCapability.SCRAPE,
            worker_role=WorkerRole.COMPETITOR_INTEL,
            worker_id="W_COMP",
            specialist_id="W_COMP",
        )


def test_unauthorized_competitor_specialist_rejected():
    """Verify unknown specialist_id is rejected fail-closed."""
    with pytest.raises(
        SandboxInvocationError, match="Unauthorized or unknown Competitor specialist"
    ):
        validate_capability_access(
            capability=SandboxCapability.SCRAPE,
            worker_role=WorkerRole.COMPETITOR_INTEL,
            worker_id="W_COMP",
            specialist_id="w_comp.arbitrary_hacker",
        )


def test_specialist_operation_restriction():
    """Verify specialist cannot execute unapproved operations."""
    # Pricing specialist cannot execute transparency_query
    with pytest.raises(
        SandboxInvocationError, match="Operation 'transparency_query' is not permitted"
    ):
        validate_capability_access(
            capability=SandboxCapability.SCRAPE,
            worker_role=WorkerRole.COMPETITOR_INTEL,
            specialist_id="COMP-PRICE",
            operation="transparency_query",
        )


def test_specialist_tool_restriction():
    """Verify micro-tools outside the specialist allowlist are blocked."""
    # Synthesis cannot use browser automation
    with pytest.raises(SandboxInvocationError, match="not permitted for Competitor specialist"):
        validate_tool_access(
            requested_tool="browser_automation",
            capability=SandboxCapability.SCRAPE,
            specialist_id="COMP-SYNTH",
        )

    # Valid tool access succeeds
    validate_tool_access(
        requested_tool="evidence_synthesizer",
        capability=SandboxCapability.SCRAPE,
        specialist_id="COMP-SYNTH",
    )


def test_synthesis_network_egress_strictly_denied():
    """Verify COMP-SYNTH has zero research-network egress under DENY_ALL."""
    egress_grant = SandboxEgressGrant(
        tenant_id="tenant-1",
        task_id="task-1",
        specialist_id="COMP-SYNTH",
        allowed_domains=["google.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    # Requesting allowlist network for SYNTH must fail
    with pytest.raises(SandboxInvocationError, match="restricted to DENY_ALL"):
        validate_capability_access(
            capability=SandboxCapability.SCRAPE,
            worker_role=WorkerRole.COMPETITOR_INTEL,
            specialist_id="COMP-SYNTH",
            operation="evidence_synthesize",
            requested_network=NetworkPolicy.ALLOWLIST,
            egress_grant=egress_grant,
        )

    # Attaching egress grant to DISABLED network must fail
    with pytest.raises(SandboxInvocationError, match="under DENY_ALL network policy"):
        validate_capability_access(
            capability=SandboxCapability.SCRAPE,
            worker_role=WorkerRole.COMPETITOR_INTEL,
            specialist_id="COMP-SYNTH",
            operation="evidence_synthesize",
            requested_network=NetworkPolicy.DISABLED,
            egress_grant=egress_grant,
        )


def test_egress_grant_specialist_mismatch_and_expiry():
    """Verify egress grant cannot be hijacked across specialists or after expiry."""
    # Specialist mismatch
    mismatched_grant = SandboxEgressGrant(
        tenant_id="tenant-1",
        task_id="task-1",
        specialist_id="COMP-DISCOVERY",
        allowed_domains=["example.com"],
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with pytest.raises(SandboxInvocationError, match="Egress grant specialist mismatch"):
        validate_capability_access(
            capability=SandboxCapability.SCRAPE,
            worker_role=WorkerRole.COMPETITOR_INTEL,
            specialist_id="COMP-PRICE",
            operation="public_page_capture",
            requested_network=NetworkPolicy.ALLOWLIST,
            egress_grant=mismatched_grant,
        )

    # Expired grant
    expired_grant = SandboxEgressGrant(
        tenant_id="tenant-1",
        task_id="task-1",
        specialist_id="COMP-PRICE",
        allowed_domains=["example.com"],
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    with pytest.raises(SandboxInvocationError, match="has expired"):
        validate_capability_access(
            capability=SandboxCapability.SCRAPE,
            worker_role=WorkerRole.COMPETITOR_INTEL,
            specialist_id="COMP-PRICE",
            operation="public_page_capture",
            requested_network=NetworkPolicy.ALLOWLIST,
            egress_grant=expired_grant,
        )
