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

Retry timing for queued work that calls other services (CRM pushes,
webhooks to external apps).
"""

import random
from typing import Optional


def next_attempt_delay(attempts: int, *, base_seconds: float, max_seconds: float,
                       jitter_seconds: float, retry_after_seconds: Optional[float] = None) -> float:
    """Seconds to wait before attempt number `attempts + 1`.

    Exponential (base · 2^attempts) capped at `max_seconds`; a longer
    Retry-After from the other service wins; random jitter on top so a burst
    of failures doesn't retry in lockstep.
    """
    backoff = min(base_seconds * (2 ** attempts), max_seconds)
    return max(retry_after_seconds or 0, backoff) + random.uniform(0, jitter_seconds)
