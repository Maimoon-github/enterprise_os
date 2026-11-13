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

import pytest
from unittest.mock import patch, MagicMock
import socketio

from app.core.socketio import configure_socketio, sio, socket_app, socket_origins


def test_configure_socketio_with_cors():
    """Configuring updates the origin policy's list, whatever shape it's given in"""
    with patch.object(socket_origins, 'origins', frozenset()):
        configure_socketio(cors_origins="https://example.com")
        assert socket_origins.origins == {"https://example.com"}
        assert sio.eio.cors_allowed_origins is socket_origins

        configure_socketio(cors_origins=["https://example1.com", "https://example2.com"])
        assert socket_origins.origins == {"https://example1.com", "https://example2.com"}

        configure_socketio(cors_origins={"https://example3.com"})
        assert socket_origins.origins == {"https://example3.com"}


REDIS_OPTIONS = {
    'retry_on_timeout': True,
    'health_check_interval': 30,
    'socket_timeout': 5.0,
    'socket_connect_timeout': 5.0,
}


@pytest.fixture
def restore_manager():
    """configure_socketio swaps the shared server's manager; put the real one back."""
    manager, initialized = sio.manager, sio.manager_initialized
    yield
    sio.manager, sio.manager_initialized = manager, initialized


@patch('app.core.socketio.settings')
def test_configure_socketio_with_redis_disabled(mock_settings, restore_manager):
    """Without Redis the server keeps its in-process manager."""
    mock_settings.REDIS_ENABLED = False
    manager = sio.manager

    configure_socketio()

    assert sio.manager is manager
    assert not isinstance(sio.manager, socketio.AsyncRedisManager)


@patch('app.core.socketio.settings')
@patch('socketio.AsyncRedisManager')
def test_configure_socketio_with_redis_enabled(mock_redis_manager, mock_settings, restore_manager):
    """With Redis, the Redis manager is the one the server emits through —
    not merely assigned to an attribute it never reads."""
    mock_settings.REDIS_ENABLED = True
    mock_settings.REDIS_URL = "redis://localhost:6379"
    mock_redis_instance = MagicMock()
    mock_redis_manager.return_value = mock_redis_instance

    configure_socketio()

    mock_redis_manager.assert_called_once_with(
        "redis://localhost:6379", write_only=False, channel='chattermate', redis_options=REDIS_OPTIONS,
    )
    assert sio.manager is mock_redis_instance
    mock_redis_instance.set_server.assert_called_once_with(sio)
    assert sio.manager_initialized is False


@patch('app.core.socketio.settings')
@patch('socketio.AsyncRedisManager')
def test_configure_socketio_with_elasticache(mock_redis_manager, mock_settings, restore_manager):
    """ElastiCache URLs are upgraded to TLS."""
    mock_settings.REDIS_ENABLED = True
    mock_settings.REDIS_URL = "redis://my-cluster.cache.amazonaws.com:6379"
    mock_redis_manager.return_value = MagicMock()

    configure_socketio()

    mock_redis_manager.assert_called_once_with(
        "rediss://my-cluster.cache.amazonaws.com:6379", write_only=False, channel='chattermate',
        redis_options={**REDIS_OPTIONS, 'ssl_cert_reqs': None},
    )


@patch('app.core.socketio.settings')
@patch('socketio.AsyncRedisManager')
def test_configure_socketio_with_redis_exception(mock_redis_manager, mock_settings, restore_manager):
    """A Redis manager that cannot be built leaves the in-process one serving."""
    mock_settings.REDIS_ENABLED = True
    mock_settings.REDIS_URL = "redis://localhost:6379"
    mock_redis_manager.side_effect = Exception("Redis connection error")
    manager = sio.manager

    configure_socketio()

    mock_redis_manager.assert_called_once()
    assert sio.manager is manager


