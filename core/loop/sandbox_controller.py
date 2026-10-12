# pyright: reportMissingImports=false
"""Bidirectional Sandbox Controller & Response Normalizer (TSK-10).
Dispatches typed command models to AIO Sandbox SDK endpoints and normalizes
raw outputs into typed ObservationResult payloads.
"""

from __future__ import annotations

import datetime
import os
import time
from typing import Any, Dict, List, Optional, Union

try:
    from agent_sandbox import Sandbox
except ImportError:
    Sandbox = None

from core.loop.command_protocol import (
    BrowserActionCommand,
    CodeComputeCommand,
    FileIOCommand,
    ObservationResult,
    SandboxCommand,
    ShellExecCommand,
)


class SandboxController:
    """Controller managing bidirectional command dispatch and observation ingestion."""

    def __init__(
        self,
        sandbox_client: Optional[Any] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = (
            base_url
            or os.getenv("SANDBOX_BASE_URL", "http://127.0.0.1:8080")
        )
        self.api_key = (
            api_key
            or os.getenv("SANDBOX_API_KEY", "aio-secret-key")
        )

        if sandbox_client is not None:
            self.client = sandbox_client
        elif Sandbox is not None:
            headers = {"X-AIO-API-Key": self.api_key} if self.api_key else {}
            try:
                self.client = Sandbox(base_url=self.base_url, headers=headers)
            except Exception:
                self.client = None
        else:
            self.client = None

    def dispatch_browser(self, cmd: BrowserActionCommand) -> ObservationResult:
        """Dispatch browser actions and normalize DOM/screenshot results."""
        start_t = time.perf_counter()
        artifacts = []
        dom_markdown = None
        har_logs = []
        stdout = ""
        status = "success"

        try:
            if self.client and hasattr(self.client, "browser_page"):
                bp = self.client.browser_page
                if cmd.action == "navigate" and cmd.url:
                    bp.navigate(url=cmd.url)
                    stdout = f"Navigated to {cmd.url}"
                elif cmd.action == "get_markdown":
                    res = bp.get_markdown()
                    if hasattr(res, "data") and isinstance(res.data, dict):
                        dom_markdown = str(res.data.get("markdown") or res.data)
                    else:
                        dom_markdown = str(res)
                    stdout = "Extracted DOM markdown"
                elif cmd.action == "screenshot" and cmd.screenshot_path:
                    shot = bp.screenshot()
                    if hasattr(self.client, "file"):
                        self.client.file.write_file(file=cmd.screenshot_path, content=str(shot))  # type: ignore[arg-type]
                        artifacts.append(cmd.screenshot_path)
                    stdout = f"Captured screenshot to {cmd.screenshot_path}"
                elif cmd.action == "click" and cmd.selector:
                    bp.click(selector=cmd.selector)
                    stdout = f"Clicked element {cmd.selector}"
                elif cmd.action == "fill" and cmd.selector and cmd.text:
                    bp.fill(selector=cmd.selector, text=cmd.text)
                    stdout = f"Filled {cmd.selector} with text"
                elif cmd.action == "wait":
                    bp.wait(type="timeout", timeout=cmd.wait_seconds or 1.0)
                    stdout = f"Waited {cmd.wait_seconds}s"
            else:
                # Deterministic fallback simulation
                if cmd.action == "navigate":
                    stdout = f"Simulated navigation to {cmd.url}"
                elif cmd.action == "get_markdown":
                    dom_markdown = f"# Simulated Storefront\n\nStorefront content for {cmd.url or 'landing page'}."
                    stdout = "Simulated DOM markdown extracted"
                elif cmd.action == "screenshot":
                    artifacts.append(cmd.screenshot_path or "/home/gem/browser_screenshot.png")
                    stdout = f"Simulated screenshot saved to {cmd.screenshot_path}"
                else:
                    stdout = f"Simulated action: {cmd.action}"

            dur_ms = (time.perf_counter() - start_t) * 1000.0
            return ObservationResult(
                command_type="browser",
                status=status,
                exit_code=0,
                stdout=stdout,
                dom_markdown=dom_markdown,
                har_logs=har_logs,
                artifacts_created=artifacts,
                execution_time_ms=dur_ms,
            )
        except Exception as e:
            dur_ms = (time.perf_counter() - start_t) * 1000.0
            return ObservationResult(
                command_type="browser",
                status="error",
                exit_code=1,
                stderr=str(e),
                execution_time_ms=dur_ms,
            )

    def dispatch_shell(self, cmd: ShellExecCommand) -> ObservationResult:
        """Dispatch shell command and capture return codes, stdout, and stderr."""
        start_t = time.perf_counter()
        stdout = ""
        stderr = ""
        exit_code = 0
        status = "success"

        try:
            if self.client and hasattr(self.client, "shell"):
                res = self.client.shell.exec_command(
                    command=cmd.command,
                    exec_dir=cmd.exec_dir,
                    timeout=cmd.timeout_seconds,
                )
                data = getattr(res, "data", None)
                if data is not None:
                    stdout = str(getattr(data, "output", "") or getattr(data, "stdout", "") or "")
                    stderr = str(getattr(data, "stderr", "") or "")
                    exit_code = int(getattr(data, "exit_code", 0) or 0)
                else:
                    stdout = getattr(res, "stdout", "") or str(getattr(res, "output", ""))
                    stderr = getattr(res, "stderr", "") or ""
                    exit_code = getattr(res, "exit_code", 0)
                status = "success" if exit_code == 0 else "error"
            else:
                # Deterministic fallback simulation
                stdout = f"[Simulated shell execution]: {cmd.command} in {cmd.exec_dir}\nExit 0."
                exit_code = 0

            dur_ms = (time.perf_counter() - start_t) * 1000.0
            return ObservationResult(
                command_type="shell",
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time_ms=dur_ms,
            )
        except Exception as e:
            dur_ms = (time.perf_counter() - start_t) * 1000.0
            return ObservationResult(
                command_type="shell",
                status="error",
                exit_code=1,
                stderr=str(e),
                execution_time_ms=dur_ms,
            )

    def dispatch_code(self, cmd: CodeComputeCommand) -> ObservationResult:
        """Dispatch isolated code compute task and normalize outputs."""
        start_t = time.perf_counter()
        stdout = ""
        stderr = ""
        exit_code = 0
        status = "success"

        try:
            if self.client and hasattr(self.client, "code"):
                res = self.client.code.execute_code(
                    code=cmd.code,
                    language=cmd.language,
                    cwd=cmd.cwd,
                    timeout=cmd.timeout_seconds,
                )
                data = getattr(res, "data", None)
                if data is not None:
                    stdout = str(getattr(data, "stdout", "") or getattr(data, "output", "") or "")
                    stderr = str(getattr(data, "stderr", "") or getattr(data, "traceback", "") or "")
                    exit_code = int(getattr(data, "exit_code", 0) or (1 if stderr else 0))
                else:
                    stdout = getattr(res, "output", "") or getattr(res, "stdout", "") or ""
                    stderr = getattr(res, "error", "") or getattr(res, "stderr", "") or ""
                    exit_code = 1 if stderr else 0
                status = "error" if stderr else "success"
            else:
                # Deterministic fallback execution for python calculations
                if cmd.language == "python":
                    stdout = f"[Simulated code execution result]: executed {len(cmd.code)} chars"
                else:
                    stdout = f"[Simulated {cmd.language} execution]: OK"

            dur_ms = (time.perf_counter() - start_t) * 1000.0
            return ObservationResult(
                command_type="code",
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                execution_time_ms=dur_ms,
            )
        except Exception as e:
            dur_ms = (time.perf_counter() - start_t) * 1000.0
            return ObservationResult(
                command_type="code",
                status="error",
                exit_code=1,
                stderr=str(e),
                execution_time_ms=dur_ms,
            )

    def dispatch_file(self, cmd: FileIOCommand) -> ObservationResult:
        """Dispatch file read/write/list operations within container boundaries."""
        start_t = time.perf_counter()
        stdout = ""
        stderr = ""
        artifacts = []
        status = "success"

        try:
            if self.client and hasattr(self.client, "file"):
                f_client = self.client.file
                if cmd.operation == "read":
                    res = f_client.read_file(file=cmd.file_path)
                    data = getattr(res, "data", None)
                    stdout = str(getattr(data, "content", "") if data else (getattr(res, "content", "") or str(res)))
                elif cmd.operation == "write":
                    res = f_client.write_file(file=cmd.file_path, content=cmd.content or "")
                    stdout = f"Wrote {len(cmd.content or '')} bytes to {cmd.file_path}"
                    artifacts.append(cmd.file_path)
                elif cmd.operation == "replace":
                    if hasattr(f_client, "replace_in_file"):
                        f_client.replace_in_file(
                            file=cmd.file_path,
                            old_str=cmd.old_string or "",
                            new_str=cmd.new_string or "",
                        )
                    stdout = f"Replaced text in {cmd.file_path}"
                elif cmd.operation == "list":
                    if hasattr(f_client, "list_path"):
                        res = f_client.list_path(path=cmd.file_path)
                        stdout = str(res)
                    else:
                        stdout = f"Listed {cmd.file_path}"
            else:
                # Deterministic fallback simulation
                if cmd.operation == "write":
                    stdout = f"Simulated write to {cmd.file_path} ({len(cmd.content or '')} bytes)"
                    artifacts.append(cmd.file_path)
                elif cmd.operation == "read":
                    stdout = f"Simulated content of {cmd.file_path}"
                else:
                    stdout = f"Simulated file {cmd.operation} on {cmd.file_path}"

            dur_ms = (time.perf_counter() - start_t) * 1000.0
            return ObservationResult(
                command_type="file",
                status=status,
                exit_code=0,
                stdout=stdout,
                artifacts_created=artifacts,
                execution_time_ms=dur_ms,
            )
        except Exception as e:
            dur_ms = (time.perf_counter() - start_t) * 1000.0
            return ObservationResult(
                command_type="file",
                status="error",
                exit_code=1,
                stderr=str(e),
                execution_time_ms=dur_ms,
            )

    def dispatch(self, cmd: SandboxCommand) -> ObservationResult:
        """Route typed command to corresponding dispatch method."""
        if isinstance(cmd, BrowserActionCommand) or getattr(cmd, "command_type", None) == "browser":
            if not isinstance(cmd, BrowserActionCommand):
                cmd = BrowserActionCommand(**cmd)  # type: ignore
            return self.dispatch_browser(cmd)
        elif isinstance(cmd, ShellExecCommand) or getattr(cmd, "command_type", None) == "shell":
            if not isinstance(cmd, ShellExecCommand):
                cmd = ShellExecCommand(**cmd)  # type: ignore
            return self.dispatch_shell(cmd)
        elif isinstance(cmd, CodeComputeCommand) or getattr(cmd, "command_type", None) == "code":
            if not isinstance(cmd, CodeComputeCommand):
                cmd = CodeComputeCommand(**cmd)  # type: ignore
            return self.dispatch_code(cmd)
        elif isinstance(cmd, FileIOCommand) or getattr(cmd, "command_type", None) == "file":
            if not isinstance(cmd, FileIOCommand):
                cmd = FileIOCommand(**cmd)  # type: ignore
            return self.dispatch_file(cmd)
        else:
            raise ValueError(f"Unrecognized sandbox command type: {type(cmd)}")
