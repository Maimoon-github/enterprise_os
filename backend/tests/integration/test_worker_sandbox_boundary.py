"""Verifies all seven workers use only the sandbox adapter."""
import inspect

from app.agents import (
    competitor_intel,
    creative_content,
    customer_voice,
    development,
    learning_performance,
    product_evidence,
    strategy,
)

MODULES = [
    development,
    strategy,
    creative_content,
    product_evidence,
    competitor_intel,
    customer_voice,
    learning_performance,
]


def test_workers_import_only_sandbox_client() -> None:
    for module in MODULES:
        source = inspect.getsource(module)
        assert "app.integrations.sandbox.client" in source
        assert "import agent_sandbox" not in source
