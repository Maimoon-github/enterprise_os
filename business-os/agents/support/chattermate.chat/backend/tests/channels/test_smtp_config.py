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

The SMTP connection settings every sender shares: an inbox's own credentials,
or the platform account (which local development points at Mailpit).
"""

import smtplib

import pytest

from app.channels import email as email_channel
from app.channels.email import inbox_smtp_config, open_smtp, platform_smtp_config
from app.core.config import settings


@pytest.fixture
def platform(monkeypatch):
    def configure(port, username="", password=""):
        monkeypatch.setattr(settings, "SMTP_SERVER", "smtp.example.com")
        monkeypatch.setattr(settings, "SMTP_PORT", port)
        monkeypatch.setattr(settings, "SMTP_USERNAME", username)
        monkeypatch.setattr(settings, "SMTP_PASSWORD", password)
    return configure


@pytest.mark.parametrize("port,use_ssl", [(587, False), (465, True), ("1025", False)])
def test_platform_config(platform, port, use_ssl):
    platform(port, "relay-user", "relay-pass")
    assert platform_smtp_config("noreply@example.com") == {
        "host": "smtp.example.com", "port": int(port), "username": "relay-user",
        "password": "relay-pass", "from_email": "noreply@example.com", "use_ssl": use_ssl,
    }


def test_inbox_config_defaults():
    cfg = inbox_smtp_config({"smtp_host": "smtp.acme.com"}, "support@acme.com")
    assert cfg["port"] == 587 and cfg["use_ssl"] is False
    assert cfg["from_email"] == "support@acme.com"


@pytest.mark.parametrize("port,explicit,expected", [(465, False, False), (587, True, True), (465, None, True)])
def test_inbox_explicit_ssl_wins(port, explicit, expected):
    creds = {"smtp_host": "smtp.acme.com", "smtp_port": port, "smtp_use_ssl": explicit}
    assert inbox_smtp_config(creds, "support@acme.com")["use_ssl"] is expected


class FakeSMTP:
    def __init__(self, host, port, timeout=None):
        self.calls = []

    def starttls(self):
        raise smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server.")

    def login(self, username, password):
        self.calls.append(("login", username))


def test_platform_without_username_skips_login(platform, monkeypatch):
    """Mailpit: no STARTTLS offered, no credentials configured."""
    platform(1025)
    monkeypatch.setattr(email_channel.smtplib, "SMTP", FakeSMTP)
    assert open_smtp(platform_smtp_config("noreply@example.com")).calls == []
