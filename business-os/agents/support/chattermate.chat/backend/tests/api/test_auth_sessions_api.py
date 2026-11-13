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

Server-side sessions behind the dashboard JWTs, end to end through the real
auth dependencies: nothing here overrides get_current_user.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.api import users as users_router
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, get_password_hash, verify_token
from app.database import Base, get_db
from app.models.auth_session import AuthSession
from app.models.permission import Permission, role_permissions
from app.models.role import Role
from app.models.user import User
from tests.conftest import engine, TestingSessionLocal, create_tables

app = FastAPI()
app.include_router(users_router.router, prefix=f"{settings.API_V1_STR}/users")

USERS = f"{settings.API_V1_STR}/users"
ADMIN_PASSWORD = "Adm1nPassw0rd!"
AGENT_PASSWORD = "Ag3ntPassw0rd!"


@pytest.fixture(scope="function")
def db():
    Base.metadata.drop_all(bind=engine)
    create_tables()
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def role(db: Session, test_organization) -> Role:
    perm = Permission(name="manage_users", description="Can manage users")
    db.add(perm)
    role = Role(name="Admin", organization_id=test_organization.id)
    db.add(role)
    db.commit()
    db.execute(role_permissions.insert().values(role_id=role.id, permission_id=perm.id))
    db.commit()
    return role


def _user(db: Session, org, role: Role, email: str, password: str) -> User:
    user = User(
        id=uuid4(),
        email=email,
        hashed_password=get_password_hash(password),
        organization_id=org.id,
        role_id=role.id,
        is_active=True,
        full_name=email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin(db, test_organization, role) -> User:
    return _user(db, test_organization, role, "admin@test.com", ADMIN_PASSWORD)


@pytest.fixture
def agent(db, test_organization, role) -> User:
    return _user(db, test_organization, role, "agent@test.com", AGENT_PASSWORD)


@pytest.fixture
def client(db) -> TestClient:
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    users_router.HAS_ENTERPRISE = False
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client: TestClient, email: str, password: str) -> dict:
    response = client.post(f"{USERS}/login", data={"username": email, "password": password})
    assert response.status_code == 200
    # Pass tokens explicitly on each request rather than through the cookie jar.
    client.cookies.clear()
    return response.json()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def refresh_cookie(token: str) -> dict:
    return {"Cookie": f"refresh_token={token}"}


def can_read_user(client: TestClient, token: str, user: User) -> int:
    """Status of an authenticated request made with `token`."""
    return client.get(f"{USERS}/{user.id}", headers=bearer(token)).status_code


def test_login_opens_a_session_both_tokens_share(client, db, admin):
    tokens = login(client, admin.email, ADMIN_PASSWORD)

    sid = verify_token(tokens["access_token"])["sid"]
    assert verify_token(tokens["refresh_token"])["sid"] == sid
    session = db.query(AuthSession).filter(AuthSession.id == UUID(sid)).one()
    assert session.user_id == admin.id
    assert session.revoked_at is None


def test_refresh_keeps_the_session(client, db, admin):
    tokens = login(client, admin.email, ADMIN_PASSWORD)

    response = client.post(f"{USERS}/refresh", headers=refresh_cookie(tokens["refresh_token"]))

    assert response.status_code == 200
    refreshed = response.json()
    assert verify_token(refreshed["access_token"])["sid"] == verify_token(tokens["access_token"])["sid"]
    assert db.query(AuthSession).count() == 1


def test_logout_revokes_the_access_and_refresh_tokens(client, admin):
    tokens = login(client, admin.email, ADMIN_PASSWORD)
    assert can_read_user(client, tokens["access_token"], admin) == 200

    response = client.post(
        f"{USERS}/logout",
        headers={**bearer(tokens["access_token"]), **refresh_cookie(tokens["refresh_token"])},
    )
    assert response.status_code == 200

    # A copy of either token taken before sign-out no longer works
    assert can_read_user(client, tokens["access_token"], admin) == 401
    response = client.post(f"{USERS}/refresh", headers=refresh_cookie(tokens["refresh_token"]))
    assert response.status_code == 401


def test_logout_leaves_other_sessions_alone(client, admin):
    laptop = login(client, admin.email, ADMIN_PASSWORD)
    phone = login(client, admin.email, ADMIN_PASSWORD)

    client.post(f"{USERS}/logout", headers=bearer(laptop["access_token"]))

    assert can_read_user(client, laptop["access_token"], admin) == 401
    assert can_read_user(client, phone["access_token"], admin) == 200


def test_refresh_token_is_not_an_access_token(client, admin):
    tokens = login(client, admin.email, ADMIN_PASSWORD)

    assert can_read_user(client, tokens["refresh_token"], admin) == 401


def test_access_token_is_not_a_refresh_token(client, admin):
    tokens = login(client, admin.email, ADMIN_PASSWORD)

    response = client.post(f"{USERS}/refresh", headers=refresh_cookie(tokens["access_token"]))

    assert response.status_code == 401


def test_legacy_tokens_without_a_session_still_work(client, db, admin):
    """Tokens issued before sessions existed must not sign anyone out on deploy"""
    claims = {"sub": str(admin.id), "org": str(admin.organization_id)}
    assert can_read_user(client, create_access_token(claims), admin) == 200

    response = client.post(f"{USERS}/refresh", headers=refresh_cookie(create_refresh_token(claims)))

    # ...and refreshing one moves it onto a real session
    assert response.status_code == 200
    sid = verify_token(response.json()["access_token"])["sid"]
    assert verify_token(response.json()["refresh_token"])["sid"] == sid
    assert db.query(AuthSession).filter(AuthSession.id == UUID(sid)).one().user_id == admin.id


def test_password_change_signs_out_other_sessions_only(client, admin):
    current = login(client, admin.email, ADMIN_PASSWORD)
    other = login(client, admin.email, ADMIN_PASSWORD)

    response = client.patch(
        f"{USERS}/me",
        json={"current_password": ADMIN_PASSWORD, "password": "N3wPassw0rd!"},
        headers=bearer(current["access_token"]),
    )
    assert response.status_code == 200

    assert can_read_user(client, current["access_token"], admin) == 200
    assert can_read_user(client, other["access_token"], admin) == 401
    response = client.post(f"{USERS}/refresh", headers=refresh_cookie(other["refresh_token"]))
    assert response.status_code == 401


def test_admin_password_reset_signs_out_the_target(client, admin, agent):
    admin_tokens = login(client, admin.email, ADMIN_PASSWORD)
    agent_tokens = login(client, agent.email, AGENT_PASSWORD)

    response = client.post(
        f"{USERS}/{agent.id}/reset-password",
        json={"new_password": "N3wPassw0rd!"},
        headers=bearer(admin_tokens["access_token"]),
    )
    assert response.status_code == 200

    assert can_read_user(client, agent_tokens["access_token"], agent) == 401
    response = client.post(f"{USERS}/refresh", headers=refresh_cookie(agent_tokens["refresh_token"]))
    assert response.status_code == 401
    assert can_read_user(client, admin_tokens["access_token"], admin) == 200


def test_deactivating_a_user_revokes_their_sessions(client, db, admin, agent):
    admin_tokens = login(client, admin.email, ADMIN_PASSWORD)
    login(client, agent.email, AGENT_PASSWORD)

    response = client.put(
        f"{USERS}/{agent.id}",
        json={"is_active": False},
        headers=bearer(admin_tokens["access_token"]),
    )
    assert response.status_code == 200

    sessions = db.query(AuthSession).filter(AuthSession.user_id == agent.id).all()
    assert sessions and all(s.revoked_at is not None for s in sessions)
