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

from app.utils.backoff import next_attempt_delay

POLICY = {"base_seconds": 60, "max_seconds": 3600, "jitter_seconds": 0}


def test_exponential_then_capped():
    assert next_attempt_delay(1, **POLICY) == 120
    assert next_attempt_delay(3, **POLICY) == 480
    assert next_attempt_delay(10, **POLICY) == 3600


def test_a_longer_retry_after_wins():
    assert next_attempt_delay(1, retry_after_seconds=900, **POLICY) == 900
    assert next_attempt_delay(3, retry_after_seconds=5, **POLICY) == 480


def test_jitter_only_adds():
    delay = next_attempt_delay(1, base_seconds=60, max_seconds=3600, jitter_seconds=30)
    assert 120 <= delay <= 150
