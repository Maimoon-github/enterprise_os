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

from app.core.external_urls import external_base


def test_default_when_unset(monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_BASE", raising=False)
    assert external_base("TELEGRAM_API_BASE", "https://api.telegram.org") == "https://api.telegram.org"


def test_override_without_trailing_slash(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_BASE", "http://127.0.0.1:14020/telegram/")
    assert external_base("TELEGRAM_API_BASE", "https://api.telegram.org") == "http://127.0.0.1:14020/telegram"


def test_blank_override_falls_back(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_BASE", "")
    assert external_base("TELEGRAM_API_BASE", "https://api.telegram.org") == "https://api.telegram.org"
