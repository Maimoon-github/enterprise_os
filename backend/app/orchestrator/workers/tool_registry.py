from typing import Callable, Any

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, tool_func: Callable[..., Any]):
        self._tools[name] = tool_func

    def get(self, name: str) -> Callable[..., Any] | None:
        return self._tools.get(name)

    def list_all(self) -> list[str]:
        return list(self._tools.keys())

tool_registry = ToolRegistry()
