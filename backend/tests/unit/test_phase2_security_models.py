from datetime import UTC, datetime

import pytest
from app.core.idempotency import generate_schedule_idempotency_key
from app.core.rbac import UserRole, check_permission, has_role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.db.base import Base
from fastapi import HTTPException


def test_core_models_registered_on_base():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "brands",
        "campaigns",
        "runs",
        "approvals",
        "media_assets",
        "schedules",
        "analytics_events",
    }
    assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"


def test_argon2id_password_hashing():
    password = "SuperSecurePassword123!"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_authlib_jwt_access_and_refresh_tokens():
    data = {"sub": "user_123", "email": "test@example.com", "role": "editor"}
    access_token = create_access_token(data, expires_delta_seconds=300)
    refresh_token = create_refresh_token(data, expires_delta_seconds=600)

    access_claims = verify_token(access_token)
    assert access_claims["sub"] == "user_123"
    assert access_claims["role"] == "editor"
    assert access_claims["type"] == "access"

    refresh_claims = verify_token(refresh_token)
    assert refresh_claims["sub"] == "user_123"
    assert refresh_claims["type"] == "refresh"


def test_rbac_hierarchy():
    # admin > editor > operator > viewer
    assert has_role("admin", UserRole.VIEWER) is True
    assert has_role("admin", UserRole.OPERATOR) is True
    assert has_role("admin", UserRole.EDITOR) is True
    assert has_role("admin", UserRole.ADMIN) is True

    assert has_role("editor", UserRole.OPERATOR) is True
    assert has_role("editor", UserRole.ADMIN) is False

    assert has_role("operator", UserRole.VIEWER) is True
    assert has_role("operator", UserRole.EDITOR) is False

    assert has_role("viewer", UserRole.OPERATOR) is False

    # check_permission succeeds
    check_permission("admin", minimum_role=UserRole.EDITOR)
    check_permission("editor", minimum_role=UserRole.OPERATOR)

    # check_permission fails
    with pytest.raises(HTTPException):
        check_permission("viewer", minimum_role=UserRole.OPERATOR)



def test_idempotency_key_generation():
    dt = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC)
    key1 = generate_schedule_idempotency_key("camp-1", "linkedin", dt)
    key2 = generate_schedule_idempotency_key("camp-1", "linkedin", dt)
    key3 = generate_schedule_idempotency_key("camp-1", "youtube", dt)

    assert key1 == key2
    assert len(key1) == 64
    assert key1 != key3
