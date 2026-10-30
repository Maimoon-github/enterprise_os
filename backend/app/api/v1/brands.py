import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.exceptions import EntityNotFoundError
from app.core.rbac import UserRole
from app.db.repositories.brand_repo import BrandRepository
from app.schemas.brand import BrandCreate, BrandResponse
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[BrandResponse])
async def list_brands(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    repo = BrandRepository(db)
    return await repo.list_all(limit=limit, offset=offset)


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    payload: BrandCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.EDITOR)),
):
    repo = BrandRepository(db)
    existing = await repo.get_by_slug(payload.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Brand with slug '{payload.slug}' already exists",
        )

    brand = await repo.create(
        name=payload.name,
        slug=payload.slug,
        voice_guidelines=payload.voice_guidelines,
        target_segments=payload.target_segments,
        default_platforms=payload.default_platforms,
    )
    return brand


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    repo = BrandRepository(db)
    brand = await repo.get(brand_id)
    if not brand:
        raise EntityNotFoundError("Brand", str(brand_id))
    return brand
