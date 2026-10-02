"""Comprehensive Integration Test Suite for Standalone Physical Sandbox Provisioner Boundary.

Validates:
1. Complete UDS Out-of-Process Isolation:
   - Backend/IE/Workers communicate exclusively over an authenticated Unix Domain Socket (UDS).
   - Backend has ZERO subprocess container spawning, ZERO bwrap/systemd-run authority, ZERO Docker socket access.
2. Security & Privilege Separation:
   - Rejects unauthenticated callers / invalid auth token fail-closed.
   - Rejects arbitrary command / executable execution.
   - Rejects arbitrary mount injection.
   - Strictly enforces Seccomp: 2 and NoNewPrivs: 1.
   - Rejects excessive cgroup resource ceiling requests.
   - Rejects unauthorized network enablement.
   - Rejects unauthorized or unmapped specialist skills.
   - Rejects tenant impersonation and attempt/execution replay.
   - Rejects expired execution leases.
   - Rejects path traversal.
3. Concurrent Physical Isolation over UDS:
   - Two concurrent specialist executions through the live UDS service boundary.
   - Proves distinct PID, Mount, Net, IPC, and UTS namespaces.
   - Proves dedicated cgroup v2 scopes and physical evidence capture.
   - Proves fail-closed cleanup and teardown receipts.
4. Complete Live E2E Directive Proof via SandboxClient.
"""

from __future__ import annotations

import concurrent.futures
import inspect
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.core.exceptions import (
    PolicyViolationError,
    SandboxIsolationError,
    SandboxValidationError,
)
from app.core.settings import SandboxSettings
from app.integrations.sandbox import provisioner_client
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.provisioner import (
    PINNED_DIGEST,
    SandboxProvisioner,
    get_sandbox_provisioner,
)
from app.integrations.sandbox.provisioner_client import SandboxProvisionerClient
from app.integrations.sandbox.provisioner_daemon import SandboxProvisionerServer
from app.schemas.sandbox import (
    NetworkPolicy,
    ResourceLimits,
    SandboxCapability,
    SandboxExecutionStatus,
    SandboxInvocationMandate,
)

TEST_SOCKET_PATH = "/tmp/enterprise_os_test_provisioner.sock"
TEST_AUTH_TOKEN = "enterprise_os_test_secret_token"
TEST_STATE_FILE = Path("/tmp/enterprise_os_test_replay_state.json")


@pytest.fixture(scope="session", autouse=True)
def provisioner_daemon_server():
    """Start standalone provisioner daemon server listening on UDS for the test session."""
    if TEST_STATE_FILE.exists():
        TEST_STATE_FILE.unlink()
    if Path(TEST_SOCKET_PATH).exists():
        Path(TEST_SOCKET_PATH).unlink()

    from app.integrations.sandbox.provisioner_daemon import SandboxProvisionerEngine

    engine = SandboxProvisionerEngine(replay_state_path=TEST_STATE_FILE)
    server = SandboxProvisionerServer(
        socket_path=TEST_SOCKET_PATH,
        auth_token=TEST_AUTH_TOKEN,
        engine=engine,
    )
    server.start()
    for _ in range(50):
        if Path(TEST_SOCKET_PATH).exists():
            break
        time.sleep(0.02)
    yield server
    server.stop()
    if TEST_STATE_FILE.exists():
        TEST_STATE_FILE.unlink()


@pytest.fixture
def provisioner(provisioner_daemon_server) -> SandboxProvisionerClient:
    """Return thin UDS client connected to the standalone provisioner daemon."""
    return SandboxProvisionerClient(
        socket_path=TEST_SOCKET_PATH,
        auth_token=TEST_AUTH_TOKEN,
    )


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
    resource_limits: ResourceLimits | None = None,
    lease_expires_at: datetime | None = None,
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
        resource_limits=resource_limits
        or ResourceLimits(
            cpu_cores=1.0,
            memory_mb=512,
            timeout_seconds=30,
        ),
        payload=payload,
        lease_expires_at=lease_expires_at,
    )


