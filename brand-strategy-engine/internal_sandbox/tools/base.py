"""Base tool abstractions and execution result containers."""

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, fields, replace
from typing import Any, Dict, Optional


class BaseTool(metaclass=ABCMeta):
    """Abstract base class for internal sandbox tools."""

    @abstractmethod
    async def __call__(self, **kwargs) -> Any:
        """Executes the tool with keyword arguments."""
        ...

    @abstractmethod
    def to_params(self) -> Dict[str, Any]:
        """Returns JSON schema parameters for the tool."""
        ...


class BaseAnthropicTool(BaseTool):
    """Abstract base class for Anthropic / Agent computer tools."""
    pass


@dataclass(kw_only=True, frozen=True)
class ToolResult:
    """Represents the structured result of an action execution."""

    output: Optional[str] = None
    error: Optional[str] = None
    base64_image: Optional[str] = None
    system: Optional[str] = None

    def __bool__(self) -> bool:
        return any(getattr(self, f.name) for f in fields(self))

    def __add__(self, other: "ToolResult") -> "ToolResult":
        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ) -> Optional[str]:
            if field and other_field:
                if concatenate:
                    return field + "\n" + other_field
                raise ValueError("Cannot combine non-concatenable tool results")
            return field or other_field

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            base64_image=combine_fields(self.base64_image, other.base64_image, False),
            system=combine_fields(self.system, other.system),
        )

    def replace(self, **kwargs) -> "ToolResult":
        return replace(self, **kwargs)


class CLIResult(ToolResult):
    """A ToolResult specialized for command-line interface execution."""
    pass


class ToolFailure(ToolResult):
    """A ToolResult representing an explicit failure state."""
    pass


class ToolError(Exception):
    """Raised when an internal tool encounters an unrecoverable execution error."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
