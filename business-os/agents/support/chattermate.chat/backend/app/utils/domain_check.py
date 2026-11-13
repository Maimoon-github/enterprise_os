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

An organization's website: the one check every surface stores it through, and
whether it resolves in DNS - for a soft warning, never a block: some people
sign up before their site is live.
"""

import asyncio
import ipaddress
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

LOOKUP_TIMEOUT_SECONDS = 2.0
# getaddrinfo blocks, and a thread can't be cancelled: a dead nameserver holds
# one until the system resolver gives up, long after our timeout. So lookups
# get a small pool of their own (never the event loop's shared one) and never
# queue: when every slot is busy the answer is "can't tell".
MAX_LOOKUPS = 4
_executor = ThreadPoolExecutor(max_workers=MAX_LOOKUPS, thread_name_prefix="domain-check")
_slots = threading.BoundedSemaphore(MAX_LOOKUPS)
# Only these mean "no such name"; anything else (EAI_AGAIN, a failing
# resolver) is a temporary failure and says nothing about the domain.
_NOT_FOUND = {socket.EAI_NONAME, getattr(socket, "EAI_NODATA", socket.EAI_NONAME)}
# The field re-checks on every pause in typing: remember definite answers
# for a while so that doesn't cost a lookup each time.
CACHE_SECONDS = 600
CACHE_LIMIT = 1000
_cache: Dict[str, Tuple[float, bool]] = {}


def bare_host(domain: str) -> str:
    """'https://Example.com/path' -> 'example.com'."""
    value = domain.strip()
    return (urlparse(value if "//" in value else f"//{value}").hostname or "").lower()


def site_host(domain: str) -> str:
    """An org's site as hostnames compare: 'https://WWW.Acme.com/' -> 'acme.com'.
    CORS admits this host and its www., however the domain was typed."""
    return bare_host(domain).removeprefix("www.")


LOCALHOST_DOMAIN_MESSAGE = "Localhost can't be used as your website. Use the site where you'll add the widget."
WEBSITE_REQUIRED_MESSAGE = "Your website is required"
WEBSITE_INVALID_MESSAGE = "Please enter your website, like yourwebsite.com"
WEBSITE_MAX_LENGTH = 100  # the organizations.domain column
# One DNS label: letters, digits and inner hyphens (punycode for the rest)
_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


class InvalidWebsite(ValueError):
    """An organization website that can't be stored; the message is for the person."""


def _typed_host(text: str) -> str:
    """The host in what was typed, a bare IPv6 address included."""
    try:
        host = bare_host(text)
    except ValueError:
        host = ""
    if not host:
        try:
            host = str(ipaddress.ip_address(text.strip("[]")))
        except ValueError:
            return ""
    return host.rstrip(".")


def _is_local(host: str) -> bool:
    """Whether a host is a developer's machine. Org websites still feed CORS for
    cached older loaders, which must never admit such a machine for everyone."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        name = host.removeprefix("www.")  # CORS admits a site with and without www.
        return name == "localhost" or name.endswith(".localhost")
    return address.is_loopback or address.is_unspecified


def _public_name(host: str) -> Optional[str]:
    """The host as browsers send it in an Origin (punycode), or None when it
    isn't a hostname a public website can have."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        usable = address.version == 4 and not (
            address.is_link_local or address.is_multicast or address.is_reserved)
        return host if usable else None
    try:
        name = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    labels = name.split(".")
    if len(labels) < 2 or labels[-1].isdigit() or not all(_LABEL.match(label) for label in labels):
        return None
    return name if len(name) <= WEBSITE_MAX_LENGTH else None


def validate_org_website(value: object) -> str:
    """An organization's website as stored: its host only, lowercase and in
    punycode ('https://WWW.Acme.com/pricing' -> 'www.acme.com'). Required, but
    not unique. Raises InvalidWebsite with a message a person can act on."""
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise InvalidWebsite(WEBSITE_REQUIRED_MESSAGE)
    host = _typed_host(text)
    if host and _is_local(host):
        raise InvalidWebsite(LOCALHOST_DOMAIN_MESSAGE)
    name = _public_name(host) if host else None
    if not name:
        raise InvalidWebsite(WEBSITE_INVALID_MESSAGE)
    return name


def website_update(new: object, current: Optional[str]) -> Optional[str]:
    """The website to store when someone edits it, or None to leave it be: an
    unchanged value (however it's cased or spaced) is kept as it is, so an older
    stored value never blocks saving other settings."""
    if isinstance(new, str) and current and new.strip().lower() == current.strip().lower():
        return None
    return validate_org_website(new)


def _lookup(host: str) -> Optional[bool]:
    try:
        socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return True
    except socket.gaierror as e:
        return False if e.errno in _NOT_FOUND else None


async def _resolves(host: str) -> Optional[bool]:
    if not _slots.acquire(blocking=False):
        return None
    try:
        future = _executor.submit(_lookup, host)
    except RuntimeError:  # pool shut down
        _slots.release()
        return None
    # Released when the lookup ends - or is cancelled before it ever ran,
    # which a release inside _lookup would miss.
    future.add_done_callback(lambda _: _slots.release())
    return await asyncio.wrap_future(future)


def _combine(answers) -> Optional[bool]:
    """Any address is enough; "doesn't exist" only when every name said so."""
    if any(answer is True for answer in answers):
        return True
    return False if answers and all(answer is False for answer in answers) else None


async def domain_resolves(domain: str) -> Optional[bool]:
    """True/False when DNS answered, None when it couldn't say in time (or the
    input isn't a hostname) - callers warn only on a definite False. Asks for
    the bare domain and www. together (some sites only publish www), within
    one overall time budget."""
    host = bare_host(domain)
    if not host or "." not in host:
        return None
    cached = _cache.get(host)
    if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]
    candidates = {host, f"www.{host.removeprefix('www.')}"}
    try:
        result = _combine(await asyncio.wait_for(
            asyncio.gather(*(_resolves(candidate) for candidate in candidates)), LOOKUP_TIMEOUT_SECONDS
        ))
    except asyncio.TimeoutError:
        result = None
    if result is not None:
        if len(_cache) >= CACHE_LIMIT:
            _cache.clear()
        _cache[host] = (time.monotonic(), result)
    return result
