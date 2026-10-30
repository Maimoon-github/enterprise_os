from typing import Any

from app.mcp.registries.toolset_registry import toolset_registry
from app.orchestrator.workers.retry_policies import RetryPolicy
from pydantic import BaseModel


class AgentWorkerFactory:
    """Factory creating ephemeral workers with Pydantic BaseModel validation and scoped MCP toolsets."""

    @staticmethod
    def create_worker(
        name: str,
        model_tag: str,
        output_type: type[BaseModel],
        toolset_name: str | None = None,
    ) -> dict[str, Any]:
        tools = toolset_registry.get_toolset(toolset_name or name)
        scoped_tools = []
        for t in tools:
            tool_name = t["name"]
            scoped_tools.append({
                "name": tool_name,
                "server": t["server"],
                "max_retries": RetryPolicy.get_max_retries(tool_name),
            })

        return {
            "worker_name": name,
            "model": model_tag,
            "output_contract": output_type.__name__,
            "toolset": scoped_tools,
        }
