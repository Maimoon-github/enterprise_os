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
import threading
import time
from unittest.mock import MagicMock

import pytest
from sqlalchemy import exc
from sqlalchemy.pool import QueuePool

from app.core.loop_safe_pool import LoopSafeQueuePool

# Waits are measured with time.monotonic, SQLAlchemy's queue with time.time
CLOCK_SLACK = 0.9


def make_pool(pool_class=LoopSafeQueuePool, *, pool_size=1, max_overflow=0, timeout=5.0, **kw):
    creator = MagicMock(side_effect=lambda: MagicMock(name="dbapi connection"))
    if pool_class is LoopSafeQueuePool:
        kw.setdefault("loop_overflow", 10)
    pool = pool_class(creator, pool_size=pool_size, max_overflow=max_overflow, timeout=timeout, **kw)
    return pool, creator


def on_loop(fn):
    async def run():
        return fn()
    return asyncio.run(run())


async def hold_across_an_await(pool, seconds):
    # A handler that took a connection and is now awaiting an emit or a service
    conn = pool.connect()
    await asyncio.sleep(seconds)
    conn.close()


async def check_out_while_the_pool_is_full(pool):
    await asyncio.sleep(0)  # let the holder take the only connection first
    conn = pool.connect()
    conn.close()


def run_the_freeze(pool):
    async def both():
        await asyncio.gather(hold_across_an_await(pool, 0.05), check_out_while_the_pool_is_full(pool))
    started = time.monotonic()
    asyncio.run(both())
    return time.monotonic() - started


def test_a_plain_pool_freezes_the_loop_until_it_times_out():
    """The bug: the holder can't give its connection back while the loop waits."""
    pool, _ = make_pool(QueuePool, timeout=0.3)

    started = time.monotonic()
    with pytest.raises(exc.TimeoutError):
        run_the_freeze(pool)

    assert time.monotonic() - started >= 0.3 * CLOCK_SLACK


def test_a_connection_held_across_an_await_no_longer_freezes_the_loop():
    pool, _ = make_pool(timeout=5.0)

    elapsed = run_the_freeze(pool)

    assert elapsed < 1.0
    assert pool.checkedout() == 0


def test_on_the_loop_an_idle_connection_is_reused():
    pool, creator = make_pool()

    def twice():
        pool.connect().close()
        pool.connect().close()
    on_loop(twice)

    assert creator.call_count == 1


def test_on_the_loop_a_full_pool_opens_one_more_instead_of_waiting(caplog):
    pool, creator = make_pool(timeout=5.0)
    held = pool.connect()

    started = time.monotonic()
    with caplog.at_level(logging.WARNING, logger="app.core.loop_safe_pool"):
        extra = on_loop(pool.connect)

    assert time.monotonic() - started < 1.0
    assert creator.call_count == 2
    assert pool.checkedout() == 2
    assert "Connection pool full" in caplog.text
    extra.close()
    held.close()


def test_the_warning_is_logged_once_per_crossing_not_per_connection(caplog):
    pool, _ = make_pool()
    held = [pool.connect()]

    with caplog.at_level(logging.WARNING, logger="app.core.loop_safe_pool"):
        held += [on_loop(pool.connect) for _ in range(3)]

    assert caplog.text.count("Connection pool full") == 1
    for conn in held:
        conn.close()


def test_within_its_own_overflow_the_loop_opens_connections_without_a_warning(caplog):
    pool, creator = make_pool(max_overflow=1)
    held = pool.connect()

    with caplog.at_level(logging.WARNING, logger="app.core.loop_safe_pool"):
        extra = on_loop(pool.connect)

    assert creator.call_count == 2
    assert "Connection pool full" not in caplog.text
    extra.close()
    held.close()


def test_past_its_headroom_the_loop_fails_at_once_rather_than_waiting():
    pool, _ = make_pool(timeout=5.0, loop_overflow=1)
    held = [pool.connect(), on_loop(pool.connect)]

    started = time.monotonic()
    with pytest.raises(exc.TimeoutError, match="event loop") as refused:
        on_loop(pool.connect)

    assert time.monotonic() - started < 1.0
    assert refused.value.code == "3o7r"
    for conn in held:
        conn.close()


def test_connections_opened_past_the_limit_close_as_they_come_back():
    pool, _ = make_pool(pool_size=1, max_overflow=0)
    held = pool.connect()
    overflow_before = pool.overflow()
    extra = on_loop(pool.connect)
    dbapi_connections = [held.dbapi_connection, extra.dbapi_connection]

    extra.close()
    held.close()

    assert pool.checkedout() == 0
    assert pool.checkedin() == 1
    assert pool.overflow() == overflow_before
    # whichever came back to a full pool was closed, not kept
    assert sum(c.close.called for c in dbapi_connections) == 1


def test_a_failed_connect_on_the_loop_gives_its_place_back():
    pool, creator = make_pool()
    held = pool.connect()
    overflow_before = pool.overflow()
    creator.side_effect = OSError("database is down")

    with pytest.raises(OSError):
        on_loop(pool.connect)

    assert pool.overflow() == overflow_before
    held.close()


def test_a_thread_still_waits_and_times_out_as_before():
    pool, _ = make_pool(timeout=0.2)
    held = pool.connect()

    started = time.monotonic()
    with pytest.raises(exc.TimeoutError):
        pool.connect()

    assert time.monotonic() - started >= 0.2 * CLOCK_SLACK
    held.close()


def test_a_thread_never_gets_the_loops_headroom():
    pool, _ = make_pool(timeout=0.2)
    held = [pool.connect(), on_loop(pool.connect)]

    with pytest.raises(exc.TimeoutError):
        pool.connect()
    for conn in held:
        conn.close()


def test_work_moved_off_the_loop_into_a_thread_waits_as_before():
    pool, _ = make_pool(timeout=0.2)
    held = pool.connect()

    async def from_a_thread():
        return await asyncio.to_thread(pool.connect)

    with pytest.raises(exc.TimeoutError):
        asyncio.run(from_a_thread())
    held.close()


def test_an_unlimited_pool_is_left_alone():
    pool, creator = make_pool(max_overflow=-1)
    held = pool.connect()

    extra = on_loop(pool.connect)

    assert creator.call_count == 2
    extra.close()
    held.close()


def test_without_headroom_the_loop_fails_at_once_on_a_full_pool():
    pool, _ = make_pool(loop_overflow=0)
    held = pool.connect()

    with pytest.raises(exc.TimeoutError):
        on_loop(pool.connect)
    held.close()


def test_the_count_stays_right_with_threads_and_the_loop_at_once():
    pool, _ = make_pool(pool_size=2, max_overflow=2, timeout=5.0, loop_overflow=4)
    overflow_at_rest = pool.overflow()

    def thread_work():
        for _ in range(50):
            pool.connect().close()

    async def loop_work():
        for _ in range(50):
            conn = pool.connect()
            await asyncio.sleep(0)
            conn.close()

    threads = [threading.Thread(target=thread_work) for _ in range(4)]
    for thread in threads:
        thread.start()
    asyncio.run(loop_work())
    for thread in threads:
        thread.join()

    assert pool.checkedout() == 0
    assert pool.overflow() <= overflow_at_rest + pool.size()
    assert pool.checkedin() <= pool.size()


def test_its_headroom_survives_a_recreate():
    pool, _ = make_pool(loop_overflow=3)

    assert pool.recreate().loop_overflow == 3
