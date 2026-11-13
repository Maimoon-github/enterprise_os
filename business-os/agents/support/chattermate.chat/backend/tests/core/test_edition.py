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

import sys

import pytest

from app.core import edition


@pytest.fixture
def clean_meta_path():
    saved = list(sys.meta_path)
    yield
    sys.meta_path[:] = saved


def _blockers():
    return [f for f in sys.meta_path if isinstance(f, edition._BlockEnterprise)]


def test_apply_without_flag_installs_nothing(monkeypatch, clean_meta_path):
    monkeypatch.delenv("NO_ENTERPRISE", raising=False)
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, edition._BlockEnterprise)]

    edition.apply()

    assert _blockers() == []


def test_apply_with_flag_blocks_enterprise_imports_once(monkeypatch, clean_meta_path):
    monkeypatch.setenv("NO_ENTERPRISE", "1")

    edition.apply()
    edition.apply()

    assert len(_blockers()) == 1
    with pytest.raises(ModuleNotFoundError):
        _blockers()[0].find_spec("app.enterprise.models")
    assert _blockers()[0].find_spec("app.models") is None
