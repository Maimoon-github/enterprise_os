import uuid

from app.api.deps import get_db
from app.core.config import settings
from app.core.exceptions import AuthenticationFailedError
from app.core.rbac import UserRole
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_token,
)
from app.db.models.user import User
from app.db.repositories.base_repo import BaseRepository
from app.schemas.auth import (
    AuthProviderStatus,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/providers", response_model=list[AuthProviderStatus])
async def get_auth_providers():
    """Return explicit status for social authentication providers.

    All unconfigured providers are explicitly marked, and client IDs are safely masked.
    """
    providers: list[AuthProviderStatus] = []

    # Google Workspace OAuth
    google_configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    masked_google = (
        f"{settings.GOOGLE_CLIENT_ID[:6]}...{settings.GOOGLE_CLIENT_ID[-4:]}"
        if google_configured and len(str(settings.GOOGLE_CLIENT_ID)) > 10
        else None
    )
    providers.append(
        AuthProviderStatus(
            id="google",
            name="Google Workspace",
            enabled=google_configured,
            configured=google_configured,
            client_id_preview=masked_google,
        )
    )

    # GitHub OAuth
    github_configured = bool(settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET)
    masked_github = (
        f"{settings.GITHUB_CLIENT_ID[:4]}...{settings.GITHUB_CLIENT_ID[-4:]}"
        if github_configured and len(str(settings.GITHUB_CLIENT_ID)) > 8
        else None
    )
    providers.append(
        AuthProviderStatus(
            id="github",
            name="GitHub OAuth",
            enabled=github_configured,
            configured=github_configured,
            client_id_preview=masked_github,
        )
    )

    return providers


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalars().first()

    if not user:
        raise AuthenticationFailedError("Invalid email or password")
    if not verify_password(credentials.password, user.hashed_password):
        raise AuthenticationFailedError("Invalid email or password")
    if not user.is_active:
        raise AuthenticationFailedError("User account is inactive")

    user_id = str(user.id)
    role = user.role
    email = user.email

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
