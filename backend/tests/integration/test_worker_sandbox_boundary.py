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
    assert fake_sandbox.invocations[0].capability == agent_class.capability
    assert envelope.task_id == sample_task.task_id