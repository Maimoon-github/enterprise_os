"""Verifies workers cannot directly access RAG or persistence."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

_AGENT_MODULES = [
    "app.agents.development",
    "app.agents.strategy",
    "app.agents.creative_content",
    "app.agents.creative_content_engine.subagents.research",
    "app.agents.creative_content_engine.subagents.concept",
    "app.agents.creative_content_engine.subagents.copy",
    "app.agents.creative_content_engine.subagents.visual",
    "app.agents.creative_content_engine.subagents.adaptation",
    "app.agents.creative_content_engine.subagents.quality",
    "app.agents.product_evidence",
    "app.agents.competitor_intel",
    "app.agents.customer_voice",
    "app.agents.learning_performance",
    "app.agents.base",
]

_FORBIDDEN_PREFIXES = (
    "app.services.rag",
    "app.persistence",
    "app.orchestration.rag_query_dispatch",
)


def _imported_module_names(module_dotted_path: str) -> list[str]:
    module = importlib.import_module(module_dotted_path)
    assert module.__file__ is not None
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


@pytest.mark.parametrize("module_path", _AGENT_MODULES)
def test_agents_have_no_direct_rag_or_persistence_dependency(module_path: str) -> None:
    imported = _imported_module_names(module_path)

    for name in imported:
        assert not name.startswith(_FORBIDDEN_PREFIXES), (
            f"{module_path} imports '{name}'; Model-A/RAG access must be brokered by the "
            "Intelligence Engine, and persistence must be brokered by MCP gateways."
        )


def test_only_intelligence_engine_and_context_assembly_reach_rag_dispatch() -> None:
    allowed_importers = {
        "app.orchestration.intelligence_engine",
        "app.orchestration.context_assembly",
    }

    import app.orchestration as orchestration_pkg

    package_dir = Path(orchestration_pkg.__file__).parent
    for path in package_dir.glob("*.py"):
        if path.stem == "rag_query_dispatch":
            continue
        module_name = f"app.orchestration.{path.stem}"
        imported = _imported_module_names(module_name)
        if any("rag_query_dispatch" in name for name in imported):
            assert module_name in allowed_importers, (
                f"{module_name} reaches the RAG dispatch bridge but is not an authorized caller."
            )