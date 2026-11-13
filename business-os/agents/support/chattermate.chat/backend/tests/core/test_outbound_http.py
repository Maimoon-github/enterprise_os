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

"""OUTBOUND_URL_POLICY=public_only at connect time: DNS rebinding and
redirects into the internal network are refused on the address actually
dialled; policy "any" installs nothing."""

import dataclasses
import inspect
import socket
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpcore
import httpx
import openai
import pytest
from agno.models.openai import OpenAIChat
from agno.tools.mcp import SSEClientParams, StreamableHTTPClientParams
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings
from app.core.outbound_http import (
    AsyncGuardedBackend,
    GuardedBackend,
    guarded_async_http_client,
    guarded_http_client,
)
from app.core.outbound_policy import OutboundTargetBlocked, check_outbound_target


def refused_by_policy(error: BaseException) -> bool:
    """The guard surfaces as a connect error; the policy refusal is in its causes."""
    while error is not None:
        if isinstance(error, OutboundTargetBlocked):
            return True
        error = error.__cause__ or error.__context__
    return False
from app.models.mcp_tool import MCPTransportType
from app.services import db_connector_service
from app.services.db_connector_service import DBConnectorConfig
from app.tools.mcp_manager import MCPToolsManager
from app.tools.mcp_outbound import guarded_mcp_http_client, remote_params_classes
from app.utils.agno_utils import PinnedOpenAIChat, create_model

PUBLIC_IP = "93.184.216.34"
OK = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}"


def _redirect(location: str) -> bytes:
    return f"HTTP/1.1 302 Found\r\nLocation: {location}\r\nContent-Length: 0\r\n\r\n".encode()


@pytest.fixture
def public_only(monkeypatch):
    monkeypatch.setattr(settings, "OUTBOUND_URL_POLICY", "public_only")


@pytest.fixture
def policy_any(monkeypatch):
    monkeypatch.setattr(settings, "OUTBOUND_URL_POLICY", "any")


@pytest.fixture
def dns(monkeypatch):
    """Fake resolver: ``dns[name] = [answer, ...]`` answers successive lookups
    in turn (the last one repeats), so a rebinding record is two answers."""
    answers = {}
    real = socket.getaddrinfo

    def getaddrinfo(host, port, *args, **kwargs):
        if host not in answers:
            return real(host, port, *args, **kwargs)
        queue = answers[host]
        address = queue.pop(0) if len(queue) > 1 else queue[0]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port or 0))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    return answers


class _Stream:
    def __init__(self, backend, response):
        self._backend, self._buffer = backend, [response]

    def _read(self):
        return self._buffer.pop(0) if self._buffer else b""

    def _start_tls(self, server_hostname):
        self._backend.sni.append(server_hostname)
        return self


class _SyncStream(_Stream, httpcore.NetworkStream):
    def read(self, max_bytes, timeout=None):
        return self._read()

    def write(self, buffer, timeout=None):
        self._backend.sent += buffer

    def close(self):
        pass

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        return self._start_tls(server_hostname)


class _AsyncStream(_Stream, httpcore.AsyncNetworkStream):
    async def read(self, max_bytes, timeout=None):
        return self._read()

    async def write(self, buffer, timeout=None):
        self._backend.sent += buffer

    async def aclose(self):
        pass

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        return self._start_tls(server_hostname)


class _Recording:
    """Stands in for the real socket layer under the guard: records what it
    was asked to dial and serves a canned response per dialled address."""

    def __init__(self, responses):
        self.responses, self.dialled, self.sni, self.sent = responses, [], [], b""


class RecordingBackend(_Recording, httpcore.NetworkBackend):
    def connect_tcp(self, host, port, **kwargs):
        self.dialled.append((host, port))
        return _SyncStream(self, self.responses[host])


class AsyncRecordingBackend(_Recording, httpcore.AsyncNetworkBackend):
    async def connect_tcp(self, host, port, **kwargs):
        self.dialled.append((host, port))
        return _AsyncStream(self, self.responses[host])


def _guard_of(client):
    return client._transport._pool._network_backend


def _sync_client(responses, **kwargs):
    client = guarded_http_client(follow_redirects=True, **kwargs)
    recorder = RecordingBackend(responses)
    _guard_of(client)._inner = recorder
    return client, recorder


def _async_client(responses):
    client = guarded_async_http_client(follow_redirects=True)
    recorder = AsyncRecordingBackend(responses)
    _guard_of(client)._inner = recorder
    return client, recorder


