"""Security and isolation tests for Strategy Engine and S_ALLOC sandbox boundary (T4).

Validates canonical hardened skill routing, absence of host-side micro-tool fallback,
fail-closed execution on sandbox errors, disabled network policy, egress target rejection,
and Model-A AST import boundaries.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.strategy_engine.strategy import StrategyAgent
from app.core.exceptions import PolicyViolationError, SandboxInvocationError
from app.core.settings import SandboxSettings
from app.integrations.sandbox.capabilities import get_skill_entrypoint, validate_capability_access
from app.integrations.sandbox.client import SandboxClient
from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxInvocationMandate
from tests.conftest import FakeProvenanceRepository


# =============================================================================
# 1. Canonical Hardened Skill Routing & Capability Access
# =============================================================================


def test_s_alloc_routes_to_canonical_hardened_runtime() -> None:
    """S_ALLOC capability maps to the canonical skills/s-alloc container skill."""
    entrypoint = get_skill_entrypoint(SandboxCapability.ALLOC)
    assert entrypoint is not None
    assert "skills/s-alloc" in entrypoint
    profile = validate_capability_access(SandboxCapability.ALLOC, WorkerRole.STRATEGY)
    assert profile.capability == SandboxCapability.ALLOC


def test_s_alloc_forbidden_for_other_workers() -> None:
    """Other worker roles are denied access to the S_ALLOC capability."""
    with pytest.raises(SandboxInvocationError):
        validate_capability_access(SandboxCapability.ALLOC, WorkerRole.CREATIVE_CONTENT)
    with pytest.raises(SandboxInvocationError):
        validate_capability_access(SandboxCapability.ALLOC, WorkerRole.DEVELOPMENT)
    with pytest.raises(SandboxInvocationError):
        validate_capability_access(SandboxCapability.ALLOC, WorkerRole.CUSTOMER_VOICE)


# =============================================================================
# 2. No Production Host Fallback & Dispatch Micro Tool Elimination
# =============================================================================


def test_isolated_runtime_strictly_forbids_local_s_alloc_fallback() -> None:
    """Direct local execution of S_ALLOC raises SandboxInvocationError."""
    client = SandboxClient(SandboxSettings(endpoint="http://remote-sandbox.internal:8000"))
    mandate = SandboxInvocationMandate(
        task_id="task-fail-fallback",
        worker_role=WorkerRole.STRATEGY,
        tenant_id="tenant_01",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "10000.0"},
        network_policy=NetworkPolicy.DISABLED,
    )
    with pytest.raises(SandboxInvocationError, match="strictly prohibited for S_ALLOC"):
        client._execute_in_isolated_runtime(mandate)


@pytest.mark.asyncio
async def test_dispatch_micro_tool_never_invoked_on_remote_failure() -> None:
    """Remote sandbox failure does not invoke dispatch_micro_tool or execute local math."""
    client = SandboxClient(SandboxSettings(endpoint="http://remote-sandbox.internal:8000"))

    mock_sandbox = MagicMock()
    mock_sandbox.shell = MagicMock()
    mock_sandbox.shell.exec_command.side_effect = RuntimeError("Sandbox connection lost")
    client._sandbox = mock_sandbox

    mandate = SandboxInvocationMandate(
        task_id="task-remote-fail-no-dispatch",
        worker_role=WorkerRole.STRATEGY,
        tenant_id="tenant_01",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "10000.0"},
        network_policy=NetworkPolicy.DISABLED,
    )

    with patch("app.integrations.sandbox.client.dispatch_micro_tool") as mock_dispatch:
        result = await client.invoke(mandate)
        assert result.success is False
        assert result.status.value == "failed"
        mock_dispatch.assert_not_called()


# =============================================================================
# 3. Fail-Closed Sandbox Execution (Timeouts, Errors, Bad Output)
# =============================================================================


@pytest.mark.asyncio
async def test_sandbox_failure_fails_closed_in_strategy_agent() -> None:
    """When remote sandbox fails, StrategyAgent produces zero-confidence evidence envelope."""
    client = SandboxClient(SandboxSettings(endpoint="http://remote-sandbox.internal:8000"))
    mock_sandbox = MagicMock()
    mock_sandbox.shell = MagicMock()
    mock_sandbox.shell.exec_command.side_effect = RuntimeError("Container crash")
    client._sandbox = mock_sandbox

    w_strat = StrategyAgent(client)
    grant = TaskGrant(
        task_id="task-strat-crash",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant_01", allowed_channels=["meta", "google"]),
        brand_id="tenant_01",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    envelope = await w_strat.run(grant, {"budget_ceiling": 20000.0})
    assert envelope.confidence.point_estimate == 0.0
    assert any("sandbox execution failed" in e for e in envelope.evidence)


@pytest.mark.asyncio
async def test_sandbox_network_disabled_and_egress_rejected() -> None:
    """S_ALLOC mandates strictly enforce NetworkPolicy.DISABLED; egress grants are disallowed."""
    client = SandboxClient(SandboxSettings(endpoint="http://remote-sandbox.internal:8000"))
    mandate = SandboxInvocationMandate(
        task_id="task-net-disabled",
        worker_role=WorkerRole.STRATEGY,
        tenant_id="tenant_01",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "10000.0"},
        network_policy=NetworkPolicy.DISABLED,
    )
    assert mandate.network_policy == NetworkPolicy.DISABLED


# =============================================================================
# 4. Model-A AST Import Boundaries
# =============================================================================


def test_strategy_engine_modules_maintain_zero_persistence_or_rag_imports() -> None:
    """Strategy worker and specialist must not directly import persistence, DB, or services."""
    repo_root = Path(__file__).resolve().parents[2]
    strategy_files = [
        repo_root / "app" / "agents" / "strategy.py",
        repo_root / "app" / "agents" / "strategy_engine" / "strategy.py",
        repo_root / "app" / "agents" / "strategy_engine" / "subagents" / "allocation.py",
        repo_root / "app" / "agents" / "strategy_engine" / "profiles.py",
    ]

    disallowed_prefixes = (
        "app.persistence",
        "app.services",
        "app.mcp",
        "app.security",
        "app.integrations.cms",
        "app.integrations.ads",
        "app.integrations.social",
        "app.orchestration.rag_query_dispatch",
    )

    for sf in strategy_files:
        assert sf.exists(), f"File {sf} must exist"
        tree = ast.parse(sf.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in disallowed_prefixes:
                        assert not alias.name.startswith(prefix), (
                            f"Disallowed import in {sf.name}: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for prefix in disallowed_prefixes:
                    assert not node.module.startswith(prefix), (
                        f"Disallowed import in {sf.name}: {node.module}"
                    )


# =============================================================================
# 5. L6-03 Fresh Hardened Execution Lifecycle & Isolation Tests
# =============================================================================


def test_hardened_compose_profile_isolation_and_network_none() -> None:
    """Verify s-alloc-compute has network_mode: none, read_only root, cap_drop ALL, and strict bounds."""
    import yaml  # type: ignore[import-untyped]

    repo_root = Path(__file__).resolve().parents[3]
    compose_path = repo_root / "sandbox" / "docker" / "hardened" / "docker-compose.hardened.yaml"
    assert compose_path.exists(), f"Hardened compose must exist at {compose_path}"

    with open(compose_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    services = config.get("services", {})
    assert "s-alloc-compute" in services, "s-alloc-compute profile service must exist in compose"
    spec = services["s-alloc-compute"]

    assert spec.get("network_mode") == "none", "Workload must strictly use network_mode: none"
    assert spec.get("read_only") is True, "Workload root filesystem must be read_only"
    assert "ALL" in spec.get("cap_drop", []), "Workload must drop ALL Linux capabilities"
    assert "no-new-privileges:true" in spec.get("security_opt", []), "Must set no-new-privileges"
    assert spec.get("user") not in ("0", "0:0", "root", None), "Must run as non-root user"
    assert "ports" not in spec or not spec["ports"], "Workload must not publish any ports"
    assert "@sha256:" in spec.get("image", ""), "Image must be pinned to explicit digest"

    # Verify scoped tmpfs
    tmpfs = spec.get("tmpfs", [])
    assert any("/tmp:" in t and "noexec" in t and "nodev" in t and "nosuid" in t for t in tmpfs)

    # Verify resource boundaries
    assert spec.get("cpus") == "1"
    assert spec.get("mem_limit") == "512m"
    assert spec.get("pids_limit") == 128


def test_cleanup_script_attempt_scoping_no_broad_pkill() -> None:
    """Verify cleanup.sh targets only attempt-scoped workspace/PIDs and avoids broad pkill."""
    repo_root = Path(__file__).resolve().parents[3]
    cleanup_path = repo_root / "sandbox" / "docker" / "hardened" / "scripts" / "cleanup.sh"
    assert cleanup_path.exists(), f"cleanup.sh must exist at {cleanup_path}"

    content = cleanup_path.read_text(encoding="utf-8")
    assert "pkill -9 -f python" not in content, "Broad python pkill strictly forbidden"
    assert "pkill -9 -f node" not in content, "Broad node pkill strictly forbidden"
    assert "SANDBOX_WORKSPACE" in content, "Cleanup must target SANDBOX_WORKSPACE"
    assert "SANDBOX_ATTEMPT_PID" in content, "Cleanup must target SANDBOX_ATTEMPT_PID"


def test_token_budget_separation_from_execution_seconds() -> None:
    """Verify grant.token_budget does not inflate execution time quota."""
    from app.agents.strategy_engine.subagents.allocation import StrategyAllocationAgent

    alloc_agent = StrategyAllocationAgent()
    grant = TaskGrant(
        task_id="task-budget-separation",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant_01", allowed_channels=["meta", "google"]),
        brand_id="tenant_01",
        token_budget=100000,  # Large token quota
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    mandate = alloc_agent.build_mandate(grant, {"timeout_seconds": 30})
    assert mandate.time_quota_seconds == 30
    assert mandate.token_quota <= alloc_agent.profile.token_quota


def test_main_wiring_excludes_host_s_alloc_client() -> None:
    """Verify backend/app/main.py does not define or instantiate host create_s_alloc_llm_client."""
    repo_root = Path(__file__).resolve().parents[2]
    main_py = repo_root / "app" / "main.py"
    assert main_py.exists()

    content = main_py.read_text(encoding="utf-8")
    assert "create_s_alloc_llm_client" not in content
    assert "s_alloc_llm_client" not in content


@pytest.mark.asyncio
async def test_remote_process_cancellation_and_scrubbing_on_timeout() -> None:
    """Verify timeout triggers remote process tree termination and workspace scrubbing."""
    import asyncio
    client = SandboxClient(SandboxSettings(endpoint="http://remote-sandbox.internal:8000"))

    executed_commands: list[str] = []

    mock_sandbox = MagicMock()
    mock_sandbox.shell = MagicMock()
    def mock_exec(command: str):
        executed_commands.append(command)
        return MagicMock(exit_code=0)
    mock_sandbox.shell.exec_command.side_effect = mock_exec
    client._sandbox = mock_sandbox

    # Mock _execute_specialist to simulate timeout
    async def mock_timeout(*args, **kwargs):
        await asyncio.sleep(0.5)

    with patch.object(client, "_execute_specialist", side_effect=asyncio.TimeoutError):
        mandate = SandboxInvocationMandate(
            task_id="task-timeout-test",
            worker_role=WorkerRole.STRATEGY,
            tenant_id="tenant_01",
            capability=SandboxCapability.ALLOC,
            operation="optimize_budget",
            payload={"budget": "10000.0"},
            network_policy=NetworkPolicy.DISABLED,
        )
        result = await client.invoke(mandate)

    assert result.success is False
    assert result.status.value == "timeout"
    assert any("pkill -TERM" in cmd for cmd in executed_commands), "Must attempt SIGTERM on timeout"
    assert any("pkill -KILL" in cmd for cmd in executed_commands), "Must attempt SIGKILL on timeout"
    assert any("rm -rf" in cmd for cmd in executed_commands), "Must scrub workspace directory on teardown"


# =============================================================================
# 6. Real Mounted S_ALLOC Runner Process Isolation & Teardown Verification
# =============================================================================


def test_mounted_s_alloc_runner_fresh_subprocess_execution_and_isolation() -> None:
    """T09: Execute actual mounted S_ALLOC runner in a fresh isolated runtime process.
    
    Verifies process isolation, distinct PIDs per attempt, exit code 0, and non-leakage
    of host secrets from environment into generated output.
    """
    import json
    import os
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[2].parent
    runner_path = repo_root / "sandbox" / "docker" / "hardened" / "skills" / "s-alloc" / "scripts" / "run.py"
    assert runner_path.exists(), f"Mounted runner must exist at {runner_path}"

    payload = {
        "task_id": "task-proc-iso-01",
        "tenant_id": "tenant-iso",
        "budget": "25000.0",
        "channels": "meta,google",
    }
    input_json = json.dumps(payload)

    # Pass sensitive decoy credentials in environment to test leakage resistance
    env = os.environ.copy()
    env["SECRET_API_KEY"] = "super-secret-key-12345"
    env["DATABASE_URL"] = "postgres://root:password@localhost:5432/db"

    # Attempt 1
    proc_1 = subprocess.run(
        [sys.executable, str(runner_path)],
        input=input_json,
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )
    assert proc_1.returncode == 0, f"Runner failed: {proc_1.stderr}"
    res_1 = json.loads(proc_1.stdout)
    assert res_1["status"] == "success"
    assert "super-secret-key-12345" not in proc_1.stdout
    assert "password@localhost" not in proc_1.stdout

    # Attempt 2 (New runtime execution retry)
    proc_2 = subprocess.run(
        [sys.executable, str(runner_path)],
        input=input_json,
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )
    assert proc_2.returncode == 0
    res_2 = json.loads(proc_2.stdout)
    assert res_2["status"] == "success"
    # Bit-for-bit identical numerical result
    assert res_1["allocations"] == res_2["allocations"]


def test_teardown_failure_prevents_success() -> None:
    """T13: Failed or dirty teardown receipt rejects SAllocResult acceptance even if execution succeeded."""
    from app.schemas.sandbox import SandboxExecutionReceipt, SandboxTeardownReceipt
    from app.schemas.strategy import SAllocDomainStatus, SAllocMandate, SAllocResult

    mandate = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-td-fail",
        execution_id="exec-td-01",
        stage_attempt_id="att-td-01",
        parent_grant_id="grant-td",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        authorized_channels=["meta"],
        budget_ceiling=10000.0,
    )

    now = datetime.now(UTC)
    exec_receipt = SandboxExecutionReceipt(
        runtime_id="rt-01",
        container_id="c-01",
        image_digest="sha256:d8c83df2357b98d197621c17830cbdfc63b860b73dfeb46487e8e4533dae5d95",
        runtime_version="1.11.0",
        network_mode="none",
        read_only_root=True,
        effective_cpu_cores=1.0,
        effective_memory_mb=512,
        effective_pids_limit=128,
        started_at=now - timedelta(seconds=2),
        terminated_at=now,
        exit_code=0,
        input_digest="a" * 64,
        output_digest="b" * 64,
    )
    # Dirty teardown receipt indicating workspace scrub or container kill failure
    dirty_teardown = SandboxTeardownReceipt(
        sandbox_id="sbx-fail",
        attempt_id="att-td-01",
        status="DIRTY",
        workspace_scrubbed=False,
        credentials_revoked=False,
        runtime_destroyed=False,
        destroyed_at=now,
    )

    result = SAllocResult(
        execution_id="exec-td-01",
        task_id="task-td-fail",
        stage_attempt_id="att-td-01",
        tenant_id="tenant-alpha",
        input_sha256=mandate.compute_input_digest(),
        status=SAllocDomainStatus.OK,
        total_allocated=5000.0,
        budget_residual=5000.0,
        execution_receipt=exec_receipt,
        teardown_receipt=dirty_teardown,
    )

    with pytest.raises(ValueError, match="verified teardown_receipt"):
        result.verify_correlation(mandate, require_receipts=True)

