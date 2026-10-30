from app.api.deps import get_current_user, get_db
from app.db.models.brand import Brand
from app.db.repositories.base_repo import BaseRepository
from app.schemas.brand import BrandCreate, BrandResponse
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.get("", response_model=list[BrandResponse])
async def list_brands(db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    repo = BaseRepository(Brand, db)
    return await repo.list_all()

@router.post("", response_model=BrandResponse, status_code=201)
async def create_brand(payload: BrandCreate, db: AsyncSession = Depends(get_db), current_user: dict = Depends(get_current_user)):
    repo = BaseRepository(Brand, db)
    return await repo.create(**payload.model_dump())
