"""Sandboxed bash execution tool for internal sandbox operations."""

import asyncio
import os
from typing import Any, Dict, Optional

from internal_sandbox.tools.base import BaseTool, CLIResult, ToolError, ToolResult


class _BashSession:
    """Persistent asynchronous bash session."""

    _started: bool
    _process: Optional[asyncio.subprocess.Process]
    command: str = "/bin/bash"
    _output_delay: float = 0.2
    _timeout: float = 60.0
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

        cmd_payload = f"{command}; echo '{self._sentinel}'\n"
        self._process.stdin.write(cmd_payload.encode())
        await self._process.stdin.drain()

        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)
                    assert self._process.stdout
                    # Access internal buffer safely
                    buffer = getattr(self._process.stdout, "_buffer", bytearray())
                    output = buffer.decode(errors="replace")
                    if self._sentinel in output:
                        output = output[: output.index(self._sentinel)]
                        break
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(f"Bash command timed out after {self._timeout}s: {command}")

        error = ""
        if self._process.stderr:
            err_buffer = getattr(self._process.stderr, "_buffer", bytearray())
            error = err_buffer.decode(errors="replace")

        # Clear stream buffers
        if hasattr(self._process.stdout, "_buffer"):
            self._process.stdout._buffer.clear()
        if hasattr(self._process.stderr, "_buffer"):
            self._process.stderr._buffer.clear()

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
                    "command": {"type": "string", "description": "The command string to execute"},
                    "restart": {"type": "boolean", "description": "Whether to restart the shell session"},
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
            return ToolResult(system="Bash session restarted.")

        if self._session is None:
            self._session = _BashSession()
            await self._session.start()

        if command:
            return await self._session.run(command)

        raise ToolError("No command provided to BashTool.")
