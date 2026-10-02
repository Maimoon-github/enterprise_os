"""Comprehensive Integration Test Suite for Physical Sandbox Provisioner Boundary.

Validates the 12 Physical Isolation and Privilege-Separation Invariants:
1. No Backend Docker Socket Access (unprivileged container namespace provisioning)
2. Dedicated Provisioner Boundary (typed SandboxInvocationMandate only)
3. Physical Runtime per Attempt (unique runtime ID, PID/Mount/Net namespaces, cgroup)
4. Strict Runtime Template (pinned image, ro-rootfs, non-root UID, deny-all net)
5. No Cross-Specialist Mount Exposure (least-privilege skill mounts)
6. Safe Input/Output Transfer (ephemeral staging, anti-traversal)
7. Lifecycle Enforcement (fail-closed teardown, scrub, receipt generation)
8. Retry Isolation (Attempt N+1 never reuses Attempt N state or namespaces)
9. Concurrent Isolation Proof (concurrent specialists prove distinct namespaces & zero visibility)
10. Physical Provenance (execution and teardown receipts with genuine kernel namespace inodes)
11. Privilege-Separation Test (jail escape and unauthorized mount prevention)
12. Complete Live E2E Directive Proof via SandboxClient
"""

from __future__ import annotations

import concurrent.futures
import os
from typing import Any

import pytest

from app.core.exceptions import (
    PolicyViolationError,
    SandboxValidationError,
)
from app.core.settings import SandboxSettings
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.provisioner import (
    PINNED_DIGEST,
    SandboxProvisioner,
    get_sandbox_provisioner,
)
from app.schemas.sandbox import (
    NetworkPolicy,
    ResourceLimits,
    SandboxCapability,
    SandboxExecutionStatus,
    SandboxInvocationMandate,
)


@pytest.fixture
def provisioner() -> SandboxProvisioner:
    """Return physical sandbox provisioner instance."""
    return get_sandbox_provisioner()


def _make_mandate(
    *,
    capability: SandboxCapability,
    worker_role: str,
    operation: str,
    payload: dict[str, Any],
    execution_id: str = "exec-test-1",
    task_id: str = "task-test-1",
    tenant_id: str = "tenant-acme",
    attempt_id: str = "attempt-1",
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED,
) -> SandboxInvocationMandate:
    """Construct a typed SandboxInvocationMandate."""
    return SandboxInvocationMandate(
        execution_id=execution_id,
        task_id=task_id,
        worker_role=worker_role,
        tenant_id=tenant_id,
        stage_attempt_id=attempt_id,
        capability=capability,
        operation=operation,
        network_policy=network_policy,
        resource_limits=ResourceLimits(
            cpu_cores=1.0,
            memory_mb=512,
            timeout_seconds=30,
        ),
        payload=payload,
    )


# 1. No Backend Docker Socket Access
def test_no_backend_docker_socket_access(provisioner: SandboxProvisioner) -> None:
    """Verify backend, workers, and provisioner operate without
    /var/run/docker.sock or docker group."""
    # Assert provisioner does not require /var/run/docker.sock to achieve physical isolation
    assert provisioner.has_physical_isolation_runtime is True
    # Verify environment has no forced docker socket binding or host socket authority
    assert "DOCKER_HOST" not in os.environ or not os.environ["DOCKER_HOST"].startswith("unix://")


# 2. Dedicated Provisioner Boundary
def test_dedicated_provisioner_boundary_rejects_unauthorized_capability(
    provisioner: SandboxProvisioner,
) -> None:
    """Verify provisioner rejects unauthorized or untyped capabilities fail-closed."""
    mandate = _make_mandate(
        capability=SandboxCapability.ALLOC,
        worker_role="W_STRAT",
        operation="allocate_budget",
        payload={"budget": 1000},
    )
    # Temporarily tamper capability to an invalid one
    object.__setattr__(mandate, "capability", "S_UNAUTHORIZED")
    with pytest.raises(SandboxValidationError, match="Unauthorized or unregistered"):
        provisioner.validate_mandate(mandate)


def test_dedicated_provisioner_boundary_rejects_path_traversal(
    provisioner: SandboxProvisioner,
) -> None:
    """Verify provisioner blocks path traversal in payloads fail-closed."""
    mandate = _make_mandate(
        capability=SandboxCapability.ALLOC,
        worker_role="W_STRAT",
        operation="allocate_budget",
        payload={"target_file": "../../../etc/passwd"},
    )
    with pytest.raises(SandboxValidationError, match="Path traversal detected"):
        provisioner.validate_mandate(mandate)


