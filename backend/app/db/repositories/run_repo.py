import uuid

from app.db.models.run import Run
from app.db.repositories.base_repo import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class RunRepository(BaseRepository[Run]):
    def __init__(self, session: AsyncSession):
        super().__init__(Run, session)

    async def get_by_thread_id(self, thread_id: str) -> Run | None:
        result = await self.session.execute(select(Run).where(Run.thread_id == thread_id))
        return result.scalars().first()

    async def list_by_campaign(self, campaign_id: uuid.UUID) -> list[Run]:
        result = await self.session.execute(select(Run).where(Run.campaign_id == campaign_id))
        return list(result.scalars().all())
