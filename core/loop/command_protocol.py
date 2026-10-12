# pyright: reportMissingImports=false
"""Typed Command Dispatch Protocol & Observation Schemas (TSK-10).
Defines Pydantic contracts for sandbox commands and normalized observation payloads.
Strictly enforces /home/gem workspace boundaries.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


SANDBOX_WORKSPACE_PREFIX = "/home/gem"


def _validate_sandbox_path(path_val: str) -> str:
    """Enforce security invariant: paths must reside within /home/gem and deny traversal."""
    if not path_val:
        return SANDBOX_WORKSPACE_PREFIX
    normalized = path_val.strip()
    if ".." in normalized:
        raise ValueError(f"Path traversal ('..') is strictly forbidden: {normalized}")
    if not normalized.startswith(SANDBOX_WORKSPACE_PREFIX):
        raise ValueError(
            f"Command execution restricted to container workspace '{SANDBOX_WORKSPACE_PREFIX}'. Got: '{normalized}'"
        )
    return normalized


class BrowserActionCommand(BaseModel):
    """Directives dispatched to AIO Sandbox headless browser service."""

    command_type: Literal["browser"] = "browser"
    action: Literal["navigate", "get_markdown", "screenshot", "click", "fill", "wait"]
    url: Optional[str] = None
    selector: Optional[str] = None
    text: Optional[str] = None
    wait_seconds: Optional[float] = 1.0
    screenshot_path: Optional[str] = "/home/gem/browser_screenshot.png"

    @field_validator("screenshot_path")
    @classmethod
    def validate_screenshot_path(cls, v: Optional[str]) -> Optional[str]:
        return _validate_sandbox_path(v) if v else v


class ShellExecCommand(BaseModel):
    """Directives executing terminal commands inside sandbox shell."""

    command_type: Literal["shell"] = "shell"
    command: str
    exec_dir: str = SANDBOX_WORKSPACE_PREFIX
    timeout_seconds: float = 30.0

    @field_validator("exec_dir")
    @classmethod
    def validate_exec_dir(cls, v: str) -> str:
        return _validate_sandbox_path(v)


class CodeComputeCommand(BaseModel):
    """Directives executing isolated Python or Node.js compute scripts."""

    command_type: Literal["code"] = "code"
    language: Literal["python", "javascript", "bash"] = "python"
    code: str
    cwd: str = SANDBOX_WORKSPACE_PREFIX
    timeout_seconds: int = 30

    @field_validator("cwd")
    @classmethod
    def validate_cwd(cls, v: str) -> str:
        return _validate_sandbox_path(v)


class FileIOCommand(BaseModel):
    """Directives reading, writing, or inspecting files within sandbox."""

    command_type: Literal["file"] = "file"
    operation: Literal["read", "write", "list", "replace"]
    file_path: str
    content: Optional[str] = None
    old_string: Optional[str] = None
    new_string: Optional[str] = None

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        return _validate_sandbox_path(v)


SandboxCommand = Union[
    BrowserActionCommand,
    ShellExecCommand,
    CodeComputeCommand,
    FileIOCommand,
]


class ObservationResult(BaseModel):
    """Normalized observation payload returned from AIO Sandbox execution."""

    command_type: Literal["browser", "shell", "code", "file"]
    status: Literal["success", "error", "timeout"]
    exit_code: Optional[int] = 0
    stdout: str = ""
    stderr: str = ""
    dom_markdown: Optional[str] = None
    har_logs: Optional[List[Dict[str, Any]]] = None
    artifacts_created: List[str] = Field(default_factory=list)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float = 0.0
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