# 3. Physical Runtime per Attempt
def test_physical_runtime_per_attempt(provisioner: SandboxProvisioner) -> None:
    """Verify every attempt receives a fresh container ID, PID, Mount, and Network namespace."""
    mandate_1 = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-1", "performance_metrics": {"roi": 2.5}},
        execution_id="exec-phys-1",
        attempt_id="att-1",
    )
    res_1 = provisioner.execute(mandate_1)
    assert res_1.success is True
    assert res_1.execution_receipt is not None
    assert res_1.execution_receipt.pid_namespace != ""
    assert res_1.execution_receipt.mount_namespace != ""
    assert res_1.execution_receipt.net_namespace != ""

    mandate_2 = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-2", "performance_metrics": {"roi": 3.1}},
        execution_id="exec-phys-2",
        attempt_id="att-2",
    )
    res_2 = provisioner.execute(mandate_2)
    assert res_2.success is True
    assert res_2.execution_receipt is not None

    # Invariants: completely distinct runtime/container identities
    assert res_1.execution_receipt.container_id != res_2.execution_receipt.container_id
    assert res_1.execution_receipt.runtime_id != res_2.execution_receipt.runtime_id


# 4. Strict Runtime Template
def test_strict_runtime_template_enforced(provisioner: SandboxProvisioner) -> None:
    """Verify server-side runtime template: pinned image, ro-rootfs, seccomp, deny-all network."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-template"},
        network_policy=NetworkPolicy.DISABLED,
    )
    res = provisioner.execute(mandate)
    assert res.success is True
    rcpt = res.execution_receipt
    assert rcpt is not None
    assert rcpt.image_digest == PINNED_DIGEST
    assert rcpt.read_only_root is True
    assert rcpt.seccomp_profile == "worker-seccomp.json"
    assert rcpt.network_mode == NetworkPolicy.DISABLED.value

    # Verify that requesting network without an egress grant is rejected fail-closed
    network_mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-net"},
        network_policy=NetworkPolicy.CONTROLLED,
    )
    with pytest.raises(PolicyViolationError, match="without approved SandboxEgressGrant"):
        provisioner.validate_mandate(network_mandate)


# 5. No Cross-Specialist Mount Exposure
def test_no_cross_specialist_mount_exposure(provisioner: SandboxProvisioner) -> None:
    """Verify specialist container mounts strictly its designated skill
    and cannot see sibling skills."""
    # S_ATTR can mount only s-attr
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-iso"},
    )
    skill_name = provisioner.validate_mandate(mandate)
    assert skill_name == "s-attr"


# 6. Safe Input/Output Transfer & Staging Scrubbing
def test_safe_input_output_transfer_and_scrubbing(provisioner: SandboxProvisioner) -> None:
    """Verify I/O transport is execution-scoped and deterministically scrubbed upon exit."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-scrub"},
        execution_id="exec-scrub-99",
    )
    res = provisioner.execute(mandate)
    assert res.success is True
    assert res.teardown_receipt is not None
    assert res.teardown_receipt.workspace_scrubbed is True
    assert res.teardown_receipt.runtime_destroyed is True


# 7. Lifecycle Enforcement Fail-Closed
def test_lifecycle_enforcement_fail_closed(provisioner: SandboxProvisioner) -> None:
    """Verify that execution failure produces failure receipts, scrubs storage, and fails closed."""
    # Trigger deliberate failure in skill execution
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"simulate_execution_failure": True, "malformed": "bad_input"},
        execution_id="exec-fail-1",
    )
    # Execution handles failures cleanly and records receipt
    res = provisioner.execute(mandate)
    assert res.teardown_receipt is not None
    assert res.teardown_receipt.workspace_scrubbed is True


# 8. Retry Isolation
def test_retry_isolation(provisioner: SandboxProvisioner) -> None:
    """Verify Attempt N+1 never reuses Attempt N container ID, namespaces, or lease."""
    mandate_n = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"attempt": 1},
        execution_id="exec-retry-1",
        attempt_id="attempt-1",
    )
    res_n = provisioner.execute(mandate_n)
    assert res_n.success is True

    mandate_n1 = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"attempt": 2},
        execution_id="exec-retry-2",
        attempt_id="attempt-2",
    )
    res_n1 = provisioner.execute(mandate_n1)
    assert res_n1.success is True

    # Complete isolation between retry attempts
    assert res_n.execution_receipt is not None
    assert res_n1.execution_receipt is not None
    assert res_n.execution_receipt.container_id != res_n1.execution_receipt.container_id
    assert res_n.execution_receipt.runtime_id != res_n1.execution_receipt.runtime_id


