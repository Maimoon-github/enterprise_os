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

Signup domain DNS check: answers true/false, and "can't tell" (None) on a
timeout or a non-hostname - only a definite false should warn.
"""

import asyncio
import socket
import time

import pytest

from app.utils import domain_check
from app.utils.domain_check import (
    LOCALHOST_DOMAIN_MESSAGE,
    WEBSITE_INVALID_MESSAGE,
    WEBSITE_REQUIRED_MESSAGE,
    InvalidWebsite,
    bare_host,
    domain_resolves,
    validate_org_website,
    website_update,
)


@pytest.mark.parametrize("given,expected", [
    ("teeckbox.com", "teeckbox.com"), ("https://WWW.Teeckbox.com/pricing", "www.teeckbox.com"),
    ("  rex.com ", "rex.com"), ("", ""),
])
def test_bare_host(given, expected):
    assert bare_host(given) == expected


@pytest.fixture(autouse=True)
def empty_cache():
    domain_check._cache.clear()


def fake_dns(monkeypatch, known=(), slow=False, errno=socket.EAI_NONAME):
    def getaddrinfo(host, port, type=None):
        if slow:
            time.sleep(0.3)
        if host in known:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 0))]
        raise socket.gaierror(errno, "Name or service not known")
    monkeypatch.setattr(domain_check.socket, "getaddrinfo", getaddrinfo)


def test_resolving_domain(monkeypatch):
    fake_dns(monkeypatch, known={"teeckbox.com"})
    assert asyncio.run(domain_resolves("teeckbox.com")) is True


def test_www_only_domain_counts(monkeypatch):
    fake_dns(monkeypatch, known={"www.teeckbox.com"})
    assert asyncio.run(domain_resolves("https://teeckbox.com")) is True


def test_unknown_domain(monkeypatch):
    fake_dns(monkeypatch)
    assert asyncio.run(domain_resolves("erfanpv.com")) is False


def test_timeout_is_unknown(monkeypatch):
    fake_dns(monkeypatch, slow=True)
    monkeypatch.setattr(domain_check, "LOOKUP_TIMEOUT_SECONDS", 0.01)
    assert asyncio.run(domain_resolves("slow.example")) is None


@pytest.mark.parametrize("value", ["", "localhost", "not a domain"])
def test_non_hostnames_are_unknown(monkeypatch, value):
    fake_dns(monkeypatch)
    assert asyncio.run(domain_resolves(value)) is None


def test_temporary_failure_is_unknown(monkeypatch):
    """EAI_AGAIN means the resolver had trouble, not that the site is gone."""
    fake_dns(monkeypatch, errno=socket.EAI_AGAIN)
    assert asyncio.run(domain_resolves("teeckbox.com")) is None


def test_full_pool_answers_unknown_without_queueing(monkeypatch):
    fake_dns(monkeypatch, known={"teeckbox.com"})
    for _ in range(domain_check.MAX_LOOKUPS):
        domain_check._slots.acquire()
    try:
        assert asyncio.run(domain_resolves("teeckbox.com")) is None
    finally:
        for _ in range(domain_check.MAX_LOOKUPS):
            domain_check._slots.release()
    assert "teeckbox.com" not in domain_check._cache  # "can't tell" isn't remembered


def test_answers_are_cached(monkeypatch):
    lookups = []
    fake_dns(monkeypatch, known={"teeckbox.com"})
    real = domain_check._resolves

    async def counting(host):
        lookups.append(host)
        return await real(host)
    monkeypatch.setattr(domain_check, "_resolves", counting)
    asyncio.run(domain_resolves("teeckbox.com"))
    asyncio.run(domain_resolves("https://teeckbox.com/"))
    assert len(lookups) == 2  # bare + www, once


def test_one_overall_time_budget(monkeypatch):
    fake_dns(monkeypatch, slow=True)
    monkeypatch.setattr(domain_check, "LOOKUP_TIMEOUT_SECONDS", 0.05)
    started = asyncio.run(_timed(domain_resolves("slow.example")))
    assert started < 0.09  # not 2 x 0.05


async def _timed(coro):
    start = time.monotonic()
    await coro
    return time.monotonic() - start


def test_slots_come_back_after_timeouts(monkeypatch):
    fake_dns(monkeypatch, slow=True)
    monkeypatch.setattr(domain_check, "LOOKUP_TIMEOUT_SECONDS", 0.01)
    for _ in range(domain_check.MAX_LOOKUPS):
        asyncio.run(domain_resolves(f"slow{_}.example"))
    time.sleep(0.5)  # the abandoned lookups finish
    fake_dns(monkeypatch, known={"teeckbox.com"})
    monkeypatch.setattr(domain_check, "LOOKUP_TIMEOUT_SECONDS", 1.0)
    assert asyncio.run(domain_resolves("teeckbox.com")) is True


# ---- organization websites ----------------------------------------------------

@pytest.mark.parametrize("typed, stored", [
    ("acme.com", "acme.com"),
    ("  https://WWW.Acme.com/pricing?plan=pro  ", "www.acme.com"),
    ("shop.acme.co.uk:8443", "shop.acme.co.uk"),
    ("acme.com.", "acme.com"),
    ("my.cool-site.com", "my.cool-site.com"),
    ("bücher.de", "xn--bcher-kva.de"),  # as browsers send it in an Origin
    ("xn--bcher-kva.de", "xn--bcher-kva.de"),
    ("203.0.113.7", "203.0.113.7"),
    ("192.168.1.5", "192.168.1.5"),  # a self-hosted intranet site
])
def test_a_website_is_stored_as_its_host(typed, stored):
    assert validate_org_website(typed) == stored


@pytest.mark.parametrize("typed", [None, "", "   ", 42])
def test_a_website_is_required(typed):
    with pytest.raises(InvalidWebsite) as refused:
        validate_org_website(typed)
    assert str(refused.value) == WEBSITE_REQUIRED_MESSAGE


@pytest.mark.parametrize("typed", [
    "a]b.com", "[x", "intranet", "acme .com", "acme.com<script>x", 'a"b.com', ".com", "a..b.com",
    "-acme.com", "acme-.com", "acme_shop.com", "acme.123", "10.1",
    "a" * 64 + ".com",  # one label is at most 63
    ".".join(["abcdefghi"] * 10) + ".com",  # longer than the column
    ".".join(["日本語のウェブサイト名前店舗"] * 3) + ".jp",  # 47 typed, 134 as punycode
    "169.254.169.254", "224.0.0.1", "240.0.0.1", "[2001:db8::1]",
])
def test_what_no_public_website_could_be_is_refused(typed):
    with pytest.raises(InvalidWebsite) as refused:
        validate_org_website(typed)
    assert str(refused.value) == WEBSITE_INVALID_MESSAGE


@pytest.mark.parametrize("typed", [
    "localhost", "localhost:3000", "www.localhost", "app.localhost", "http://LocalHost:5173/x",
    "127.0.0.1", "127.0.0.2", "0.0.0.0", "::1", "[::1]:8000", "http://[::1]/",
])
def test_every_form_of_localhost_gets_its_own_message(typed):
    # www.localhost too: CORS admits a website with and without www.
    with pytest.raises(InvalidWebsite) as refused:
        validate_org_website(typed)
    assert str(refused.value) == LOCALHOST_DOMAIN_MESSAGE


@pytest.mark.parametrize("typed", ["localhost.example.com", "mylocalhost.com"])
def test_lookalikes_of_localhost_are_websites(typed):
    assert validate_org_website(typed) == typed


@pytest.mark.parametrize("typed", ["acme.com", " ACME.com ", "Acme.Com"])
def test_an_unchanged_website_is_left_as_it_is(typed):
    assert website_update(typed, "acme.com") is None


def test_an_unchanged_older_value_never_blocks_saving():
    # stored before websites were checked
    assert website_update("https://Acme.com/x", "https://acme.com/x") is None


def test_a_changed_website_is_checked_and_stored_as_its_host():
    assert website_update("https://New.example/x", "acme.com") == "new.example"
    with pytest.raises(InvalidWebsite):
        website_update("localhost", "acme.com")
    with pytest.raises(InvalidWebsite):
        website_update("", "acme.com")


def test_a_first_website_is_checked():
    assert website_update("acme.com", None) == "acme.com"
