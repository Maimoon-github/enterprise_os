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
from uuid import uuid4

from app.core.security import create_access_token, verify_token
from app.models.auth_session import AuthSession
from app.models.user import User
from app.services.auth_sessions import (
    ACCESS,
    REFRESH,
    issue_tokens,
    live_payload,
    revoke_user_sessions,
)


def _user(db, org, email):
    user = User(
        id=uuid4(),
        email=email,
        hashed_password="x",
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def user(db, test_organization):
    return _user(db, test_organization, "one@test.com")


def test_live_payload_checks_the_token_type(db, user):
    access, refresh = issue_tokens(db, user.id, user.organization_id)
    db.commit()

    assert live_payload(db, access, ACCESS)["sub"] == str(user.id)
    assert live_payload(db, refresh, REFRESH)["sub"] == str(user.id)
    assert live_payload(db, access, REFRESH) is None
    assert live_payload(db, refresh, ACCESS) is None


def test_live_payload_rejects_a_session_of_another_user(db, user, test_organization):
    """A sid is only good for the user it was opened for"""
    other = _user(db, test_organization, "two@test.com")
    access, _ = issue_tokens(db, other.id, other.organization_id)
    db.commit()
    sid = verify_token(access)["sid"]

    forged = create_access_token({"sub": str(user.id), "org": str(user.organization_id), "sid": sid})

    assert live_payload(db, forged, ACCESS) is None


@pytest.mark.parametrize("sid", [str(uuid4()), "not-a-uuid"])
def test_live_payload_rejects_an_unknown_session(db, user, sid):
    token = create_access_token({"sub": str(user.id), "org": str(user.organization_id), "sid": sid})

    assert live_payload(db, token, ACCESS) is None


def test_revoke_user_sessions_can_keep_one(db, user, test_organization):
    other = _user(db, test_organization, "two@test.com")
    keep, _ = issue_tokens(db, user.id, user.organization_id)
    drop, _ = issue_tokens(db, user.id, user.organization_id)
    bystander, _ = issue_tokens(db, other.id, other.organization_id)
    db.commit()

    revoke_user_sessions(db, user.id, keep_sid=verify_token(keep)["sid"])
    db.commit()

    assert live_payload(db, keep, ACCESS) is not None
    assert live_payload(db, drop, ACCESS) is None
    assert live_payload(db, bystander, ACCESS) is not None
    assert db.query(AuthSession).filter(AuthSession.revoked_at.isnot(None)).count() == 1
