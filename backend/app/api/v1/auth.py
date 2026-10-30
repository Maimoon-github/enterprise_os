import uuid

from app.api.deps import get_db
from app.core.exceptions import AuthenticationFailedError
from app.core.rbac import UserRole
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.db.models.user import User
from app.db.repositories.base_repo import BaseRepository
from app.schemas.auth import LoginRequest, RefreshTokenRequest, TokenResponse
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    repo = BaseRepository(User, db)
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalars().first()

    if user:
        if not verify_password(credentials.password, user.hashed_password):
            raise AuthenticationFailedError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationFailedError("User account is inactive")
        user_id = str(user.id)
        role = user.role
        email = user.email
    elif credentials.email == "admin@marketing-os.local" and credentials.password == "admin123":
        # Seed initial admin user if not present
        hashed = get_password_hash(credentials.password)
        admin_user = await repo.create(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            email=credentials.email,
            hashed_password=hashed,
            full_name="System Administrator",
            role=UserRole.ADMIN.value,
            is_active=True,
        )
        user_id = str(admin_user.id)
        role = admin_user.role
        email = admin_user.email
    else:
        raise AuthenticationFailedError("Invalid email or password")

    token_data = {"sub": user_id, "email": email, "role": role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        role=role,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        claims = verify_token(payload.refresh_token)
    except Exception:
        raise AuthenticationFailedError("Invalid or expired refresh token")

    if claims.get("type") != "refresh":
        raise AuthenticationFailedError("Provided token is not a refresh token")

    user_id = claims.get("sub")
    if not user_id:
        raise AuthenticationFailedError("Invalid token claims")

    repo = BaseRepository(User, db)
    try:
        user_uuid = uuid.UUID(user_id)
        user = await repo.get(user_uuid)
        role = user.role if user else claims.get("role", UserRole.VIEWER.value)
        email = user.email if user else claims.get("email", "")
    except (ValueError, TypeError):
        role = claims.get("role", UserRole.VIEWER.value)
        email = claims.get("email", "")

    new_token_data = {"sub": user_id, "email": email, "role": role}
    new_access_token = create_access_token(new_token_data)
    new_refresh_token = create_refresh_token(new_token_data)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        role=role,
    )
