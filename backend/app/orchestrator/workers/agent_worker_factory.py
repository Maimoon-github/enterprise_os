from typing import Any

from app.mcp.registries.toolset_registry import toolset_registry
from app.orchestrator.workers.retry_policies import RetryPolicy
from app.services.skill_service import skill_service
from pydantic import BaseModel


class AgentWorkerFactory:
    """Factory creating ephemeral workers with Pydantic BaseModel validation,

    scoped MCP toolsets, and progressive-disclosure Agent Skills (Tiers 1 & 2).
    """

    @staticmethod
    def create_worker(
        name: str,
        model_tag: str,
        output_type: type[BaseModel],
        toolset_name: str | None = None,
        active_skills: list[str] | None = None,
    ) -> dict[str, Any]:
        tools = toolset_registry.get_toolset(toolset_name or name)

        # Tier 1 catalog metadata injected by default (~100 tokens per skill)
        tier1_catalog = skill_service.get_tier1_catalog()

        # Tier 2 instructions disclosed on demand for active skills (<5,000 tokens)
        tier2_instructions: dict[str, str] = {}
        allowed_tools_scope: set[str] = set()

        if active_skills:
            for skill_name in active_skills:
                instructions = skill_service.load_skill_body(skill_name)
                if instructions:
                    tier2_instructions[skill_name] = instructions
                skill_detail = skill_service.get_skill(skill_name)
                if skill_detail and skill_detail.allowed_tools:
                    allowed_tools_scope.update(skill_detail.allowed_tools)

        scoped_tools = []
        for t in tools:
            tool_name = t["name"]
            # Filter tools against allowed-tools scope if defined on active skills
            if allowed_tools_scope and not any(
                tool_name in at or at in tool_name for at in allowed_tools_scope
            ):
                continue

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
            "tier1_skills": tier1_catalog,
            "tier2_instructions": tier2_instructions,
            "active_skills": active_skills or [],
        }