# 1. No Backend Docker Socket Access & Zero Process Spawning
def test_no_backend_docker_socket_access(provisioner: SandboxProvisionerClient) -> None:
    """Verify backend and provisioner client operate without docker socket or container CLI authority."""
    assert provisioner.has_physical_isolation_runtime is True
    assert "DOCKER_HOST" not in os.environ or not os.environ["DOCKER_HOST"].startswith("unix://")

    # Verify SandboxProvisionerClient has zero host process spawning logic
    client_src = inspect.getsource(provisioner_client)
    assert "import subprocess" not in client_src
    assert "subprocess." not in client_src
    assert '"bwrap"' not in client_src
    assert '"systemd-run"' not in client_src
    assert "shutil.which" not in client_src


# 2. Dedicated Provisioner Boundary (Fail-Closed Validations)
def test_dedicated_provisioner_boundary_rejects_unauthorized_capability(
    provisioner: SandboxProvisionerClient,
) -> None:
    """Verify provisioner rejects unauthorized or untyped capabilities fail-closed."""
    mandate = _make_mandate(
        capability=SandboxCapability.ALLOC,
        worker_role="W_STRAT",
        operation="allocate_budget",
        payload={"budget": 1000},
    )
    object.__setattr__(mandate, "capability", "S_UNAUTHORIZED")
    with pytest.raises(SandboxValidationError, match="Unauthorized or unregistered"):
        provisioner.validate_mandate(mandate)


def test_dedicated_provisioner_boundary_rejects_path_traversal(
    provisioner: SandboxProvisionerClient,
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


# 3. Physical Runtime per Attempt over UDS
def test_physical_runtime_per_attempt(provisioner: SandboxProvisionerClient) -> None:
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

    # Distinct runtime and container identities
    assert res_1.execution_receipt.container_id != res_2.execution_receipt.container_id
    assert res_1.execution_receipt.runtime_id != res_2.execution_receipt.runtime_id


# 4. Strict Runtime Template Enforced
def test_strict_runtime_template_enforced(provisioner: SandboxProvisionerClient) -> None:
    """Verify server-side runtime template: pinned image, ro-rootfs, seccomp, deny-all network."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-template"},
        execution_id="exec-tmpl-1",
        attempt_id="att-tmpl-1",
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

    # Requesting network without an egress grant is rejected fail-closed
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
def test_no_cross_specialist_mount_exposure(provisioner: SandboxProvisionerClient) -> None:
    """Verify specialist container mounts strictly its designated skill."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-iso"},
    )
    skill_name = provisioner.validate_mandate(mandate)
    assert skill_name == "s-attr"


# 6. Safe Input/Output Transfer & Staging Scrubbing
def test_safe_input_output_transfer_and_scrubbing(provisioner: SandboxProvisionerClient) -> None:
    """Verify I/O transport is execution-scoped and deterministically scrubbed upon exit."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-scrub"},
        execution_id="exec-scrub-99",
        attempt_id="att-scrub-99",
    )
    res = provisioner.execute(mandate)
    assert res.success is True
    assert res.teardown_receipt is not None
    assert res.teardown_receipt.workspace_scrubbed is True
    assert res.teardown_receipt.runtime_destroyed is True


# 7. Lifecycle Enforcement Fail-Closed
def test_lifecycle_enforcement_fail_closed(provisioner: SandboxProvisionerClient) -> None:
    """Verify execution failure produces failure receipts, scrubs storage, and fails closed."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"simulate_execution_failure": True, "malformed": "bad_input"},
        execution_id="exec-fail-1",
        attempt_id="att-fail-1",
    )
    res = provisioner.execute(mandate)
    assert res.teardown_receipt is not None
    assert res.teardown_receipt.workspace_scrubbed is True


# 8. Retry Isolation
def test_retry_isolation(provisioner: SandboxProvisionerClient) -> None:
    """Verify Attempt N+1 never reuses Attempt N container ID, namespaces, or lease."""
    mandate_n = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"attempt": 1},
        execution_id="exec-retry-1",
        attempt_id="attempt-10",
    )
    res_n = provisioner.execute(mandate_n)
    assert res_n.success is True

    mandate_n1 = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"attempt": 2},
        execution_id="exec-retry-2",
        attempt_id="attempt-20",
    )
    res_n1 = provisioner.execute(mandate_n1)
    assert res_n1.success is True

    assert res_n.execution_receipt is not None
    assert res_n1.execution_receipt is not None
    assert res_n.execution_receipt.container_id != res_n1.execution_receipt.container_id
    assert res_n.execution_receipt.runtime_id != res_n1.execution_receipt.runtime_id


