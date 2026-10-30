import uuid

from app.db.models.campaign import Campaign
from app.db.repositories.base_repo import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class CampaignRepository(BaseRepository[Campaign]):
    def __init__(self, session: AsyncSession):
        super().__init__(Campaign, session)

    async def list_by_brand(self, brand_id: uuid.UUID) -> list[Campaign]:
        result = await self.session.execute(select(Campaign).where(Campaign.brand_id == brand_id))
        return list(result.scalars().all())
