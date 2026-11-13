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

from typing import Optional, Tuple
from uuid import UUID
import http.cookies
from urllib.parse import parse_qs, urlparse
from app.core.security import verify_conversation_token
from app.core.logger import get_logger
from app.database import close_session, session_off_loop
from app.models.user import User
from sqlalchemy.orm import Session
from app.core.cors import is_first_party_origin, origin_of
from app.models.widget import Widget
from app.repositories.customer import CustomerRepository
from app.services.auth_sessions import ACCESS, REFRESH, issue_tokens, live_payload

logger = get_logger(__name__)


async def refresh_access_token(refresh_token: str, db: Session) -> str | None:
    """Refresh access token using refresh token"""
    try:
        payload = live_payload(db, refresh_token, REFRESH)
        if not payload:
            return None

        user_id = payload.get("sub")
        org_id = payload.get("org")

        if not user_id or not org_id:
            return None

        # Verify user exists and is active
        user = db.query(User).filter(User.id == UUID(user_id)).first()
        if not user or not user.is_active:
            return None

        # Generate new access token for the same session (a legacy token
        # without one gets a new session)
        access_token, _ = issue_tokens(db, user_id, org_id, sid=payload.get("sid"))
        db.commit()
        return access_token

    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        return None


def _is_own_origin(origin: str, host: str) -> bool:
    """Whether Origin is the API's own origin (the host the request was sent to)."""
    own = origin_of(origin)
    return bool(own and host) and own == origin_of(f"{urlparse(origin).scheme}://{host}")


def cookie_socket_allowed(environ: dict) -> bool:
    """Whether a socket handshake may sign in with the dashboard's cookies.

    Sockets get no CORS check and the cookies are SameSite=None, so a page on
    another site (an org's signup domain is unverified) could otherwise open
    the socket as whoever is signed in. socket.io authenticates a namespace
    with the headers of the first handshake request, so all of it must have
    come from our own pages:
    - never a JSONP handshake: a <script> tag sends the cookies without an Origin
    - with an Origin, a first-party one or the API's own origin
    - without one, only a same-origin request (browsers omit Origin on
      same-origin GETs, e.g. polling behind a single-host proxy)
    """
    if "j" in parse_qs(environ.get("QUERY_STRING", "")):
        return False
    origin = environ.get("HTTP_ORIGIN")
    if origin:
        return is_first_party_origin(origin) or _is_own_origin(origin, environ.get("HTTP_HOST", ""))
    return environ.get("HTTP_SEC_FETCH_SITE") == "same-origin"


async def authenticate_socket(sid: str, environ: dict) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Authenticate socket connection using cookies
    Returns: (access_token, user_id, org_id)
    """
    if not cookie_socket_allowed(environ):
        logger.warning(f"Refused cookie socket auth for sid {sid} from origin {environ.get('HTTP_ORIGIN')}")
        return None, None, None

    try:
        # Extract cookies from environ
        cookie_str = environ.get('HTTP_COOKIE', environ.get('headers', {}).get('Cookie', ''))
        cookies = http.cookies.SimpleCookie()
        cookies.load(cookie_str)

        # Get access token from cookies
        access_token = None
        if 'access_token' in cookies:
            access_token = cookies['access_token'].value

        if not access_token:
            logger.info("No access token found in cookies")
            # Try to refresh using refresh token
            if 'refresh_token' in cookies:
                refresh_token = cookies['refresh_token'].value
                db = await session_off_loop()
                try:
                    access_token = await refresh_access_token(refresh_token, db)
                finally:
                    close_session(db)

        if not access_token:
            return None, None, None

        # Verify the token is a live access token of a user who can still sign in
        db = await session_off_loop()
        try:
            payload = live_payload(db, access_token, ACCESS)
            if not payload:
                return None, None, None

            user_id = payload.get('sub')
            org_id = payload.get('org')

            user = db.query(User).filter(User.id == UUID(str(user_id))).first()
            if not user or not user.is_active:
                return None, None, None
        finally:
            close_session(db)

        return access_token, user_id, org_id

    except Exception as e:
        logger.error(f"Authentication error for sid {sid}: {str(e)}")
        return None, None, None


async def authenticate_socket_conversation_token(sid: str, auth: dict) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Authenticate widget socket connection using conversation token.
    Supports both token-required and optional-token authentication modes.
    
    Returns: (widget_id, org_id, customer_id, conversation_token)
    Returns (None, None, None, None) if authentication fails
    """
    try:
        if not auth or not isinstance(auth, dict):
            logger.warning(f"Socket auth failed: No auth data for sid {sid}")
            return None, None, None, None
        conversation_token = None
        
        # Get token from Socket.IO auth data
        conversation_token = auth.get('conversation_token', '')
        
                
        if not conversation_token:
            logger.info("No conversation token found in auth data or cookies")
            return None, None, None, None

        # Verify token and get info
        token_data = verify_conversation_token(conversation_token)
        if not token_data:
            return None, None, None, None

        widget_id = token_data.get('widget_id')
        customer_id = token_data.get('sub')
        token_type = token_data.get('type')

        # Verify token type
        if token_type != "conversation":
            logger.info(f"Invalid token type: {token_type}")
            return None, None, None, None

        logger.info(f"Authenticated widget {widget_id} for customer {customer_id}")

        # Get widget to verify and get org_id
        db = await session_off_loop()
        try:
            widget = db.query(Widget).filter(Widget.id == widget_id).first()
            if not widget:
                return None, None, None, None

            org_id = widget.organization_id

            # Resolve merged customers: if this device's token still carries an
            # anonymous customer that was merged into an identified one (lead
            # capture matched an existing email), continue as the merged target so
            # returning visitors keep their identity and history.
            if customer_id:
                survivor = CustomerRepository(db).resolve_merged(customer_id)
                if survivor is not None:
                    customer_id = str(survivor.id)
        finally:
            close_session(db)
        return widget_id, org_id, customer_id, conversation_token

    except Exception as e:
        logger.error(f"Widget authentication error for sid {sid}: {str(e)}")
        return None, None, None, None


def widget_socket_identity(session: Optional[dict]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Identity of an already-connected widget socket, from its server-side session.

    The conversation token authenticates the *connection*: the /widget connect
    handler runs authenticate_socket_conversation_token once and stores what it
    resolved. Events arriving on a live connection read that back instead of
    re-verifying the token, because the token's lifetime is not the connection's
    lifetime — re-checking tore down working chats the moment the TTL passed
    (mid-conversation, and on end_chat when the visitor closed the widget), and
    it did the same whenever Redis lost the token's JTI. Expiry and revocation
    still take effect: the next connect is authenticated normally.

    Returns (None, None, None) when there is no authenticated session for the sid.
    """
    if not session:
        return None, None, None

    widget_id = session.get('widget_id')
    org_id = session.get('org_id')
    if not widget_id or not org_id:
        return None, None, None

    return widget_id, org_id, session.get('customer_id')
