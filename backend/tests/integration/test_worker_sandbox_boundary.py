"""Verifies all seven workers use only the sandbox adapter."""

from __future__ import annotations

import ast
import importlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import TenantScope
from tests.conftest import FakeSandboxClient

_AGENT_MODULES = [
    "app.agents.development",
    "app.agents.strategy",
    "app.agents.creative_content",
    "app.agents.product_evidence",
    "app.agents.competitor_intel",
    "app.agents.customer_voice",
    "app.agents.learning_performance",
]

_DISALLOWED_IMPORT_PREFIXES = (
    "app.persistence",
    "app.services",
    "app.mcp",
    "app.security",
    "app.integrations.llm",
    "app.integrations.cms",
    "app.integrations.ads",
    "app.integrations.social",
)


def _imported_module_names(module_dotted_path: str) -> list[str]:
    module = importlib.import_module(module_dotted_path)
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


@pytest.mark.parametrize("module_path", _AGENT_MODULES)
def test_worker_module_never_imports_outside_sandbox_boundary(module_path: str) -> None:
    imported = _imported_module_names(module_path)

    for name in imported:
        assert not name.startswith(_DISALLOWED_IMPORT_PREFIXES), (
            f"{module_path} imports '{name}', which bypasses the sandbox boundary."
        )


