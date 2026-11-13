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

import pytest

import app.core.oauth_state as oauth_state


class FakeRedis:
    """Just the calls the state store makes, with real get-then-delete semantics."""

    def __init__(self):
        self.data = {}
        self.ttls = {}

    def set(self, key, value, ex=None):
        self.data[key] = value
        self.ttls[key] = ex

    def pipeline(self):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def get(self, key):
        self.ops.append(lambda: self.redis.data.get(key))

    def delete(self, key):
        self.ops.append(lambda: int(self.redis.data.pop(key, None) is not None))

    def execute(self):
        return [op() for op in self.ops]


@pytest.fixture
def no_redis(monkeypatch):
    monkeypatch.setattr(oauth_state, "get_redis", lambda: None)
    oauth_state._fallback.clear()


@pytest.fixture
def redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(oauth_state, "get_redis", lambda: fake)
    return fake


def test_redis_state_is_shared_and_single_use(redis):
    oauth_state.store_state("jira", "s1", "org-1")
    assert redis.ttls["jira_oauth_state:s1"] == oauth_state.STATE_TTL_SECONDS
    assert oauth_state.pop_state("jira", "s1") == "org-1"
    assert oauth_state.pop_state("jira", "s1") is None


def test_kinds_do_not_redeem_each_others_states(redis):
    oauth_state.store_state("slack", "s1", "org-1")
    assert oauth_state.pop_state("jira", "s1") is None
    assert oauth_state.pop_state("slack", "s1") == "org-1"


def test_fallback_is_single_use_and_per_kind(no_redis):
    oauth_state.store_state("crm", "s1", "org-1:hubspot")
    assert oauth_state.pop_state("jira", "s1") is None
    assert oauth_state.pop_state("crm", "s1") == "org-1:hubspot"
    assert oauth_state.pop_state("crm", "s1") is None


def test_fallback_state_expires(no_redis, monkeypatch):
    now = 1_000_000.0
    monkeypatch.setattr(oauth_state.time, "time", lambda: now)
    oauth_state.store_state("jira", "s1", "org-1")
    now += oauth_state.STATE_TTL_SECONDS + 1
    assert oauth_state.pop_state("jira", "s1") is None


def test_fallback_prunes_expired_states(no_redis, monkeypatch):
    now = 1_000_000.0
    monkeypatch.setattr(oauth_state.time, "time", lambda: now)
    oauth_state.store_state("jira", "abandoned", "org-1")
    now += oauth_state.STATE_TTL_SECONDS + 1
    oauth_state.store_state("jira", "fresh", "org-1")
    assert ("jira", "abandoned") not in oauth_state._fallback


def test_empty_state_is_never_valid(no_redis):
    assert oauth_state.pop_state("jira", "") is None
