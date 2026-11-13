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

from urllib.parse import urlparse

import socketio
from socketio import AsyncServer
from app.core.config import settings
from app.core.logger import get_logger
from app.core.cors import get_cors_origins

logger = get_logger(__name__)

# ElastiCache endpoints terminate TLS, so a redis:// URL pointing at one has to be
# upgraded to rediss://. Match the HOST: ".cache.amazonaws.com" anywhere in the
# string would also accept redis://evil.com/?x=.cache.amazonaws.com.
ELASTICACHE_HOST_SUFFIX = ".cache.amazonaws.com"


def needs_elasticache_tls(redis_url: str | None) -> bool:
    """True when this plaintext Redis URL points at an ElastiCache host."""
    if not redis_url or not redis_url.startswith("redis://"):
        return False
    return (urlparse(redis_url).hostname or "").endswith(ELASTICACHE_HOST_SUFFIX)

def _netloc(url: str) -> str:
    return urlparse(url).netloc.lower() if url else ""


class SocketOriginPolicy:
    """Which origins may open a Socket.IO connection.

    The CORS list, plus the host the request itself arrived on: the framed
    widget is served by this backend, so its socket is same-origin. engineio
    given a plain list doesn't allow same-origin by itself. Only the host is
    compared - uvicorn runs without proxy headers, so behind TLS the request's
    scheme reads http.

    Deliberately not "any of our hosts": a socket from the cookieless widget
    host to the API host would carry the dashboard's cookies, which is exactly
    what serving the frame elsewhere keeps out of the widget's reach.
    Installed once on the server; refreshes swap the list, never the policy.
    """

    def __init__(self, origins=()):
        self.origins = frozenset(origins)

    def update(self, origins) -> None:
        self.origins = frozenset(origins)

    def __call__(self, origin, environ=None) -> bool:
        if not origin:
            return False
        # engineio's own list handling treats "*" as any origin; keep that
        if "*" in self.origins or origin in self.origins:
            return True
        host = _netloc(origin)
        return bool(host) and host == (environ or {}).get("HTTP_HOST", "").lower()


socket_origins = SocketOriginPolicy(get_cors_origins())

# Initialize Socket.IO server with basic config. engine.io answers every
# allowed origin with credentials allowed; the cookie-authenticated /agent
# namespace refuses other sites itself (auth_utils.cookie_socket_allowed).
sio: AsyncServer = socketio.AsyncServer(
    async_mode='asgi',
    logger=True,
    engineio_logger=True,
    async_handlers=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=15 * 1024 * 1024,  # 15MB to handle base64-encoded files (5MB image = ~6.7MB base64)
    cors_allowed_origins=socket_origins,  # The same CORS origins as FastAPI, plus our own host
)

# Create ASGI app
socket_app = socketio.ASGIApp(
    socketio_server=sio,
    socketio_path='socket.io'
)

def redis_options(redis_url: str) -> dict:
    """Connection options for the Socket.IO Redis manager. ssl_cert_reqs is a
    TLS-only option — redis-py refuses it on a plain redis:// connection, and the
    manager's listener then fails in a loop."""
    options = {
        'retry_on_timeout': True,
        'health_check_interval': 30,
        'socket_timeout': 5.0,
        'socket_connect_timeout': 5.0,
    }
    if redis_url.startswith("rediss://"):
        options['ssl_cert_reqs'] = None  # ElastiCache's certificate is not verified
    return options


def configure_socketio(cors_origins=None):
    """Configure Socket.IO with CORS origins and Redis if enabled"""
    if cors_origins:
        # Convert set to list if needed and ensure all origins are strings
        cors_list = list(cors_origins) if isinstance(cors_origins, (set, list)) else [cors_origins]
        
        socket_origins.update(cors_list)
        sio.eio.cors_allowed_origins = socket_origins

    if settings.REDIS_ENABLED:
        # Use rediss:// protocol if TLS is needed (ElastiCache)
        redis_url = settings.REDIS_URL
        if needs_elasticache_tls(redis_url):
            redis_url = "rediss://" + redis_url[8:]
            logger.info(f"Using TLS for Redis connection: {redis_url}")
        
        logger.info(f"Redis URL: {redis_url}")
        
        try:
            # The server routes every emit through sio.manager, which it set
            # up at construction; assigning client_manager afterwards (as this
            # once did) changes nothing, so emits from other processes — the
            # ticket worker's CSAT requests and ticket updates — never left
            # them. Install the Redis manager where the server looks for it.
            # Local clients are still served directly; Redis carries the emit
            # to the other processes.
            manager = socketio.AsyncRedisManager(
                redis_url,
                write_only=False,
                channel='chattermate',
                redis_options=redis_options(redis_url),
            )
            manager.set_server(sio)
            sio.manager = manager
            sio.manager_initialized = False
            logger.info("Redis manager configured successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Redis manager: {str(e)}") 