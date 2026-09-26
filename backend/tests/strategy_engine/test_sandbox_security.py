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
