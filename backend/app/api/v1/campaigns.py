from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.schemas.campaign import CampaignCreate, CampaignResponse
from app.db.repositories.base_repo import BaseRepository
from app.db.models.campaign import Campaign

router = APIRouter()

@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    repo = BaseRepository(Campaign, db)
    return await repo.list_all()

@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(payload: CampaignCreate, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    repo = BaseRepository(Campaign, db)
    return await repo.create(
        brand_id=payload.brand_id,
        name=payload.name,
        objective=payload.objective,
        created_by=current_user["id"],
        status="draft",
    )