@pytest.mark.parametrize("module_path", _AGENT_MODULES)
@pytest.mark.asyncio
async def test_worker_executes_only_through_sandbox_client(
    module_path: str, sample_task
) -> None:
    module = importlib.import_module(module_path)
    agent_classes = [
        obj
        for name, obj in vars(module).items()
        if isinstance(obj, type) and name.endswith("Agent") and obj.__module__ == module.__name__
    ]
    assert len(agent_classes) == 1
    agent_class = agent_classes[0]

    fake_sandbox = FakeSandboxClient()
    agent = agent_class(fake_sandbox)
    grant = TaskGrant(
        task_id=sample_task.task_id,
        worker_role=sample_task.worker_role,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    envelope = await agent.run(grant, context={})

    assert len(fake_sandbox.invocations) == 1
    inv = fake_sandbox.invocations[0]
    assert inv.capability == agent_class.capability
    assert inv.worker_role == sample_task.worker_role
    assert inv.tenant_id == "acme"
    assert inv.execution_id.startswith("exec-")
    assert inv.operation is not None
    if inv.capability == "S_SCRAPE":
        from app.schemas.sandbox import NetworkPolicy
        assert inv.network_policy == NetworkPolicy.CONTROLLED
    else:
        from app.schemas.sandbox import NetworkPolicy
        assert inv.network_policy == NetworkPolicy.DISABLED
    assert envelope.task_id == sample_task.task_id


def test_validate_capability_access_authorized_cases() -> None:
    from app.integrations.sandbox.capabilities import validate_capability_access
    from app.schemas.sandbox import NetworkPolicy

    # S_CODE
    p1 = validate_capability_access("S_CODE", "W_DEV", "generate_diff")
    assert p1.worker_role == "W_DEV"
    assert p1.network_policy == NetworkPolicy.DISABLED

    # S_SCRAPE
    p2 = validate_capability_access("S_SCRAPE", "W_COMP", "scrape_prices", requested_network=NetworkPolicy.CONTROLLED)
    assert p2.worker_role == "W_COMP"
    assert p2.network_policy == NetworkPolicy.CONTROLLED


def test_validate_capability_access_unauthorized_role_raises() -> None:
    from app.core.exceptions import SandboxInvocationError
    from app.integrations.sandbox.capabilities import validate_capability_access

    with pytest.raises(SandboxInvocationError, match="not authorized"):
        validate_capability_access("S_SCRAPE", "W_DEV", "scrape_prices")

    with pytest.raises(SandboxInvocationError, match="not authorized"):
        validate_capability_access("S_CODE", "W_STRAT", "generate_diff")


def test_validate_capability_access_unknown_capability_raises() -> None:
    from app.core.exceptions import SandboxInvocationError
    from app.integrations.sandbox.capabilities import validate_capability_access

    with pytest.raises(SandboxInvocationError, match="Unknown sandbox capability"):
        validate_capability_access("S_UNKNOWN", "W_DEV", "op")


def test_validate_capability_access_unauthorized_operation_raises() -> None:
    from app.core.exceptions import SandboxInvocationError
    from app.integrations.sandbox.capabilities import validate_capability_access

    with pytest.raises(SandboxInvocationError, match="not allowed"):
        validate_capability_access("S_STRAT", "W_STRAT", "unauthorized_operation")


def test_validate_capability_access_network_policy_violation_raises() -> None:
    from app.core.exceptions import SandboxInvocationError
    from app.integrations.sandbox.capabilities import validate_capability_access
    from app.schemas.sandbox import NetworkPolicy

    with pytest.raises(SandboxInvocationError, match="Egress network policy"):
        validate_capability_access("S_CODE", "W_DEV", "generate_diff", requested_network=NetworkPolicy.CONTROLLED)


@pytest.mark.asyncio
async def test_sandbox_client_sanitizes_credentials() -> None:
    from app.integrations.sandbox.client import SandboxClient
    from app.schemas.sandbox import SandboxInvocationMandate

    client = SandboxClient()
    mandate = SandboxInvocationMandate(
        execution_id="exec-sec-1",
        worker_role="W_DEV",
        tenant_id="acme",
        capability="S_CODE",
        operation="generate_diff",
        payload={
            "api_key": "supersecretkey123",
            "bearer_header": "Bearer secret_token_xyz",
            "password": "mypassword456",
            "safe_data": "public_info",
        },
    )

    result = await client.execute(mandate)
    assert result.success is True
    # Verify outputs are sanitized
    for key, val in result.output.items():
        if isinstance(val, str):
            assert "supersecretkey123" not in val
            assert "secret_token_xyz" not in val
            assert "mypassword456" not in val


@pytest.mark.asyncio
async def test_sandbox_client_timeout_handling() -> None:
    import asyncio
    from unittest.mock import patch
    from app.integrations.sandbox.client import SandboxClient
    from app.schemas.sandbox import SandboxExecutionStatus, SandboxInvocationMandate

    client = SandboxClient()
    mandate = SandboxInvocationMandate(
        execution_id="exec-time-1",
        worker_role="W_DEV",
        tenant_id="acme",
        capability="S_CODE",
        operation="generate_diff",
        payload={"diff": "content"},
        timeout_seconds=1,
    )

    async def slow_execution(*args, **kwargs):
        await asyncio.sleep(5)
        return {"output": "never"}

    with patch.object(client, "_execute_in_isolated_runtime", side_effect=slow_execution):
        result = await client.execute(mandate)
        assert result.success is False
        assert result.status == SandboxExecutionStatus.TIMEOUT
        assert any("timed out" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_sandbox_client_provenance_and_duration() -> None:
    from app.integrations.sandbox.client import SandboxClient
    from app.schemas.sandbox import SandboxExecutionStatus, SandboxInvocationMandate

    client = SandboxClient()
    mandate = SandboxInvocationMandate(
        execution_id="exec-prov-1",
        worker_role="W_STRAT",
        tenant_id="tenant-xyz",
        capability="S_ALLOC",
        operation="optimize_budget",
        payload={"budget": 10000},
    )

    result = await client.execute(mandate)
    assert result.success is True
    assert result.status == SandboxExecutionStatus.COMPLETED
    assert result.execution_duration_ms is not None
    assert result.execution_duration_ms >= 0
    assert result.provenance is not None
    assert result.provenance["capability"] == "S_ALLOC"
    assert result.provenance["worker_role"] == "W_STRAT"
    assert result.provenance["tenant_id"] == "tenant-xyz"