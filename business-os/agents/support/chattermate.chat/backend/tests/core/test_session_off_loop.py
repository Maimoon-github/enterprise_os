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
import threading

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

from app import database
from app.database import SessionLocal, close_session, get_db, release_connection, session_off_loop


@pytest.fixture
def pool(tmp_path, monkeypatch):
    """The app's engine, swapped for a one-connection pool on a throwaway database."""
    engine = create_engine(f"sqlite:///{tmp_path / 'off_loop.db'}", poolclass=QueuePool, pool_size=1,
                           max_overflow=0, pool_timeout=5, connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE notes (body TEXT)"))
    monkeypatch.setattr(database, "engine", engine)
    yield engine.pool
    engine.dispose()


def test_the_session_keeps_its_one_connection_through_commits(pool):
    async def use_it():
        db = await session_off_loop()
        try:
            db.execute(text("INSERT INTO notes VALUES ('first')"))
            db.commit()  # as repositories do
            assert pool.checkedout() == 1
            db.execute(text("INSERT INTO notes VALUES ('second')"))
            db.commit()
            return db.execute(text("SELECT count(*) FROM notes")).scalar()
        finally:
            close_session(db)

    assert asyncio.run(use_it()) == 2
    assert pool.checkedout() == 0


def test_closing_rolls_back_what_was_not_committed(pool):
    async def abandon_it():
        db = await session_off_loop()
        db.execute(text("INSERT INTO notes VALUES ('never saved')"))
        close_session(db)

    asyncio.run(abandon_it())

    with database.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM notes")).scalar() == 0


def test_a_full_pool_makes_the_caller_wait_while_the_loop_keeps_running(pool):
    held = pool.connect()  # someone else has the only connection
    threading.Timer(0.3, held.close).start()
    ticks = 0

    async def meanwhile():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.01)

    async def wait_for_a_session():
        ticker = asyncio.create_task(meanwhile())
        db = await session_off_loop()
        ticker.cancel()
        close_session(db)

    asyncio.run(wait_for_a_session())

    assert ticks >= 10  # the loop served others the whole time
    assert pool.checkedout() == 0


def test_a_caller_cancelled_while_waiting_gives_the_connection_back(pool, monkeypatch):
    held = pool.connect()
    handed_back = []
    real_close_unwanted = database._close_unwanted

    def close_unwanted(checkout):
        handed_back.append(checkout)
        real_close_unwanted(checkout)

    monkeypatch.setattr(database, "_close_unwanted", close_unwanted)

    async def give_up_waiting():
        waiting = asyncio.create_task(session_off_loop())
        await asyncio.sleep(0.05)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        held.close()  # the thread now gets the connection, for nobody
        for _ in range(100):
            if handed_back and pool.checkedout() == 0:
                return
            await asyncio.sleep(0.02)

    asyncio.run(give_up_waiting())

    # closed on purpose as the thread got it, not left for the garbage collector
    assert len(handed_back) == 1
    assert pool.checkedout() == 0


def test_sessions_stop_short_of_the_pool_so_requests_find_room(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'cap.db'}", poolclass=QueuePool, pool_size=3,
                           max_overflow=0, pool_timeout=5, connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "OFF_LOOP_SESSIONS", 2)

    async def three_handlers():
        first, second = await session_off_loop(), await session_off_loop()
        third = asyncio.create_task(session_off_loop())
        await asyncio.sleep(0.2)
        # a connection is free, but it stays the requests'
        assert not third.done() and engine.pool.checkedout() == 2
        close_session(first)
        close_session(await asyncio.wait_for(third, 5))
        close_session(second)

    asyncio.run(three_handlers())

    assert engine.pool.checkedout() == 0
    engine.dispose()


def test_a_failed_checkout_gives_its_slot_back(pool, monkeypatch):
    monkeypatch.setattr(database, "OFF_LOOP_SESSIONS", 1)
    real_connect = database.engine.connect
    attempts = []

    def connect_once_failing():
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("database is down")
        return real_connect()

    monkeypatch.setattr(database.engine, "connect", connect_once_failing)

    async def fail_then_succeed():
        with pytest.raises(OSError):
            await session_off_loop()
        close_session(await asyncio.wait_for(session_off_loop(), 5))

    asyncio.run(fail_then_succeed())

    assert pool.checkedout() == 0


def test_releasing_before_a_slow_call_frees_the_connection_and_the_slot(pool, monkeypatch):
    monkeypatch.setattr(database, "OFF_LOOP_SESSIONS", 1)

    async def chat_turn():
        db = await session_off_loop()
        try:
            db.execute(text("INSERT INTO notes VALUES ('before the call')"))
            release_connection(db)
            # during the model call: nothing held, and another handler gets in
            assert pool.checkedout() == 0
            close_session(await asyncio.wait_for(session_off_loop(), 5))
            # after it, the session carries on with a fresh connection
            return db.execute(text("SELECT count(*) FROM notes")).scalar()
        finally:
            close_session(db)

    assert asyncio.run(chat_turn()) == 1
    assert pool.checkedout() == 0


def test_a_request_session_waits_off_the_loop_and_is_given_back(pool):
    async def request():
        dependency = get_db()
        db = await dependency.__anext__()
        assert pool.checkedout() == 1
        db.execute(text("SELECT 1"))
        with pytest.raises(StopAsyncIteration):
            await dependency.__anext__()

    asyncio.run(request())

    assert pool.checkedout() == 0


def test_close_session_closes_an_ordinary_session_too(pool):
    db = SessionLocal(bind=database.engine)
    db.execute(text("SELECT 1"))

    close_session(db)

    assert pool.checkedout() == 0
