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

# One-time OAuth `state` values for the install flows (Jira, CRMs, Slack).
#
# The provider sends the browser back to whichever backend worker it lands on, so
# the state lives in Redis when it is enabled. Without Redis (single-worker dev
# setups) an in-process dict stands in. Either way a state expires after
# STATE_TTL_SECONDS and can be redeemed once.

import time
from typing import Optional

from app.core.redis import get_redis

STATE_TTL_SECONDS = 60 * 10

# (kind, state) -> (value, expires_at)
_fallback: dict = {}


def _redis_key(kind: str, state: str) -> str:
    return f"{kind}_oauth_state:{state}"


def store_state(kind: str, state: str, value: str) -> None:
    """Remember `value` (usually the org id) for `state` until it is popped or expires."""
    redis_client = get_redis()
    if redis_client is not None:
        redis_client.set(_redis_key(kind, state), value, ex=STATE_TTL_SECONDS)
        return
    now = time.time()
    for key in [k for k, (_, expires_at) in _fallback.items() if expires_at < now]:
        _fallback.pop(key, None)
    _fallback[(kind, state)] = (value, now + STATE_TTL_SECONDS)


def pop_state(kind: str, state: str) -> Optional[str]:
    """The value stored for `state`, removed so it can't be replayed; None if unknown or expired."""
    if not state:
        return None
    redis_client = get_redis()
    if redis_client is not None:
        pipe = redis_client.pipeline()
        pipe.get(_redis_key(kind, state))
        pipe.delete(_redis_key(kind, state))
        value, _ = pipe.execute()
        return value or None
    entry = _fallback.pop((kind, state), None)
    return entry[0] if entry and entry[1] >= time.time() else None
