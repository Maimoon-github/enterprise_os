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
import gc

from app.utils.keyed_lock import KeyedLock


def test_one_key_runs_one_at_a_time_and_other_keys_are_free():
    locks = KeyedLock()
    order = []

    async def work(key, name):
        async with locks(key):
            order.append(f"{name} in")
            await asyncio.sleep(0.01)
            order.append(f"{name} out")

    async def main():
        await asyncio.gather(work("a", "first"), work("a", "second"), work("b", "other"))

    asyncio.run(main())

    assert order.index("first out") < order.index("second in")
    assert order.index("other in") < order.index("first out")


def test_a_key_is_forgotten_once_nobody_holds_it():
    locks = KeyedLock()

    async def use_once():
        async with locks("session"):
            pass

    asyncio.run(use_once())
    gc.collect()

    assert "session" not in locks._locks