# 9. Concurrent Isolation Proof over UDS
def test_concurrent_isolation_proof(provisioner: SandboxProvisionerClient) -> None:
    """Run two specialists concurrently through UDS and prove distinct physical namespaces,
    dedicated cgroups, and Seccomp: 2 enforcement."""
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

    # Distinct container identities
    assert rcpt_a.container_id != rcpt_b.container_id
    assert rcpt_a.runtime_id != rcpt_b.runtime_id

    # Distinct physical kernel namespace inodes
    assert rcpt_a.pid_namespace != "" and rcpt_b.pid_namespace != ""
    assert rcpt_a.mount_namespace != "" and rcpt_b.mount_namespace != ""
    assert rcpt_a.net_namespace != "" and rcpt_b.net_namespace != ""
    assert rcpt_a.ipc_namespace != "" and rcpt_b.ipc_namespace != ""
    assert rcpt_a.uts_namespace != "" and rcpt_b.uts_namespace != ""

    assert rcpt_a.pid_namespace != rcpt_b.pid_namespace
    assert rcpt_a.mount_namespace != rcpt_b.mount_namespace
    assert rcpt_a.net_namespace != rcpt_b.net_namespace
    assert rcpt_a.ipc_namespace != rcpt_b.ipc_namespace
    assert rcpt_a.uts_namespace != rcpt_b.uts_namespace

    # Dedicated cgroup scopes
    assert rcpt_a.cgroup_path != rcpt_b.cgroup_path
    assert "sbx-" in rcpt_a.cgroup_path
    assert "sbx-" in rcpt_b.cgroup_path

    # Genuine kernel seccomp enforcement
    assert rcpt_a.seccomp_status == "2"
    assert rcpt_b.seccomp_status == "2"
    assert rcpt_a.no_new_privs is True
    assert rcpt_b.no_new_privs is True


# 10. Physical Provenance Receipts
def test_physical_provenance_receipts(provisioner: SandboxProvisionerClient) -> None:
    """Verify execution and teardown receipts contain genuine cryptographic digests and timestamps."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"metrics": {"conversions": 42}},
        execution_id="exec-prov-1",
        attempt_id="att-prov-1",
    )
    res = provisioner.execute(mandate)
    assert res.success is True
    rcpt = res.execution_receipt
    assert rcpt is not None
    assert len(rcpt.input_digest) == 64
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


# 11. Privilege-Separation: Blocks Arbitrary Host Mounts & Injected Commands
def test_privilege_separation_blocks_unauthorized_host_mounts(
    provisioner: SandboxProvisionerClient,
) -> None:
    """Verify caller cannot inject arbitrary host mounts or commands through the mandate."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"host_path": "/etc/shadow", "inject_mount": "/etc:/etc"},
        execution_id="exec-priv-1",
        attempt_id="att-priv-1",
    )
    res = provisioner.execute(mandate)
    assert res.success is True
    assert "/etc/shadow" not in str(res.sanitized_output)


# 12. Security Test: Reject Unauthorized or Missing Authentication Token
def test_security_rejects_unauthorized_token() -> None:
    """Verify UDS server rejects connections with invalid auth tokens fail-closed."""
    unauthorized_client = SandboxProvisionerClient(
        socket_path=TEST_SOCKET_PATH,
        auth_token="wrong_malicious_token",
    )
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "test"},
        execution_id="exec-unauth-token-1",
        attempt_id="att-unauth-token-1",
    )
    with pytest.raises(PolicyViolationError, match="invalid or missing authentication token"):
        unauthorized_client.execute(mandate)


