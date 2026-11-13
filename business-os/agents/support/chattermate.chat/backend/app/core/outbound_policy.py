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

"""Opt-in refusal of user-configured outbound targets on internal networks.

AI base URLs, MCP server URLs and ticket databases are dialled by this server.
Self-hosters legitimately point them at their own network (Ollama on
localhost, a private MCP server or database), so the default policy "any"
allows everything. A shared, multi-tenant deployment sets
OUTBOUND_URL_POLICY=public_only so no tenant can use these features to reach
the server's own network or the cloud metadata endpoint.

Targets are checked when saved and again before connecting. The connection
itself is then pinned: the address that passed the check is the one dialled
(app.core.outbound_http for HTTP clients, pin_outbound_target for databases),
so a hostname that re-resolves elsewhere (DNS rebinding) or a redirect to an
internal host is refused at connect time too.
"""

import ipaddress
import socket
from typing import List, Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.knowledge.url_safety import is_public_ip, resolves_to_blocked_host

POLICY_ANY = "any"
POLICY_PUBLIC_ONLY = "public_only"


class OutboundTargetBlocked(ValueError):
    """A configured target is internal and the policy is public_only."""


def public_only() -> bool:
    return settings.OUTBOUND_URL_POLICY == POLICY_PUBLIC_ONLY


def _blocked(label: str) -> OutboundTargetBlocked:
    return OutboundTargetBlocked(
        f"{label} must be a public address. This server does not allow "
        "private, loopback, link-local or reserved network targets."
    )


def _as_url(target: str) -> str:
    """resolves_to_blocked_host parses a URL; give a bare host (a database or
    SSH host) the shape it expects. A scheme-less "localhost:11434/v1" would
    otherwise parse with no host at all and slip through."""
    if "://" in target:
        return target
    try:
        if ipaddress.ip_address(target).version == 6:
            return f"//[{target}]"
    except ValueError:
        pass
    return f"//{target}"


def check_outbound_target(target: Optional[str], label: str) -> None:
    """Raise OutboundTargetBlocked when the policy is public_only and
    ``target`` (a URL or a bare host) is, or resolves to, a private, loopback,
    link-local or reserved address. ``label`` names the field in the error."""
    if not public_only() or not target:
        return
    if resolves_to_blocked_host(_as_url(target.strip())):
        raise _blocked(label)


def vetted_addresses(host: str, port: Optional[int], label: str) -> List[str]:
    """Resolve ``host`` once and return its addresses for dialling, refusing
    it if ANY of them is not public. Unlike the save-time check this fails
    closed: an address that can't be parsed is refused, and a name that
    doesn't resolve raises socket.gaierror. Callers connect to the returned
    addresses directly, so nothing resolves the name a second time."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    if not addresses:
        raise socket.gaierror(f"{host} did not resolve to any address")
    for address in addresses:
        try:
            public = is_public_ip(ipaddress.ip_address(address))
        except ValueError:
            public = False
        if not public:
            raise _blocked(label)
    return addresses


def pin_outbound_target(host: Optional[str], label: str) -> Optional[str]:
    """For drivers that dial a host themselves (databases, SSH): under
    public_only, vet ``host`` and return the address to connect to instead of
    the name. None under policy "any", meaning connect as before."""
    if not public_only() or not host:
        return None
    return vetted_addresses(host.strip(), None, label)[0]


def require_public_target(target: Optional[str], label: str) -> None:
    """check_outbound_target for request handlers: a refusal is a 400."""
    try:
        check_outbound_target(target, label)
    except OutboundTargetBlocked as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
