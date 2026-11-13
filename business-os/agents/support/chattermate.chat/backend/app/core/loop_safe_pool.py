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

import asyncio
import logging

from sqlalchemy import exc
from sqlalchemy.pool import QueuePool
from sqlalchemy.util import queue as sqla_queue

logger = logging.getLogger(__name__)


def _on_event_loop() -> bool:
    """True when called from the thread running an asyncio loop, not from a
    worker thread (anyio's threadpool, asyncio.to_thread)."""
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


class LoopSafeQueuePool(QueuePool):
    """A QueuePool that never makes the event loop wait for a connection.

    Socket handlers, async routes and agent tools run sync queries on the event
    loop. A checkout there that waits for a full pool blocks the loop, but the
    connections out are held by coroutines suspended at an await and by request
    teardowns that run on the loop: none of them can give theirs back until the
    wait times out, and every request stalls meanwhile.

    So on the loop, a full pool opens up to loop_overflow connections past its
    limit (closed again as they come back to a full pool), and beyond that a
    checkout fails at once. Checkouts from threads wait as usual: the loop keeps
    running while they do.
    """

    def __init__(self, creator, loop_overflow: int = 0, **kw):
        # A plain keyword (not keyword-only): create_engine forwards only the
        # pool arguments it finds that way
        super().__init__(creator, **kw)
        self.loop_overflow = loop_overflow

    def recreate(self) -> "LoopSafeQueuePool":
        pool = super().recreate()
        pool.loop_overflow = self.loop_overflow
        return pool

    def _do_get(self):
        if self._max_overflow == -1 or not _on_event_loop():
            return super()._do_get()
        # Mirrors QueuePool._do_get (SQLAlchemy 2.0) without its wait: recheck
        # this against the base class when upgrading SQLAlchemy
        try:
            return self._pool.get(False)
        except sqla_queue.Empty:
            pass
        with self._overflow_lock:
            if self._overflow >= self._max_overflow + self.loop_overflow:
                raise exc.TimeoutError(
                    "QueuePool limit of size %d overflow %d reached on the event "
                    "loop, which never waits for a connection"
                    % (self.size(), self.overflow()),
                    code="3o7r",
                )
            first_past_limit = self._overflow == self._max_overflow
            self._overflow += 1
        if first_past_limit:
            logger.warning(
                "Connection pool full: opening up to %d more for the event loop (%s)",
                self.loop_overflow, self.status())
        try:
            return self._create_connection()
        except BaseException:
            self._dec_overflow()
            raise