def test_plain_redis_gets_no_tls_options():
    """redis-py rejects ssl_cert_reqs on redis://; with it the manager's listener
    fails in a loop and floods the log."""
    from app.core.socketio import redis_options
    assert 'ssl_cert_reqs' not in redis_options("redis://redis:6379/0")
    assert redis_options("rediss://cache.amazonaws.com:6379")['ssl_cert_reqs'] is None


class TestSocketOriginPolicy:
    """The framed widget's socket is same-origin; everything else needs the CORS list."""

    @pytest.fixture
    def policy(self, monkeypatch):
        from app.core.socketio import SocketOriginPolicy, settings
        monkeypatch.setattr(settings, "BACKEND_URL", "https://api.example.com")
        monkeypatch.setattr(settings, "WIDGET_FRAME_URL", "https://widget.example.com")
        return SocketOriginPolicy(["https://listed.example"])

    def test_a_listed_origin_is_allowed(self, policy):
        assert policy("https://listed.example", {"HTTP_HOST": "api.example.com"})

    def test_the_requests_own_host_is_allowed_whatever_the_scheme(self, policy):
        # behind TLS the ASGI scheme reads http, so only the host is compared
        assert policy("https://chat.selfhost.example", {"HTTP_HOST": "chat.selfhost.example"})
        assert policy("http://chat.selfhost.example", {"HTTP_HOST": "chat.selfhost.example"})

    def test_the_frame_host_cannot_open_a_socket_on_the_api_host(self, policy):
        # It would carry the dashboard's cookies, which the cookieless frame host exists to keep out
        assert not policy("https://widget.example.com", {"HTTP_HOST": "api.example.com"})
        assert policy("https://widget.example.com", {"HTTP_HOST": "widget.example.com"})

    def test_a_wildcard_list_still_allows_every_origin(self):
        from app.core.socketio import SocketOriginPolicy
        assert SocketOriginPolicy(["*"])("https://anyone.example", {"HTTP_HOST": "api.example.com"})

    def test_another_site_is_refused(self, policy):
        assert not policy("https://evil.example", {"HTTP_HOST": "api.example.com"})

    def test_a_forwarded_host_is_not_trusted(self, policy):
        assert not policy("https://evil.example", {"HTTP_HOST": "api.example.com", "HTTP_X_FORWARDED_HOST": "evil.example"})

    def test_a_port_must_match_too(self, policy):
        assert not policy("https://api.example.com:4443", {"HTTP_HOST": "other"})

    def test_no_origin_is_refused(self, policy):
        assert not policy(None, {})
        assert not policy("", {"HTTP_HOST": ""})

    def test_works_when_engineio_calls_without_environ(self, policy):
        assert policy("https://listed.example")
        assert not policy("https://evil.example")
        assert not policy("https://api.example.com")

    def test_engineio_uses_it_for_the_handshake(self, monkeypatch):
        environ = {"HTTP_ORIGIN": "https://evil.example", "HTTP_HOST": "api.example.com"}
        assert sio.eio._cors_allowed_origins(environ) == []

        environ = {"HTTP_ORIGIN": "https://api.example.com", "HTTP_HOST": "api.example.com"}
        assert sio.eio._cors_allowed_origins(environ) == ["https://api.example.com"]

    def test_own_host_still_allowed_after_a_cors_refresh(self, monkeypatch):
        from fastapi import FastAPI
        from app.core import cors
        monkeypatch.setattr(socket_origins, "origins", socket_origins.origins)

        cors.update_local_cors(FastAPI(), ["https://only.example"])

        assert sio.eio.cors_allowed_origins is socket_origins
        environ = {"HTTP_ORIGIN": "https://api.example.com", "HTTP_HOST": "api.example.com"}
        assert sio.eio._cors_allowed_origins(environ) == ["https://api.example.com"]
        assert sio.eio._cors_allowed_origins({"HTTP_ORIGIN": "https://only.example", "HTTP_HOST": "x"}) == ["https://only.example"]
