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

"""Shared SSRF guards for the crawler / sitemap fetchers."""

import ipaddress
import socket
from contextlib import contextmanager
from typing import Optional, Union
from urllib.parse import urljoin, urlparse

from app.core.logger import get_logger

logger = get_logger(__name__)

# Match httpx's default so the manual (SSRF-checked) redirect following doesn't
# reject legitimate sites with longer redirect chains.
MAX_REDIRECTS = 20


class BlockedHostError(Exception):
    """Raised when a fetch target resolves to a private/internal address."""


IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

# NAT64 well-known prefix: 64:ff9b::a9fe:a9fe reaches 169.254.169.254
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
# Deprecated IPv4-compatible IPv6 (::a.b.c.d): ::7f00:1 is 127.0.0.1
_IPV4_COMPATIBLE = ipaddress.ip_network("::/96")


def is_public_ip(ip: IPAddress) -> bool:
    """True only for an address on the public internet.

    An IPv6 address that carries an IPv4 one (mapped, NAT64, 6to4, Teredo,
    IPv4-compatible) is judged as that IPv4 address. Then it must be global —
    which also excludes carrier-grade NAT (100.64/10) and documentation
    ranges — and none of the classic internal kinds.
    """
    ip = _embedded_ipv4(ip) or ip
    return ip.is_global and not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified
        or (ip.version == 6 and ip.is_site_local)  # deprecated fec0::/10
    )


def _embedded_ipv4(ip: IPAddress) -> Optional[ipaddress.IPv4Address]:
    if ip.version != 6:
        return None
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip.teredo is not None:
        return ip.teredo[1]  # the client's address
    if ip in _NAT64 or (ip in _IPV4_COMPATIBLE and int(ip) > 1):
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def is_blocked_host(url: str) -> bool:
    """True if the URL targets a literal private/loopback/link-local IP host.

    Catches the obvious internal targets given as an IP literal (cloud metadata
    ``169.254.169.254``, ``127.0.0.1``, RFC1918 ranges) plus ``localhost``.
    """
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        return not is_public_ip(ipaddress.ip_address(host))
    except ValueError:
        return False


def resolves_to_blocked_host(url: str) -> bool:
    """True if the URL's host is, or DNS-resolves to, an internal address.

    Extends :func:`is_blocked_host` by resolving hostnames — this closes the
    "attacker domain with an A record pointing at 169.254.169.254 / an RFC1918
    IP" SSRF vector. Hosts that can't be resolved are not blocked here (the
    request will simply fail to connect).
    """
    if is_blocked_host(url):
        return True
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError, ValueError, OSError):
        return False
    for info in infos:
        addr = info[4][0]
        try:
            if not is_public_ip(ipaddress.ip_address(addr)):
                return True
        except ValueError:
            continue
    return False


def guard_url(url: str) -> None:
    """Raise BlockedHostError if the URL targets an internal address."""
    if resolves_to_blocked_host(url):
        raise BlockedHostError(f"Refusing to fetch internal/blocked host: {url}")


def _redirect_target(resp) -> Optional[str]:
    """The absolute URL a redirect response points at, or None when ``resp``
    is final (not a redirect, or a redirect with no Location)."""
    if not resp.is_redirect:
        return None
    location = resp.headers.get("location")
    return urljoin(str(resp.url), location) if location else None


def safe_get(client, url: str, *, max_redirects: int = MAX_REDIRECTS, **kwargs):
    """httpx GET that follows redirects manually, re-validating each hop's host.

    Prevents the "public URL 302-redirects to an internal IP" SSRF: every hop
    (including the initial URL) is checked with :func:`guard_url` before it is
    fetched. Returns the final non-redirect response; the caller handles status.
    """
    current = url
    for _ in range(max_redirects + 1):
        guard_url(current)
        resp = client.get(current, follow_redirects=False, **kwargs)
        target = _redirect_target(resp)
        if target is None:
            return resp
        current = target
    raise BlockedHostError(f"Too many redirects while fetching {url}")


@contextmanager
def safe_stream(client, url: str, *, max_redirects: int = MAX_REDIRECTS, **kwargs):
    """Streaming counterpart of :func:`safe_get`, for bodies too large to hold
    in memory. Yields the final non-redirect response, unread; every hop is
    checked with :func:`guard_url` before it is opened."""
    current = url
    for _ in range(max_redirects + 1):
        guard_url(current)
        with client.stream("GET", current, follow_redirects=False, **kwargs) as resp:
            target = _redirect_target(resp)
            if target is None:
                yield resp
                return
        current = target
    raise BlockedHostError(f"Too many redirects while fetching {url}")
