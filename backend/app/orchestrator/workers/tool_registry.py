from collections.abc import Callable
from typing import Any

from app.orchestrator.workers.retry_policies import RetryPolicy


class ToolRegistry:
    """Manages available worker tools and binds side-effect retry policies."""

    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}
        self._retry_limits: dict[str, int] = {}

    def register(
        self,
        name: str,
        tool_func: Callable[..., Any],
        max_retries: int | None = None,
    ) -> None:
        self._tools[name] = tool_func
        self._retry_limits[name] = (
            max_retries if max_retries is not None else RetryPolicy.get_max_retries(name)
        )

    def get(self, name: str) -> Callable[..., Any] | None:
        return self._tools.get(name)

    def get_retry_limit(self, name: str) -> int:
        return self._retry_limits.get(name, RetryPolicy.get_max_retries(name))

    def list_all(self) -> list[str]:
        return list(self._tools.keys())

    def get_scoped_tools(self, allowed_tools: list[str] | None = None) -> list[str]:
        """Filter registered tools against an explicit allowed-tools scope list."""
        all_tools = self.list_all()
        if not allowed_tools:
            return all_tools
        return [
            t
            for t in all_tools
            if t in allowed_tools or any(t in a for a in allowed_tools)
        ]


tool_registry = ToolRegistry()