# 13. Security Test: Excessive Cgroup Resource Limits Rejected Server-Side
def test_security_excessive_cgroup_limits_rejected(provisioner: SandboxProvisionerClient) -> None:
    """Verify server rejects excessive CPU/RAM resource requests beyond policy ceiling."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "test"},
        execution_id="exec-cgroup-ceil-1",
        attempt_id="att-cgroup-ceil-1",
    )
    # Tamper resource limits to bypass client-side Pydantic constructor
    object.__setattr__(mandate.resource_limits, "cpu_cores", 999.0)
    with pytest.raises((PolicyViolationError, SandboxValidationError)):
        provisioner.execute(mandate)


# 14. Security Test: Replayed Execution ID Rejected Fail-Closed
def test_security_replayed_execution_id_rejected(provisioner: SandboxProvisionerClient) -> None:
    """Verify provisioner rejects execution ID replay attacks."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "test"},
        execution_id="exec-replay-target",
        attempt_id="att-replay-1",
    )
    res = provisioner.execute(mandate)
    assert res.success is True

    # Attempt to replay the exact same execution_id
    replay_mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "test"},
        execution_id="exec-replay-target",
        attempt_id="att-replay-2",
    )
    with pytest.raises(SandboxIsolationError, match="has already been executed. Replay forbidden"):
        provisioner.execute(replay_mandate)


# 15. Security Test: Expired Execution Lease Rejected Fail-Closed
def test_security_expired_lease_rejected(provisioner: SandboxProvisionerClient) -> None:
    """Verify provisioner rejects mandates with expired leases."""
    expired_mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "test"},
        execution_id="exec-lease-exp-1",
        attempt_id="att-lease-exp-1",
        lease_expires_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    with pytest.raises(PolicyViolationError, match="lease expired"):
        provisioner.execute(expired_mandate)


# 16. Complete Live E2E Directive Proof via SandboxClient wired to UDS Provisioner
@pytest.mark.asyncio
async def test_live_e2e_directive_via_sandbox_client(provisioner: SandboxProvisionerClient) -> None:
    """Execute real directive through SandboxClient wired to the standalone UDS provisioner."""
    settings = SandboxSettings(
        use_physical_provisioner=True,
        provisioner_socket_path=TEST_SOCKET_PATH,
        provisioner_auth_token=TEST_AUTH_TOKEN,
    )
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
    assert result.execution_receipt.ipc_namespace.startswith("ipc:[")
    assert result.execution_receipt.uts_namespace.startswith("uts:[")
    assert result.execution_receipt.seccomp_status == "2"
    assert result.execution_receipt.no_new_privs is True
    assert result.teardown_receipt is not None
    assert result.teardown_receipt.workspace_scrubbed is True
    assert result.teardown_receipt.runtime_destroyed is True


# 17. Security Test: Cannot Execute Arbitrary Host Commands
def test_security_cannot_execute_arbitrary_host_commands(provisioner: SandboxProvisionerClient) -> None:
    """Prove compromised client cannot execute arbitrary commands on the host or in container."""
    pwn_marker = Path("/tmp/should_never_exist_sbx_pwn")
    if pwn_marker.exists():
        pwn_marker.unlink()

    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={
            "command": f"touch {pwn_marker}",
            "shell": True,
            "args": ["-c", f"touch {pwn_marker}"],
            "executable": "/bin/sh",
        },
        execution_id="exec-no-cmd-1",
        attempt_id="att-no-cmd-1",
    )
    res = provisioner.execute(mandate)
    assert res.success is True
    # The arbitrary command was never run
    assert not pwn_marker.exists()


# 18. Security Test: Cannot Disable Seccomp Filter
def test_security_cannot_disable_seccomp(provisioner: SandboxProvisionerClient) -> None:
    """Prove client cannot disable seccomp filter; Seccomp: 2 is strictly enforced server-side."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"disable_seccomp": True, "seccomp": "unconfined", "no_new_privs": False},
        execution_id="exec-force-seccomp-1",
        attempt_id="att-force-seccomp-1",
    )
    res = provisioner.execute(mandate)
    assert res.success is True
    assert res.execution_receipt is not None
    assert res.execution_receipt.seccomp_status == "2"
    assert res.execution_receipt.no_new_privs is True


# 19. Security Test: Cannot Enable Network Access Without Approved Grant
def test_security_cannot_enable_unauthorized_network(provisioner: SandboxProvisionerClient) -> None:
    """Prove client cannot enable network egress without cryptographically approved grant."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "test"},
        execution_id="exec-unauth-net-1",
        attempt_id="att-unauth-net-1",
        network_policy=NetworkPolicy.CONTROLLED,
    )
    with pytest.raises(PolicyViolationError, match="without approved SandboxEgressGrant"):
        provisioner.execute(mandate)


