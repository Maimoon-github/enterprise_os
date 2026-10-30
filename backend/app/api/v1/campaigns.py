import contextlib
import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.exceptions import EntityNotFoundError
from app.core.rbac import UserRole
from app.db.repositories.campaign_repo import CampaignRepository
from app.schemas.campaign import CampaignCreate, CampaignResponse, CampaignUpdate
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(
    brand_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    repo = CampaignRepository(db)
    if brand_id:
        return await repo.list_by_brand(brand_id)
    return await repo.list_all(limit=limit, offset=offset)


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.EDITOR)),
):
    repo = CampaignRepository(db)
    user_id = None
    with contextlib.suppress(ValueError, TypeError):
        user_id = uuid.UUID(current_user["id"])

    campaign = await repo.create(

        brand_id=payload.brand_id,
        name=payload.name,
        objective=payload.objective,
        blueprint={"target_platforms": payload.target_platforms} if payload.target_platforms else None,
        created_by=user_id,
        status="draft",
    )
    return campaign


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    repo = CampaignRepository(db)
    campaign = await repo.get(campaign_id)
    if not campaign:
        raise EntityNotFoundError("Campaign", str(campaign_id))
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.EDITOR)),
):
    repo = CampaignRepository(db)
    campaign = await repo.get(campaign_id)
    if not campaign:
        raise EntityNotFoundError("Campaign", str(campaign_id))

    update_data = payload.model_dump(exclude_unset=True)
    updated = await repo.update(campaign_id, **update_data)
    return updated or campaign
