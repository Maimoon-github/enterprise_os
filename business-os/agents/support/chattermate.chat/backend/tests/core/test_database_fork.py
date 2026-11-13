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

import os

import pytest

from app import database
from app.core.loop_safe_pool import LoopSafeQueuePool


@pytest.fixture
def app_sessions_use_the_test_database():
    """These tests are about the app's own engine: leave it in place."""


def test_a_child_starts_with_its_own_pool():
    parent_pool = database.engine.pool
    parent_threads = database._checkout_threads

    database._fresh_pool_after_fork()

    assert database.engine.pool is not parent_pool
    # still the pool that never makes the event loop wait, with its headroom
    assert isinstance(database.engine.pool, LoopSafeQueuePool)
    assert database.engine.pool.loop_overflow == parent_pool.loop_overflow > 0
    assert database._checkout_threads is not parent_threads


@pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork()")
def test_a_forked_worker_never_reuses_the_parents_pool():
    parent_pool_id = id(database.engine.pool)
    read_end, write_end = os.pipe()
    pid = os.fork()
    if pid == 0:  # the child: report whether it got a fresh pool, then leave at once
        os.close(read_end)
        os.write(write_end, b"fresh" if id(database.engine.pool) != parent_pool_id else b"shared")
        os._exit(0)
    os.close(write_end)
    answer = os.read(read_end, 16)
    os.close(read_end)
    os.waitpid(pid, 0)

    assert answer == b"fresh"
    assert id(database.engine.pool) == parent_pool_id
