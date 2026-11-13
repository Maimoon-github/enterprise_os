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

"""Remote MCP connection params that honour OUTBOUND_URL_POLICY at connect
time. agno's MCPTools passes its params dataclass to the mcp SDK's
sse_client / streamablehttp_client as keyword arguments, so adding an
``httpx_client_factory`` field is how the SDK's httpx client (and the
redirects it follows) gets the address guard."""

from dataclasses import dataclass
from typing import Callable, Tuple, Type

from agno.tools.mcp import SSEClientParams, StreamableHTTPClientParams

from app.core.outbound_http import guarded_async_http_client
from app.core.outbound_policy import public_only


def guarded_mcp_http_client(headers=None, timeout=None, auth=None):
    """The mcp SDK's httpx_client_factory, dialling only vetted public
    addresses. Redirects stay on, as in the SDK's default factory."""
    return guarded_async_http_client(
        headers=headers, timeout=timeout, auth=auth, follow_redirects=True
    )


@dataclass
class PinnedSSEClientParams(SSEClientParams):
    httpx_client_factory: Callable = guarded_mcp_http_client


@dataclass
class PinnedStreamableHTTPClientParams(StreamableHTTPClientParams):
    httpx_client_factory: Callable = guarded_mcp_http_client


def remote_params_classes() -> Tuple[Type[SSEClientParams], Type[StreamableHTTPClientParams]]:
    """The (SSE, streamable-HTTP) params classes for the current policy;
    agno's own, untouched, under "any"."""
    if public_only():
        return PinnedSSEClientParams, PinnedStreamableHTTPClientParams
    return SSEClientParams, StreamableHTTPClientParams
