from app.db.models.brand import Brand
from app.db.repositories.base_repo import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class BrandRepository(BaseRepository[Brand]):
    def __init__(self, session: AsyncSession):
        super().__init__(Brand, session)

    async def get_by_slug(self, slug: str) -> Brand | None:
        result = await self.session.execute(select(Brand).where(Brand.slug == slug))
        return result.scalars().first()
