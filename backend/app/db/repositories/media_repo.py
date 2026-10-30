import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.repositories.base_repo import BaseRepository
from app.db.models.media_asset import MediaAsset

class MediaRepository(BaseRepository[MediaAsset]):
    def __init__(self, session: AsyncSession):
        super().__init__(MediaAsset, session)

    async def get_by_hash(self, content_hash: str) -> MediaAsset | None:
        result = await self.session.execute(select(MediaAsset).where(MediaAsset.content_hash == content_hash))
        return result.scalars().first()

    async def list_by_campaign(self, campaign_id: uuid.UUID) -> list[MediaAsset]:
        result = await self.session.execute(select(MediaAsset).where(MediaAsset.campaign_id == campaign_id))
        return list(result.scalars().all())
