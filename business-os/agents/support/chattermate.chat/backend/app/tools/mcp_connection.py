"""
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# An MCP tool's session, opened, held and closed by one task of its own.
#
# The MCP transports run inside anyio cancel scopes that belong to the task that
# enters them. Entered from the request's own task, a refused streamable-HTTP
# connect surfaced as a CancelledError instead of the error, and the leaked
# scope cancelled the next connector in the same request too; closing from
# another task failed with "exit cancel scope in a different task". The owner
# task here enters and exits the tool's context itself, so a failure stays in it.

import asyncio
from typing import Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

CONNECTION_FAILED = "Could not connect to the server (refused, unreachable or not an MCP endpoint)"

# Strong references to owner tasks being torn down; without them the loop can
# garbage collect a task mid-flight.
_closing: set = set()


def _forget_outcome(task: asyncio.Task) -> None:
    """Read a finished owner task's exception so asyncio doesn't log it as never
    retrieved; whoever cared has already reported it."""
    if not task.cancelled():
        task.exception()


class HeldConnection:
    def __init__(self, tool):
        self.tool = tool
        self._opened = asyncio.Event()
        self._release = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    async def open(self, timeout: float) -> None:
        """Connect within ``timeout`` seconds. Raises TimeoutError, or what the
        connect raised (ConnectionError when the transport only cancelled)."""
        self._task = asyncio.create_task(self._hold())
        self._task.add_done_callback(_forget_outcome)
        opened = asyncio.create_task(self._opened.wait())
        try:
            await asyncio.wait({opened, self._task}, timeout=timeout,
                               return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            self._abandon()  # the request itself was cancelled
            raise
        finally:
            opened.cancel()
        if self._opened.is_set():
            return
        if not self._task.done():
            self._abandon()
            raise asyncio.TimeoutError()
        if self._task.cancelled():
            raise ConnectionError(CONNECTION_FAILED)
        raise self._task.exception()

    async def _hold(self) -> None:
        await self.tool.__aenter__()
        try:
            self._opened.set()
            await self._release.wait()
        finally:
            await self.tool.__aexit__(None, None, None)

    def _abandon(self) -> None:
        """Stop the owner without waiting: a STDIO server that never answered
        can leave its unwind blocked until the child process exits."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
            _closing.add(self._task)
            self._task.add_done_callback(_closing.discard)

    async def close(self, timeout: float) -> None:
        """Ask the owner task to exit the tool's context, waiting up to
        ``timeout`` seconds before abandoning it. Never raises."""
        if self._task is None or self._task.done():
            return
        self._release.set()
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout)
        except asyncio.TimeoutError:
            logger.debug("MCP tool did not close in time; abandoning it")
            self._abandon()
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                self._abandon()  # the caller itself is being cancelled
                raise
            # Otherwise the owner ended cancelled by its transport: it is closed.
        except Exception as e:
            logger.debug(f"MCP tool close raised (non-critical): {e}")

    def release(self) -> None:
        """Close without waiting."""
        self._release.set()
