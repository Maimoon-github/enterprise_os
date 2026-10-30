import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.repositories.base_repo import BaseRepository
from app.db.models.campaign import Campaign

class CampaignRepository(BaseRepository[Campaign]):
    def __init__(self, session: AsyncSession):
        super().__init__(Campaign, session)

    async def list_by_brand(self, brand_id: uuid.UUID) -> list[Campaign]:
        result = await self.session.execute(select(Campaign).where(Campaign.brand_id == brand_id))
        return list(result.scalars().all())
