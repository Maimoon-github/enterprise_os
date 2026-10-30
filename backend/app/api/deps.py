import uuid
from collections.abc import AsyncGenerator
from typing import Any

from app.core.exceptions import AuthenticationFailedError
from app.core.rbac import UserRole, check_permission
from app.core.security import verify_token
from app.db.models.user import User
from app.db.repositories.base_repo import BaseRepository
from app.db.session import get_async_session
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        payload = verify_token(token)
    except Exception:
        raise AuthenticationFailedError("Invalid or expired access token")

    token_type = payload.get("type", "access")
    if token_type != "access":
        raise AuthenticationFailedError("Invalid token type: access token required")

    user_id_str: str | None = payload.get("sub")
    role: str = payload.get("role", UserRole.VIEWER.value)
    email: str = payload.get("email", "")

    if not user_id_str:
        raise AuthenticationFailedError("Token missing subject claim")

    # Attempt to load persistent user if valid UUID
    try:
        user_uuid = uuid.UUID(user_id_str)
        repo = BaseRepository(User, db)
        user_obj = await repo.get(user_uuid)
        if user_obj:
            if not user_obj.is_active:
                raise AuthenticationFailedError("User account is inactive")
            return {
                "id": str(user_obj.id),
                "email": user_obj.email,
                "role": user_obj.role,
                "full_name": user_obj.full_name,
            }
    except (ValueError, TypeError):
        pass

    return {
        "id": user_id_str,
        "email": email,
        "role": role,
        "full_name": payload.get("full_name"),
    }


def require_role(minimum_role: str | UserRole):
    async def role_checker(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        check_permission(current_user.get("role", UserRole.VIEWER.value), minimum_role=minimum_role)
        return current_user

    return role_checker
