"""Collection classes for managing multiple tools."""

from typing import Any

from .base import (
    BaseAnthropicTool,
    ToolError,
    ToolFailure,
    ToolResult,
)


class ToolCollection:
    """A collection of sandbox computer and bash tools."""

    def __init__(self, *tools: BaseAnthropicTool):
        self.tools = tools
        self.tool_map: dict[str, BaseAnthropicTool] = {}
        self.toolset_map: dict[str, BaseAnthropicTool] = {}
        for tool in tools:
            params = tool.to_params()
            if "name" in params:
                self.tool_map[params["name"]] = tool
            else:
                self.toolset_map[getattr(tool, "toolset_name", "")] = tool

    def to_params(self) -> list[dict[str, Any]]:
        return [tool.to_params() for tool in self.tools]

    async def run(
        self,
        *,
        name: str,
        tool_input: dict[str, Any],
        toolset_name: str | None = None,
    ) -> ToolResult:
        if toolset_name is not None:
            toolset = self.toolset_map.get(toolset_name)
            if not toolset:
                return ToolFailure(error=f"Toolset {toolset_name} is invalid")
            try:
                return await toolset(action=name, **tool_input)
            except ToolError as e:
                return ToolFailure(error=e.message)
        tool = self.tool_map.get(name)
        if not tool:
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            return await tool(**tool_input)
        except ToolError as e:
            return ToolFailure(error=e.message)
