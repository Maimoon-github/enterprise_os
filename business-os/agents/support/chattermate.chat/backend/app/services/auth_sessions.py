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

Server-side sessions behind the dashboard JWTs.

The tokens are stateless, so on their own signing out only deleted cookies: a
copied access token kept working for its 30 minutes and a refresh token kept
minting new ones for 7 days, and a password change ended nothing. Every token
now names an auth_sessions row in its `sid` claim, and a token is only live
while that row is.

Tokens without a `sid` (issued before this existed, or by the enterprise signup
flow) are accepted until they expire, so deploying this signs nobody out.

None of these functions commit: the session row belongs in the caller's
transaction, alongside whatever it is doing (a login, an org setup, a password
change).
"""

from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, verify_token
from app.models.auth_session import AuthSession

ACCESS = "access"
REFRESH = "refresh"


PASSWORD_LOGIN = "password"
SIGNUP = "signup"
SSO_LOGIN = "sso"


def issue_tokens(db: Session, user_id, org_id, sid=None, auth_method=None, identity_id=None) -> Tuple[str, str]:
    """Return (access_token, refresh_token) for a session.

    Without `sid` a new session is opened (a login), recording how it was
    opened. With the `sid` of a live session the tokens are re-minted for it
    (a refresh), so revoking it still ends everything that came from the same
    login.
    """
    if sid is None:
        session = AuthSession(user_id=_as_uuid(user_id), auth_method=auth_method, identity_id=identity_id)
        db.add(session)
        db.flush()
        sid = session.id

    token_data = {"sub": str(user_id), "org": str(org_id), "sid": str(sid)}
    return create_access_token(token_data), create_refresh_token(token_data)


def live_payload(db: Session, token: str, expected_type: str) -> Optional[dict]:
    """The token's payload if it is valid, of `expected_type` and not revoked.

    The type check keeps a 7-day refresh token from being used as an access
    token. A token without a `sid` predates sessions and is let through.
    """
    payload = verify_token(token)
    if not payload or payload.get("type") != expected_type:
        return None

    sid = payload.get("sid")
    if sid is None:
        return payload

    session_id = _as_uuid(sid)
    if session_id is None:
        return None
    session = db.query(AuthSession).filter(AuthSession.id == session_id).first()
    if (
        session is None
        or session.revoked_at is not None
        or str(session.user_id) != str(payload.get("sub"))
    ):
        return None
    return payload


def session_id_of(token: Optional[str]) -> Optional[str]:
    """The `sid` a correctly signed token carries, or None."""
    payload = verify_token(token) if token else None
    return payload.get("sid") if payload else None


def revoke_session(db: Session, sid) -> None:
    """End one session; both of its tokens stop working."""
    session_id = _as_uuid(sid)
    if session_id is None:
        return
    db.query(AuthSession).filter(
        AuthSession.id == session_id,
        AuthSession.revoked_at.is_(None),
    ).update({"revoked_at": datetime.now(timezone.utc)}, synchronize_session=False)


def revoke_identity_sessions(db: Session, identity_id, keep_sid=None) -> None:
    """End every session a linked SSO account opened, except `keep_sid`."""
    query = db.query(AuthSession).filter(
        AuthSession.identity_id == _as_uuid(identity_id),
        AuthSession.revoked_at.is_(None),
    )
    keep = _as_uuid(keep_sid) if keep_sid is not None else None
    if keep is not None:
        query = query.filter(AuthSession.id != keep)
    query.update({"revoked_at": datetime.now(timezone.utc)}, synchronize_session=False)


def revoke_user_sessions(db: Session, user_id, keep_sid=None) -> None:
    """End every session the user has, except `keep_sid` when given."""
    query = db.query(AuthSession).filter(
        AuthSession.user_id == _as_uuid(user_id),
        AuthSession.revoked_at.is_(None),
    )
    keep = _as_uuid(keep_sid) if keep_sid is not None else None
    if keep is not None:
        query = query.filter(AuthSession.id != keep)
    query.update({"revoked_at": datetime.now(timezone.utc)}, synchronize_session=False)


def session_method(db: Session, sid) -> str:
    """How a session was opened, for re-checking the sign-in policy on refresh.
    Sessions from before the record (and legacy tokens) count as password
    sign-ins, which is what they were or what a signup is."""
    session_id = _as_uuid(sid)
    method = None
    if session_id is not None:
        method = db.query(AuthSession.auth_method).filter(AuthSession.id == session_id).scalar()
    return SSO_LOGIN if method == SSO_LOGIN else PASSWORD_LOGIN


def revoke_non_sso_sessions(db: Session, user_id) -> None:
    """End every session the user opened other than through SSO."""
    db.query(AuthSession).filter(
        AuthSession.user_id == _as_uuid(user_id),
        AuthSession.revoked_at.is_(None),
        or_(AuthSession.auth_method.is_(None), AuthSession.auth_method != SSO_LOGIN),
    ).update({"revoked_at": datetime.now(timezone.utc)}, synchronize_session=False)


def _as_uuid(value) -> Optional[UUID]:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def session_user_payload(user, role) -> dict:
    """The `user` object a sign-in answers with. The profile picture stays as
    stored: UserResponse signs it on the way out."""
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "organization_id": user.organization_id,
        "profile_pic": user.profile_pic,
        "is_online": user.is_online,
        "last_seen": user.last_seen,
        "is_active": user.is_active,
        "role": role.to_dict() if role else None,
    }