class TestGuard:
    def test_public_target_dials_the_vetted_ip_with_sni_and_host_unchanged(self, public_only, dns):
        dns["api.example.com"] = [PUBLIC_IP]
        client, recorder = _sync_client({PUBLIC_IP: OK})

        assert client.get("https://api.example.com/v1/models").status_code == 200
        assert recorder.dialled == [(PUBLIC_IP, 443)]
        assert recorder.sni == ["api.example.com"]
        assert b"\r\nHost: api.example.com\r\n" in recorder.sent

    def test_rebinding_after_the_check_is_refused(self, public_only, dns):
        dns["rebind.example.com"] = [PUBLIC_IP, "127.0.0.1"]
        check_outbound_target("https://rebind.example.com/v1", "Base URL")  # passes: public
        client, recorder = _sync_client({})

        with pytest.raises(httpx.ConnectError) as exc:
            client.get("https://rebind.example.com/v1/models")
        assert refused_by_policy(exc.value)
        assert recorder.dialled == []

    def test_any_internal_answer_refuses_the_host(self, public_only, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 443)),
        ])
        client, recorder = _sync_client({})
        with pytest.raises(httpx.ConnectError) as exc:
            client.get("https://mixed.example.com/")
        assert refused_by_policy(exc.value)
        assert recorder.dialled == []

    @pytest.mark.parametrize("location", [
        "http://127.0.0.1:8080/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://internal.example.com/",
    ])
    def test_redirect_to_an_internal_address_is_refused(self, public_only, dns, location):
        dns["api.example.com"] = [PUBLIC_IP]
        dns["internal.example.com"] = ["10.0.0.5"]
        client, recorder = _sync_client({PUBLIC_IP: _redirect(location)})

        with pytest.raises(httpx.ConnectError) as exc:
            client.get("https://api.example.com/v1/models")
        assert refused_by_policy(exc.value)
        assert recorder.dialled == [(PUBLIC_IP, 443)]

    def test_redirect_to_another_public_host_is_followed(self, public_only, dns):
        dns["api.example.com"] = [PUBLIC_IP]
        dns["cdn.example.net"] = ["93.184.216.35"]
        client, recorder = _sync_client({
            PUBLIC_IP: _redirect("https://cdn.example.net/x"), "93.184.216.35": OK,
        })
        assert client.get("https://api.example.com/").status_code == 200
        assert recorder.dialled == [(PUBLIC_IP, 443), ("93.184.216.35", 443)]
        assert recorder.sni == ["api.example.com", "cdn.example.net"]

    @pytest.mark.asyncio
    async def test_async_dials_the_vetted_ip(self, public_only, dns):
        dns["api.example.com"] = [PUBLIC_IP]
        client, recorder = _async_client({PUBLIC_IP: OK})

        assert (await client.get("https://api.example.com/v1")).status_code == 200
        assert recorder.dialled == [(PUBLIC_IP, 443)]
        assert recorder.sni == ["api.example.com"]

    @pytest.mark.asyncio
    async def test_async_redirect_to_metadata_is_refused(self, public_only, dns):
        dns["api.example.com"] = [PUBLIC_IP]
        client, recorder = _async_client({PUBLIC_IP: _redirect("http://169.254.169.254/")})

        with pytest.raises(httpx.ConnectError) as exc:
            await client.get("https://api.example.com/v1")
        assert refused_by_policy(exc.value)
        assert recorder.dialled == [(PUBLIC_IP, 443)]

    @pytest.mark.asyncio
    async def test_async_rebinding_is_refused(self, public_only, dns):
        dns["rebind.example.com"] = [PUBLIC_IP, "169.254.169.254"]
        check_outbound_target("https://rebind.example.com", "MCP server URL")
        client, recorder = _async_client({})

        with pytest.raises(httpx.ConnectError) as exc:
            await client.get("https://rebind.example.com/mcp")
        assert refused_by_policy(exc.value)
        assert recorder.dialled == []

    def test_unresolvable_host_is_a_connect_error(self, public_only, monkeypatch):
        def fail(*a, **k):
            raise socket.gaierror("nodename nor servname provided")
        monkeypatch.setattr(socket, "getaddrinfo", fail)
        client, _ = _sync_client({})
        with pytest.raises(httpx.ConnectError):
            client.get("https://nowhere.example.com/")


class TestPolicyAny:
    def test_no_guarded_clients(self, policy_any):
        assert guarded_http_client() is None
        assert guarded_async_http_client() is None

    def test_ai_model_is_plain_openai_chat(self, policy_any):
        model = create_model("OPENAI_COMPATIBLE", "key", "m", base_url="http://127.0.0.1:11434/v1")
        assert type(model) is OpenAIChat

    def test_mcp_params_are_agnos_own(self, policy_any):
        assert remote_params_classes() == (SSEClientParams, StreamableHTTPClientParams)

    def test_database_is_dialled_by_name(self, policy_any):
        config = _db_config(host="db.internal")
        with patch.object(db_connector_service, "_driver_connect") as driver:
            with db_connector_service._connection(config):
                pass
        driver.assert_called_once_with(config, "db.internal", 5432, None)