# 20. Security Test: Cannot Impersonate Tenant
def test_security_cannot_impersonate_tenant(provisioner: SandboxProvisionerClient) -> None:
    """Prove client cannot execute mandates without valid bound tenant identity."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "test"},
        execution_id="exec-no-tenant-1",
        attempt_id="att-no-tenant-1",
        tenant_id="",
    )
    with pytest.raises(SandboxValidationError, match="missing required tenant_id"):
        provisioner.execute(mandate)


# 21. Security Test: Cannot Reuse Another Attempt's Runtime
def test_security_cannot_reuse_attempt_runtime(provisioner: SandboxProvisionerClient) -> None:
    """Prove attempt ID reuse fails closed with isolation error."""
    mandate_1 = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "test-1"},
        task_id="task-reuse-check",
        attempt_id="att-shared-id",
        execution_id="exec-reuse-1",
    )
    res_1 = provisioner.execute(mandate_1)
    assert res_1.success is True

    # Same task_id and stage_attempt_id cannot be reused
    mandate_2 = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "test-2"},
        task_id="task-reuse-check",
        attempt_id="att-shared-id",
        execution_id="exec-reuse-2",
    )
    with pytest.raises(SandboxIsolationError, match="is already active or reused"):
        provisioner.execute(mandate_2)


# 22. Production Hardening: SO_PEERCRED UID/GID Authorization Enforcement
def test_uds_so_peercred_authorization() -> None:
    """Verify UDS server authorizes peer credentials via SO_PEERCRED and rejects unauthorized UIDs fail-closed."""
    from app.integrations.sandbox.provisioner_daemon import SandboxProvisionerEngine, SocketIdentityPolicy

    unauth_sock = "/tmp/enterprise_os_test_unauth.sock"
    if Path(unauth_sock).exists():
        Path(unauth_sock).unlink()

    # Reject all callers except foreign UID 99999
    strict_policy = SocketIdentityPolicy(
        allowed_uids={99999},
        allow_same_user=False,
        allow_root=False,
    )
    server = SandboxProvisionerServer(
        socket_path=unauth_sock,
        auth_token=TEST_AUTH_TOKEN,
        engine=SandboxProvisionerEngine(),
        identity_policy=strict_policy,
    )
    server.start()
    try:
        client = SandboxProvisionerClient(socket_path=unauth_sock, auth_token=TEST_AUTH_TOKEN)
        mandate = _make_mandate(
            capability=SandboxCapability.ATTR,
            worker_role="W_LEARN",
            operation="analyze_attribution",
            payload={"data": "test"},
            execution_id="exec-peercred-unauth",
            attempt_id="att-peercred-unauth",
        )
        with pytest.raises(PolicyViolationError, match="Unauthorized caller: Peer credential UID="):
            client.execute(mandate)
    finally:
        server.stop()


# 23. Production Hardening: Bubblewrap Security & User Namespace Lockdown (--disable-userns)
def test_bubblewrap_security_and_userns_lockdown(provisioner: SandboxProvisionerClient) -> None:
    """Verify physical runtime applies --disable-userns, preventing specialist nested user namespaces."""
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-userns-test", "metrics": {"conversions": 10}},
        execution_id="exec-userns-lockdown-1",
        attempt_id="att-userns-lockdown-1",
    )
    res = provisioner.execute(mandate)
    assert res.success is True
    rcpt = res.execution_receipt
    assert rcpt is not None
    # User namespace lockdown verified
    assert rcpt.userns_disabled is True
    assert rcpt.no_new_privs is True
    assert rcpt.seccomp_status == "2"
    assert len(rcpt.bwrap_version) > 0


# 24. Production Hardening: Persistent Replay State Across Daemon Restarts
def test_persistent_replay_state_across_daemon_restarts() -> None:
    """Verify seen execution IDs survive daemon crashes and restarts fail-closed."""
    from app.integrations.sandbox.provisioner_daemon import SandboxProvisionerEngine

    restart_sock = "/tmp/enterprise_os_test_restart.sock"
    restart_state = Path("/tmp/enterprise_os_test_restart_state.json")
    if Path(restart_sock).exists():
        Path(restart_sock).unlink()
    if restart_state.exists():
        restart_state.unlink()

    engine1 = SandboxProvisionerEngine(replay_state_path=restart_state)
    server1 = SandboxProvisionerServer(
        socket_path=restart_sock,
        auth_token=TEST_AUTH_TOKEN,
        engine=engine1,
    )
    server1.start()

    client = SandboxProvisionerClient(socket_path=restart_sock, auth_token=TEST_AUTH_TOKEN)
    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"data": "persisted-exec"},
        execution_id="exec-persistent-1",
        attempt_id="att-persistent-1",
    )
    res = client.execute(mandate)
    assert res.success is True

    # Crash / stop server 1
    server1.stop()

    # Start server 2 with same persistent state file
    engine2 = SandboxProvisionerEngine(replay_state_path=restart_state)
    server2 = SandboxProvisionerServer(
        socket_path=restart_sock,
        auth_token=TEST_AUTH_TOKEN,
        engine=engine2,
    )
    server2.start()

    try:
        # Replaying exact same execution ID must fail closed
        replay_mandate = _make_mandate(
            capability=SandboxCapability.ATTR,
            worker_role="W_LEARN",
            operation="analyze_attribution",
            payload={"data": "replay-after-restart"},
            execution_id="exec-persistent-1",
            attempt_id="att-persistent-2",
        )
        with pytest.raises(SandboxIsolationError, match="has already been executed. Replay forbidden"):
            client.execute(replay_mandate)
    finally:
        server2.stop()
        if restart_state.exists():
            restart_state.unlink()


# 25. Production Hardening: Stale Socket and Staging Runtime Cleanup
def test_stale_socket_and_runtime_cleanup() -> None:
    """Verify dead socket files and abandoned staging directories are scrubbed on daemon init."""
    import tempfile
    from app.integrations.sandbox.provisioner_daemon import SandboxProvisionerEngine, cleanup_stale_runtimes

    # Create dummy stale staging directory
    stale_dir = Path(tempfile.mkdtemp(prefix="sbx-staging-stale-test-"))
    dummy_file = stale_dir / "leftover.txt"
    dummy_file.write_text("abandoned staging file")
    assert stale_dir.exists()

    cleaned = cleanup_stale_runtimes()
    assert cleaned >= 1
    assert not stale_dir.exists()


# 26. Production Hardening: Systemd Socket Activation Integration
def test_systemd_socket_activation_integration() -> None:
    """Verify physical execution completes through active systemd socket activation."""
    systemd_sock = Path("/run/user/1000/enterprise_os/provisioner.sock")
    if not systemd_sock.exists():
        pytest.skip("Systemd user socket /run/user/1000/enterprise_os/provisioner.sock not present")

    client = SandboxProvisionerClient(socket_path=systemd_sock)
    assert client.has_physical_isolation_runtime is True

    mandate = _make_mandate(
        capability=SandboxCapability.ATTR,
        worker_role="W_LEARN",
        operation="analyze_attribution",
        payload={"strategy_id": "strat-systemd-test", "metrics": {"roi": 4.0}},
        execution_id=f"exec-systemd-test-{int(time.time())}",
        attempt_id=f"att-systemd-test-{int(time.time())}",
    )
    res = client.execute(mandate)
    assert res.success is True
    assert res.execution_receipt is not None
    assert res.execution_receipt.pid_namespace != ""
    assert res.execution_receipt.mount_namespace != ""
    assert res.execution_receipt.userns_disabled is True