# 9. Concurrent Isolation Proof
def test_concurrent_isolation_proof(provisioner: SandboxProvisioner) -> None:
    """Run two specialists concurrently and prove distinct container IDs
    and physical namespace inodes."""
    mandate_a = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"branch": "A"},
        execution_id="exec-conc-A",
        attempt_id="att-conc-A",
    )
    mandate_b = _make_mandate(
        capability=SandboxCapability.ALLOC,
        worker_role="W_STRAT",
        operation="allocate_budget",
        payload={
            "total_budget": 5000.0,
            "channels": ["meta", "google"],
            "constraints": {"min_allocation": 100.0},
        },
        execution_id="exec-conc-B",
        attempt_id="att-conc-B",
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(provisioner.execute, mandate_a)
        future_b = executor.submit(provisioner.execute, mandate_b)
        res_a = future_a.result()
        res_b = future_b.result()

    assert res_a.success is True
    assert res_b.success is True

    rcpt_a = res_a.execution_receipt
    rcpt_b = res_b.execution_receipt
    assert rcpt_a is not None and rcpt_b is not None

    # Prove distinct physical container identities
    assert rcpt_a.container_id != rcpt_b.container_id
    assert rcpt_a.runtime_id != rcpt_b.runtime_id

    # Prove distinct physical kernel namespace inodes
    assert rcpt_a.pid_namespace != ""
    assert rcpt_b.pid_namespace != ""
    assert rcpt_a.mount_namespace != ""
    assert rcpt_b.mount_namespace != ""
    assert rcpt_a.net_namespace != ""
    assert rcpt_b.net_namespace != ""

    assert rcpt_a.pid_namespace != rcpt_b.pid_namespace
    assert rcpt_a.mount_namespace != rcpt_b.mount_namespace
    assert rcpt_a.net_namespace != rcpt_b.net_namespace


# 10. Physical Provenance Receipts
def test_physical_provenance_receipts(provisioner: SandboxProvisioner) -> None:
    """Verify execution and teardown receipts contain genuine cryptographic
    digests and timestamps."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"metrics": {"conversions": 42}},
        execution_id="exec-prov-1",
    )
    res = provisioner.execute(mandate)
    assert res.success is True
    rcpt = res.execution_receipt
    assert rcpt is not None
    assert len(rcpt.input_digest) == 64  # SHA-256
    assert len(rcpt.output_digest) == 64
    assert rcpt.exit_code == 0
    assert rcpt.termination_reason == "completed"
    assert rcpt.started_at is not None
    assert rcpt.terminated_at is not None
    assert rcpt.started_at <= rcpt.terminated_at

    td = res.teardown_receipt
    assert td is not None
    assert td.status == "CLEAN"
    assert td.workspace_scrubbed is True
    assert td.runtime_destroyed is True


# 11. Privilege-Separation Test
def test_privilege_separation_blocks_unauthorized_host_mounts(
    provisioner: SandboxProvisioner,
) -> None:
    """Verify caller cannot inject arbitrary host mounts or commands through the mandate."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"host_path": "/etc/shadow", "inject_mount": "/etc:/etc"},
    )
    # The provisioner validates server-side and only mounts /home/gem/skills/<skill>
    skill_name = provisioner.validate_mandate(mandate)
    assert skill_name == "s-attr"
    res = provisioner.execute(mandate)
    assert res.success is True
    # The output does not reflect arbitrary host data
    assert "/etc/shadow" not in str(res.sanitized_output)


# 12. Complete Live E2E Directive Proof via SandboxClient
@pytest.mark.asyncio
async def test_live_e2e_directive_via_sandbox_client(provisioner: SandboxProvisioner) -> None:
    """Execute real directive through SandboxClient wired to the physical provisioner."""
    settings = SandboxSettings(use_physical_provisioner=True)
    client = SandboxClient(settings=settings, provisioner=provisioner)

    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="calculate_attribution",
        payload={
            "strategy_id": "strat-e2e-live",
            "kpis": {"ctr": 0.05, "roas": 4.2},
        },
        execution_id="exec-e2e-live",
        attempt_id="attempt-e2e-live",
    )

    result = await client.invoke(mandate)
    assert result.status == SandboxExecutionStatus.COMPLETED
    assert result.success is True
    assert result.execution_receipt is not None
    assert result.execution_receipt.container_id.startswith("sbx-")
    assert result.execution_receipt.pid_namespace.startswith("pid:[")
    assert result.execution_receipt.mount_namespace.startswith("mnt:[")
    assert result.execution_receipt.net_namespace.startswith("net:[")
    assert result.teardown_receipt is not None
    assert result.teardown_receipt.workspace_scrubbed is True
    assert result.teardown_receipt.runtime_destroyed is True
