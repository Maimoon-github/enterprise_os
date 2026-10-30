import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.config import settings
from app.core.exceptions import EntityNotFoundError
from app.core.rbac import UserRole
from app.db.models.media_asset import MediaAsset
from app.db.repositories.media_repo import MediaRepository
from app.schemas.media import MediaAssetResponse, MediaPresignedUrlResponse
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[MediaAssetResponse])
async def list_media_assets(
    brand_id: uuid.UUID | None = None,
    campaign_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    repo = MediaRepository(db)
    if campaign_id:
        return await repo.list_by_campaign(campaign_id)
    if brand_id:
        result = await db.execute(
            select(MediaAsset).where(MediaAsset.brand_id == brand_id).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    return await repo.list_all(limit=limit, offset=offset)


@router.get("/presigned", response_model=MediaPresignedUrlResponse)
async def get_presigned_url(
    filename: str = Query("asset.png"),
    bucket: str | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    target_bucket = bucket or settings.MINIO_BUCKET_RAW
    key = f"uploads/{uuid.uuid4().hex[:12]}_{filename}"
    url = f"http://{settings.MINIO_ENDPOINT}/{target_bucket}/{key}"
    return MediaPresignedUrlResponse(
        url=url,
        bucket=target_bucket,
        key=key,
        expires_in=3600,
    )


@router.get("/{media_id}", response_model=MediaAssetResponse)
async def get_media_asset(
    media_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    repo = MediaRepository(db)
    asset = await repo.get(media_id)
    if not asset:
        raise EntityNotFoundError("MediaAsset", str(media_id))
    return asset


@router.post("/upload", response_model=MediaAssetResponse, status_code=status.HTTP_201_CREATED)
async def upload_media_record(
    brand_id: uuid.UUID,
    minio_bucket: str,
    minio_key: str,
    content_hash: str,
    mime_type: str,
    campaign_id: uuid.UUID | None = None,
    width: int | None = None,
    height: int | None = None,
    aspect_ratio: str | None = None,
    prompt_lineage: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.OPERATOR)),
):
    repo = MediaRepository(db)
    asset = await repo.create(
        brand_id=brand_id,
        campaign_id=campaign_id,
        minio_bucket=minio_bucket,
        minio_key=minio_key,
        content_hash=content_hash,
        mime_type=mime_type,
        width=width,
        height=height,
        aspect_ratio=aspect_ratio,
        prompt_lineage=prompt_lineage,
    )
    return asset
