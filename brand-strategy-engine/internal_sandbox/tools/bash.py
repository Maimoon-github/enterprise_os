"""Sandboxed bash execution tool for internal sandbox operations."""

import asyncio
import os
from typing import Any, Dict, Literal, Optional

from .base import BaseAnthropicTool, BaseTool, CLIResult, ToolError, ToolResult


class _BashSession:
    """Persistent asynchronous bash session."""

    _started: bool
    _process: Optional[asyncio.subprocess.Process]
    command: str = "/bin/bash"
    _output_delay: float = 0.2
    _timeout: float = 120.0
    _sentinel: str = "<<exit_sentinel>>"

    def __init__(self):
        self._started = False
        self._process = None
        self._timed_out = False

    async def start(self) -> None:
        if self._started:
            return
        self._process = await asyncio.create_subprocess_shell(
            self.command,
            preexec_fn=os.setsid,
            shell=True,
            bufsize=0,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._started = True

    def stop(self) -> None:
        if not self._started or not self._process:
            return
        if self._process.returncode is None:
            self._process.terminate()
        self._started = False

    async def run(self, command: str) -> CLIResult:
        if not self._started or not self._process or not self._process.stdin:
            await self.start()
        assert self._process and self._process.stdin

        if self._process.returncode is not None:
            return CLIResult(
                system="tool must be restarted",
                error=f"bash has exited with returncode {self._process.returncode}",
            )
        if self._timed_out:
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted"
            )

        cmd_payload = f"{command}; echo '{self._sentinel}'\n"
        self._process.stdin.write(cmd_payload.encode())
        await self._process.stdin.drain()

        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)
                    assert self._process.stdout
                    buffer = getattr(self._process.stdout, "_buffer", bytearray())
                    output = buffer.decode(errors="replace")
                    if self._sentinel in output:
                        output = output[: output.index(self._sentinel)]
                        break
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(f"timed out: bash has not returned in {self._timeout} seconds and must be restarted")

        error = ""
        if self._process.stderr:
            err_buffer = getattr(self._process.stderr, "_buffer", bytearray())
            error = err_buffer.decode(errors="replace")

        # Clear stream buffers
        out_buf = getattr(self._process.stdout, "_buffer", None)
        if out_buf is not None and hasattr(out_buf, "clear"):
            out_buf.clear()
        err_buf = getattr(self._process.stderr, "_buffer", None)
        if err_buf is not None and hasattr(err_buf, "clear"):
            err_buf.clear()

        return CLIResult(output=output.strip(), error=error.strip())


class BashTool(BaseTool):
    """Execution bridge for sandboxed shell commands."""

    name: str = "bash"

    def __init__(self):
        self._session: Optional[_BashSession] = None

    def to_params(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": "Execute sandboxed bash command within the internal sandbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command line to execute",
                    },
                    "restart": {
                        "type": "boolean",
                        "description": "Whether to restart the bash session",
                    },
                },
                "required": ["command"],
            },
        }

    async def __call__(
        self, command: Optional[str] = None, restart: bool = False, **kwargs
    ) -> ToolResult:
        if restart:
            if self._session:
                self._session.stop()
            self._session = _BashSession()
            await self._session.start()
            return ToolResult(system="tool has been restarted.")

        if self._session is None:
            self._session = _BashSession()
            await self._session.start()

        if command is not None:
            return await self._session.run(command)

        raise ToolError("no command provided.")


class BashTool20250124(BashTool, BaseAnthropicTool):
    api_type: Literal["bash_20250124"] = "bash_20250124"
    name: Literal["bash"] = "bash"


class BashTool20241022(BashTool20250124):
    api_type: Literal["bash_20250124"] = "bash_20250124"
