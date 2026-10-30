import uuid
from datetime import UTC, datetime
from typing import Any

from app.db.models.chat import ChatMessage, ChatSession
from app.db.repositories.base_repo import BaseRepository
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class ChatRepository(BaseRepository[ChatSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(ChatSession, db)
        self.db = db

    async def create_session(
        self,
        user_id: str,
        title: str = "New Orchestrator Chat",
        project_id: str | None = None,
        brand_id: uuid.UUID | None = None,
    ) -> ChatSession:
        session = ChatSession(
            user_id=str(user_id),
            title=title,
            project_id=project_id,
            brand_id=brand_id,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def list_sessions(
        self,
        user_id: str,
        is_pinned: bool | None = None,
        is_archived: bool | None = False,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatSession]:
        query = select(ChatSession).where(ChatSession.user_id == str(user_id))

        if is_pinned is not None:
            query = query.where(ChatSession.is_pinned == is_pinned)
        if is_archived is not None:
            query = query.where(ChatSession.is_archived == is_archived)
        if search:
            query = query.where(ChatSession.title.ilike(f"%{search}%"))

        query = query.order_by(desc(ChatSession.is_pinned), desc(ChatSession.updated_at))
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_session_with_messages(
        self,
        session_id: uuid.UUID,
        user_id: str | None = None,
    ) -> ChatSession | None:
        query = (
            select(ChatSession)
            .where(ChatSession.id == session_id)
            .options(selectinload(ChatSession.messages))
        )
        if user_id is not None:
            query = query.where(ChatSession.user_id == str(user_id))

        result = await self.db.execute(query)
        return result.scalars().first()

    async def update_session(
        self,
        session_id: uuid.UUID,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> ChatSession | None:
        session = await self.get(session_id)
        if not session:
            return None
        if user_id is not None and session.user_id != str(user_id):
            return None

        for k, v in kwargs.items():
            if v is not None and hasattr(session, k):
                setattr(session, k, v)
        session.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete_session(
        self,
        session_id: uuid.UUID,
        user_id: str | None = None,
    ) -> bool:
        session = await self.get(session_id)
        if not session:
            return False
        if user_id is not None and session.user_id != str(user_id):
            return False

        await self.db.delete(session)
        await self.db.commit()
        return True

    async def create_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        run_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            run_id=run_id,
            msg_metadata=metadata or {},
        )
        self.db.add(msg)

        # Touch parent session updated_at
        session = await self.get(session_id)
        if session:
            session.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def list_messages(
        self,
        session_id: uuid.UUID,
        limit: int = 100,
    ) -> list[ChatMessage]:
        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_messages(self, session_id: uuid.UUID) -> int:
        query = select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
        result = await self.db.execute(query)
        return int(result.scalar_one() or 0)