class TestAIModelWiring:
    def test_sync_and_async_clients_are_guarded(self, public_only, dns):
        dns["llm.example.com"] = [PUBLIC_IP]
        model = create_model("OPENAI_COMPATIBLE", "key", "m", base_url="https://llm.example.com/v1")

        assert isinstance(model, PinnedOpenAIChat)
        assert isinstance(_guard_of(model.get_client()._client), GuardedBackend)
        assert isinstance(_guard_of(model.get_async_client()._client), AsyncGuardedBackend)

    def test_sdk_redirect_to_metadata_is_refused(self, public_only, dns):
        dns["llm.example.com"] = [PUBLIC_IP]
        model = PinnedOpenAIChat(api_key="k", id="m", base_url="https://llm.example.com/v1", max_retries=0)
        client = model.get_client()
        recorder = RecordingBackend({PUBLIC_IP: _redirect("http://169.254.169.254/latest/")})
        _guard_of(client._client)._inner = recorder

        with pytest.raises(openai.APIConnectionError) as exc:
            client.models.list()
        assert refused_by_policy(exc.value)
        assert recorder.dialled == [(PUBLIC_IP, 443)]


class TestMCPWiring:
    def _config(self, transport):
        return SimpleNamespace(
            name="Remote", transport_type=transport, url="https://mcp.example.com/mcp",
            headers={"Authorization": "Bearer t"}, timeout=None, sse_read_timeout=None,
            terminate_on_close=True,
        )

    @pytest.mark.parametrize("transport", [MCPTransportType.HTTP, MCPTransportType.SSE])
    def test_remote_tool_carries_the_guarded_factory(self, public_only, dns, transport):
        dns["mcp.example.com"] = [PUBLIC_IP]
        tool = MCPToolsManager._build_remote_tool(self._config(transport))

        # agno hands these to the mcp SDK as keyword arguments.
        params = dataclasses.asdict(tool.server_params)
        assert params["httpx_client_factory"] is guarded_mcp_http_client

    def test_factory_builds_a_guarded_redirect_following_client(self, public_only):
        client = guarded_mcp_http_client(headers={"X": "1"}, timeout=httpx.Timeout(5))
        assert isinstance(_guard_of(client), AsyncGuardedBackend)
        assert client.follow_redirects is True
        assert client.headers["X"] == "1"

    @pytest.mark.parametrize("transport_client", [sse_client, streamablehttp_client])
    def test_installed_mcp_sdk_accepts_the_factory(self, transport_client):
        assert "httpx_client_factory" in inspect.signature(transport_client).parameters


def _db_config(**overrides):
    values = dict(
        id=None, organization_id=None, name="c", engine="postgresql",
        host="db.example.com", port=5432, database="d", username="u", password="p",
    )
    values.update(overrides)
    return DBConnectorConfig(**values)


class TestDatabasePinning:
    def test_postgres_dials_the_vetted_ip_and_keeps_the_name(self, public_only, dns, monkeypatch):
        dns["db.example.com"] = [PUBLIC_IP]
        connect = MagicMock()
        monkeypatch.setattr("psycopg.connect", connect)
        with db_connector_service._connection(_db_config()):
            pass
        kwargs = connect.call_args.kwargs
        assert kwargs["hostaddr"] == PUBLIC_IP
        assert kwargs["host"] == "db.example.com"

    def test_postgres_rebinding_is_refused(self, public_only, dns, monkeypatch):
        dns["db.example.com"] = [PUBLIC_IP, "127.0.0.1"]
        check_outbound_target("db.example.com", "Database host")  # the save-time check
        connect = MagicMock()
        monkeypatch.setattr("psycopg.connect", connect)
        with pytest.raises(OutboundTargetBlocked, match="Database host"):
            with db_connector_service._connection(_db_config()):
                pass
        connect.assert_not_called()

    def test_mysql_dials_the_vetted_ip(self, public_only, dns, monkeypatch):
        dns["db.example.com"] = [PUBLIC_IP]
        pymysql = MagicMock()
        monkeypatch.setitem(sys.modules, "pymysql", pymysql)
        with db_connector_service._connection(_db_config(engine="mysql", port=3306)):
            pass
        assert pymysql.connect.call_args.kwargs["host"] == PUBLIC_IP

    def test_ssh_bastion_is_dialled_by_vetted_ip(self, public_only, dns, monkeypatch):
        dns["bastion.example.com"] = [PUBLIC_IP]
        sshtunnel = MagicMock()
        sshtunnel.SSHTunnelForwarder.return_value.local_bind_port = 40000
        monkeypatch.setitem(sys.modules, "sshtunnel", sshtunnel)
        config = _db_config(
            host="10.0.0.5", ssh_enabled=True, ssh_host="bastion.example.com",
            ssh_username="u", ssh_password="pw",
        )
        with patch.object(db_connector_service, "_driver_connect") as driver:
            with db_connector_service._connection(config):
                pass
        assert sshtunnel.SSHTunnelForwarder.call_args.args[0] == (PUBLIC_IP, 22)
        # The database itself sits behind the bastion and is reached through it.
        assert sshtunnel.SSHTunnelForwarder.call_args.kwargs["remote_bind_address"] == ("10.0.0.5", 5432)
        driver.assert_called_once_with(config, "127.0.0.1", 40000)
