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

"""httpx clients that only dial public addresses, for OUTBOUND_URL_POLICY.

Checking a URL before handing it to an HTTP client leaves two holes: the
client resolves the name again (a 0-TTL record can answer public to the check
and 127.0.0.1 to the client), and it follows redirects nobody checked. The
guard here sits in httpcore's network backend instead, so every TCP connect —
first request, each redirect hop, every reconnect — resolves the host once,
refuses it unless every address is public, and connects to that vetted
address. TLS SNI, certificate checks and the Host header still use the
hostname: httpcore passes it to start_tls and the request separately.

Under policy "any" the factories return None, so callers keep their clients
exactly as before.
"""

from typing import Any, Optional

import anyio
import httpcore
import httpx

from app.core.logger import get_logger
from app.core.outbound_policy import OutboundTargetBlocked, public_only, vetted_addresses

logger = get_logger(__name__)


class OutboundConnectRefused(httpcore.ConnectError):
    """The guard refused an address. Raised as a connect error so httpx, and
    every SDK built on it (whatever its version), reports an ordinary
    connection failure rather than letting an unknown exception escape; the
    policy's OutboundTargetBlocked is its __cause__."""


def _vet(host: str, port: int):
    try:
        return vetted_addresses(host, port, host)
    except OutboundTargetBlocked as e:
        logger.warning(f"Refused outbound connection to internal address via {host}")
        raise OutboundConnectRefused(str(e)) from e
    except OSError as e:  # DNS failure: report it the way httpx would
        raise httpcore.ConnectError(str(e)) from e


class GuardedBackend(httpcore.NetworkBackend):
    """Sync backend: connect only to vetted public addresses of the host."""

    def __init__(self, inner: httpcore.NetworkBackend):
        self._inner = inner

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        last_error: Optional[Exception] = None
        for address in _vet(host, port):
            try:
                return self._inner.connect_tcp(
                    address, port, timeout=timeout,
                    local_address=local_address, socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as e:
                last_error = e  # try the host's next address, like create_connection
        raise last_error

    def connect_unix_socket(self, *args, **kwargs):
        raise OutboundConnectRefused("Unix sockets are not allowed for outbound targets.")

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


class AsyncGuardedBackend(httpcore.AsyncNetworkBackend):
    """Async counterpart of GuardedBackend."""

    def __init__(self, inner: httpcore.AsyncNetworkBackend):
        self._inner = inner

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        last_error: Optional[Exception] = None
        for address in await anyio.to_thread.run_sync(_vet, host, port):
            try:
                return await self._inner.connect_tcp(
                    address, port, timeout=timeout,
                    local_address=local_address, socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as e:
                last_error = e
        raise last_error

    async def connect_unix_socket(self, *args, **kwargs):
        raise OutboundConnectRefused("Unix sockets are not allowed for outbound targets.")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def _guard(transport, backend_cls):
    """Swap the transport's connection-pool backend for the guarded one.
    httpx has no public hook for this; fail loudly rather than hand out an
    unguarded client if a library upgrade moves it."""
    pool = getattr(transport, "_pool", None)
    if not isinstance(pool, (httpcore.ConnectionPool, httpcore.AsyncConnectionPool)) \
            or not hasattr(pool, "_network_backend"):
        raise RuntimeError("Cannot install the outbound address guard on this httpx version")
    pool._network_backend = backend_cls(pool._network_backend)
    return transport


def guarded_http_client(**kwargs: Any) -> Optional[httpx.Client]:
    """A sync httpx.Client that dials only public addresses, or None when the
    policy is "any". ``kwargs`` go to httpx.Client (not the transport). An
    explicit transport also turns off env proxies, which would otherwise
    connect on the target's behalf unchecked."""
    if not public_only():
        return None
    return httpx.Client(transport=_guard(httpx.HTTPTransport(), GuardedBackend), **kwargs)


def guarded_async_http_client(**kwargs: Any) -> Optional[httpx.AsyncClient]:
    """Async counterpart of guarded_http_client."""
    if not public_only():
        return None
    return httpx.AsyncClient(
        transport=_guard(httpx.AsyncHTTPTransport(), AsyncGuardedBackend), **kwargs
    )
