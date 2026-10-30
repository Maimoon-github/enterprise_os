import uuid
from datetime import UTC, datetime
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.rbac import UserRole
from app.core.security import get_password_hash
from app.db.models.user import User
from app.db.repositories.base_repo import BaseRepository
from app.schemas.auth import UserCreate, UserProfile
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user_uuid = uuid.UUID(current_user["id"])
        repo = BaseRepository(User, db)
        user = await repo.get(user_uuid)
        if user:
            return user
    except (ValueError, TypeError):
        pass

    return UserProfile(
        id=uuid.UUID(current_user.get("id", "00000000-0000-0000-0000-000000000001")),
        email=current_user.get("email", "admin@marketing-os.local"),
        full_name=current_user.get("full_name", "System Administrator"),
        role=current_user.get("role", UserRole.VIEWER.value),
        is_active=True,
        created_at=datetime.now(UTC),
    )


@router.get("", response_model=list[UserProfile], dependencies=[Depends(require_role(UserRole.ADMIN))])
async def list_users(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    repo = BaseRepository(User, db)
    return await repo.list_all(limit=limit, offset=offset)


@router.post("", response_model=UserProfile, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role(UserRole.ADMIN))])
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email '{payload.email}' already exists",
        )

    repo = BaseRepository(User, db)
    user = await repo.create(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    return user
