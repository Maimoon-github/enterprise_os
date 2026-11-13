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
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.auth_utils import (
    refresh_access_token,
    authenticate_socket,
    authenticate_socket_conversation_token,
    widget_socket_identity,
)
from app.models.user import User
from app.models.widget import Widget
from uuid import uuid4
import http.cookies
from datetime import datetime, timezone
from app.core.security import verify_token, verify_conversation_token, create_access_token, create_refresh_token, create_conversation_token
from app.models.auth_session import AuthSession
from app.services.auth_sessions import issue_tokens, revoke_session

@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = MagicMock()
    return db

@pytest.fixture
def mock_user():
    """Create a mock user"""
    user_id = uuid4()
    org_id = uuid4()
    return User(
        id=user_id,
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        organization_id=org_id,
        full_name="Test User"
    )

@pytest.fixture
def mock_widget():
    """Create a mock widget"""
    widget_id = uuid4()
    org_id = uuid4()
    return Widget(
        id=str(widget_id),
        organization_id=org_id,
        name="Test Widget"
    )

@pytest.fixture
def live_user(db, test_organization):
    """A real, active user — session checks run against the database."""
    user = User(
        id=uuid4(),
        email="socket@example.com",
        hashed_password="hashed_password",
        is_active=True,
        organization_id=test_organization.id,
        full_name="Socket User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def socket_db(db):
    """Point authenticate_socket's sessions at the test database."""
    with patch('app.core.auth_utils.session_off_loop', AsyncMock(return_value=db)):
        yield db


def _socket_environ(**cookies):
    # A same-origin handshake: only our own pages may sign in with the cookies
    jar = http.cookies.SimpleCookie()
    for name, value in cookies.items():
        jar[name] = value
    return {'HTTP_COOKIE': jar.output(header='', sep=';'), 'HTTP_SEC_FETCH_SITE': 'same-origin'}


@pytest.mark.asyncio
async def test_refresh_access_token_success(db, live_user):
    """A live refresh token re-mints an access token for the same session"""
    _, refresh_token = issue_tokens(db, live_user.id, live_user.organization_id)
    db.commit()

    result = await refresh_access_token(refresh_token, db)

    payload = verify_token(result)
    assert payload["type"] == "access"
    assert payload["sub"] == str(live_user.id)
    assert payload["sid"] == verify_token(refresh_token)["sid"]
    assert db.query(AuthSession).count() == 1


@pytest.mark.asyncio
async def test_refresh_access_token_invalid_token(db):
    """Test access token refresh with invalid token"""
    assert await refresh_access_token("invalid_token", db) is None


@pytest.mark.asyncio
async def test_refresh_access_token_inactive_user(db, live_user):
    """Test access token refresh with inactive user"""
    _, refresh_token = issue_tokens(db, live_user.id, live_user.organization_id)
    live_user.is_active = False
    db.commit()

    assert await refresh_access_token(refresh_token, db) is None


@pytest.mark.asyncio
async def test_refresh_access_token_rejects_revoked_session(db, live_user):
    """A refresh token from a signed-out session mints nothing"""
    _, refresh_token = issue_tokens(db, live_user.id, live_user.organization_id)
    revoke_session(db, verify_token(refresh_token)["sid"])
    db.commit()

    assert await refresh_access_token(refresh_token, db) is None


@pytest.mark.asyncio
async def test_refresh_access_token_rejects_an_access_token(db, live_user):
    """Only a refresh token can be refreshed"""
    access_token, _ = issue_tokens(db, live_user.id, live_user.organization_id)
    db.commit()

    assert await refresh_access_token(access_token, db) is None


@pytest.mark.asyncio
async def test_refresh_access_token_migrates_a_legacy_token(db, live_user):
    """A refresh token from before sessions still works, and gets a session"""
    legacy = create_refresh_token({"sub": str(live_user.id), "org": str(live_user.organization_id)})

    result = await refresh_access_token(legacy, db)

    sid = verify_token(result)["sid"]
    session = db.query(AuthSession).one()
    assert str(session.id) == sid
    assert session.user_id == live_user.id


@pytest.mark.asyncio
async def test_authenticate_socket_success(socket_db, live_user):
    """Test successful socket authentication"""
    access_token, _ = issue_tokens(socket_db, live_user.id, live_user.organization_id)
    socket_db.commit()

    result = await authenticate_socket("test_sid", _socket_environ(access_token=access_token))

    assert result == (access_token, str(live_user.id), str(live_user.organization_id))


@pytest.mark.asyncio
async def test_authenticate_socket_with_refresh(socket_db, live_user):
    """Test socket authentication with token refresh"""
    sid = "test_sid"
    _, refresh_token = issue_tokens(socket_db, live_user.id, live_user.organization_id)
    socket_db.commit()

    result_token, result_user_id, result_org_id = await authenticate_socket(
        sid, _socket_environ(refresh_token=refresh_token))

    assert verify_token(result_token)["type"] == "access"
    assert result_user_id == str(live_user.id)
    assert result_org_id == str(live_user.organization_id)


@pytest.mark.asyncio
async def test_authenticate_socket_rejects_a_revoked_session(socket_db, live_user):
    """A token copied before sign-out cannot open a socket"""
    access_token, _ = issue_tokens(socket_db, live_user.id, live_user.organization_id)
    revoke_session(socket_db, verify_token(access_token)["sid"])
    socket_db.commit()

    result = await authenticate_socket("test_sid", _socket_environ(access_token=access_token))

    assert result == (None, None, None)


@pytest.mark.asyncio
async def test_authenticate_socket_rejects_a_refresh_token(socket_db, live_user):
    """A refresh token in the access_token cookie is the wrong type"""
    _, refresh_token = issue_tokens(socket_db, live_user.id, live_user.organization_id)
    socket_db.commit()

    result = await authenticate_socket("test_sid", _socket_environ(access_token=refresh_token))

    assert result == (None, None, None)


@pytest.mark.asyncio
async def test_authenticate_socket_rejects_an_inactive_user(socket_db, live_user):
    """A deactivated user's still-unexpired token cannot open a socket"""
    access_token, _ = issue_tokens(socket_db, live_user.id, live_user.organization_id)
    live_user.is_active = False
    socket_db.commit()

    result = await authenticate_socket("test_sid", _socket_environ(access_token=access_token))

    assert result == (None, None, None)


@pytest.mark.asyncio
async def test_authenticate_socket_rejects_a_deleted_user(socket_db):
    """A legacy token for a user who no longer exists cannot open a socket"""
    access_token = create_access_token({"sub": str(uuid4()), "org": str(uuid4())})

    result = await authenticate_socket("test_sid", _socket_environ(access_token=access_token))

    assert result == (None, None, None)


@pytest.mark.asyncio
async def test_authenticate_socket_conversation_token_success(mock_db, mock_widget):
    """Test successful widget socket authentication"""
    # Setup
    sid = "test_sid"
    conversation_token = "valid_conversation_token"
    customer_id = str(uuid4())
    
    # Create auth data
    auth = {'conversation_token': conversation_token}

    mock_db.query.return_value.filter.return_value.first.return_value = mock_widget

    # No merged-into pointer for this customer: it resolves to itself.
    with patch('app.core.auth_utils.verify_conversation_token') as mock_verify, \
         patch('app.core.auth_utils.session_off_loop', AsyncMock(return_value=mock_db)), \
         patch('app.repositories.customer.CustomerRepository.resolve_merged',
               return_value=MagicMock(id=customer_id)):
        mock_verify.return_value = {
            "widget_id": str(mock_widget.id),
            "sub": customer_id,
            "type": "conversation"
        }
        
        # Execute
        result_widget_id, result_org_id, result_customer_id, result_token = await authenticate_socket_conversation_token(sid, auth)
        
        # Assert
        assert result_widget_id == str(mock_widget.id)
        assert result_org_id == mock_widget.organization_id
        assert result_customer_id == customer_id
        assert result_token == conversation_token

@pytest.mark.asyncio
async def test_authenticate_socket_conversation_token_invalid(mock_db):
    """Test widget socket authentication with invalid token"""
    # Setup
    sid = "test_sid"
    conversation_token = "invalid_token"
    
    # Create auth data
    auth = {'conversation_token': conversation_token}
    
    with patch('app.core.auth_utils.verify_conversation_token') as mock_verify:
        mock_verify.return_value = None
        
        # Execute
        result = await authenticate_socket_conversation_token(sid, auth)
        
        # Assert
        assert result == (None, None, None, None)

@pytest.mark.asyncio
async def test_authenticate_socket_conversation_token_missing_widget(mock_db):
    """Test widget socket authentication with missing widget"""
    # Setup
    sid = "test_sid"
    conversation_token = "valid_conversation_token"
    customer_id = str(uuid4())
    widget_id = str(uuid4())
    
    # Create auth data
    auth = {'conversation_token': conversation_token}
    
    mock_db.query.return_value.filter.return_value.first.return_value = None
    
    with patch('app.core.auth_utils.verify_conversation_token') as mock_verify, \
         patch('app.core.auth_utils.session_off_loop', AsyncMock(return_value=mock_db)):
        mock_verify.return_value = {
            "widget_id": widget_id,
            "sub": customer_id,
            "type": "conversation"
        }
        
        # Execute
        result = await authenticate_socket_conversation_token(sid, auth)
        
        # Assert
        assert result == (None, None, None, None)

@pytest.mark.asyncio
async def test_authenticate_socket_conversation_token_wrong_type(mock_db, mock_widget):
    """Test widget socket authentication with wrong token type"""
    # Setup
    sid = "test_sid"
    conversation_token = "wrong_type_token"
    customer_id = str(uuid4())
    
    # Create auth data
    auth = {'conversation_token': conversation_token}
    
    mock_db.query.return_value.filter.return_value.first.return_value = mock_widget
    
    with patch('app.core.auth_utils.verify_conversation_token') as mock_verify, \
         patch('app.core.auth_utils.session_off_loop', AsyncMock(return_value=mock_db)):
        mock_verify.return_value = {
            "widget_id": str(mock_widget.id),
            "sub": customer_id,
            "type": "access"  # Wrong token type
        }
        
        # Execute
        result = await authenticate_socket_conversation_token(sid, auth)
        
        # Assert
        assert result == (None, None, None, None)

@pytest.mark.asyncio
async def test_authenticate_socket_no_cookies(mock_db):
    """Test socket authentication with no cookies"""
    # Setup
    sid = "test_sid"
    environ = {}
    
    # Execute
    result_token, result_user_id, result_org_id = await authenticate_socket(sid, environ)
    
    # Assert
    assert result_token is None
    assert result_user_id is None
    assert result_org_id is None

@pytest.mark.asyncio
async def test_authenticate_socket_invalid_token_format(mock_db):
    """Test socket authentication with invalid token format"""
    # Setup
    sid = "test_sid"
    access_token = "invalid_format_token"
    
    # Create mock environ with cookies
    environ = _socket_environ(access_token=access_token)
    
    with patch('app.core.auth_utils.live_payload') as mock_verify:
        mock_verify.side_effect = Exception("Invalid token format")
        
        # Execute
        result_token, result_user_id, result_org_id = await authenticate_socket(sid, environ)
        
        # Assert
        assert result_token is None
        assert result_user_id is None
        assert result_org_id is None 


def test_widget_socket_identity_reads_the_connected_session():
    """A live connection's identity comes from what connect resolved, not from
    re-verifying the token on every event (#315)."""
    session = {
        "widget_id": "widget-1",
        "org_id": "org-1",
        "customer_id": "customer-1",
        "conversation_token": "long-since-expired",
    }

    assert widget_socket_identity(session) == ("widget-1", "org-1", "customer-1")


def test_widget_socket_identity_allows_an_anonymous_customer():
    """A visitor who has not been identified still has a widget and an org."""
    session = {"widget_id": "widget-1", "org_id": "org-1"}

    assert widget_socket_identity(session) == ("widget-1", "org-1", None)


@pytest.mark.parametrize("session", [
    None,
    {},
    {"widget_id": "widget-1"},
    {"org_id": "org-1"},
])
def test_widget_socket_identity_rejects_an_unauthenticated_socket(session):
    """No session means connect never authenticated this sid."""
    assert widget_socket_identity(session) == (None, None, None)
