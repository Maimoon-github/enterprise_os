from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.schemas.brand import BrandCreate, BrandResponse
from app.db.repositories.base_repo import BaseRepository
from app.db.models.brand import Brand

router = APIRouter()

@router.get("", response_model=list[BrandResponse])
async def list_brands(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    repo = BaseRepository(Brand, db)
    return await repo.list_all()

@router.post("", response_model=BrandResponse, status_code=201)
async def create_brand(payload: BrandCreate, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    repo = BaseRepository(Brand, db)
    return await repo.create(**payload.model_dump())
