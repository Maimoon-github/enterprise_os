from app.db.models.approval import Approval
from app.db.repositories.base_repo import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class ApprovalRepository(BaseRepository[Approval]):
    def __init__(self, session: AsyncSession):
        super().__init__(Approval, session)

    async def list_pending(self) -> list[Approval]:
        result = await self.session.execute(select(Approval).where(Approval.status == "pending"))
        return list(result.scalars().all())

    async def get_by_thread(self, thread_id: str) -> Approval | None:
        result = await self.session.execute(select(Approval).where(Approval.thread_id == thread_id))
        return result.scalars().first()
