from datetime import UTC, datetime
from typing import Any

from app.db.models.platform_connection import PlatformConnection
from app.db.repositories.base_repo import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class PlatformConnectionRepository(BaseRepository[PlatformConnection]):
    def __init__(self, db: AsyncSession):
        super().__init__(PlatformConnection, db)
        self.db = db

    async def get_by_platform(self, platform: str) -> PlatformConnection | None:
        query = select(PlatformConnection).where(PlatformConnection.platform == platform.lower())
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_connections(self) -> list[PlatformConnection]:
        query = select(PlatformConnection).order_by(PlatformConnection.platform.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def upsert_connection(
        self,
        platform: str,
        encrypted_credentials: str | None = None,
        account_name: str | None = None,
        connection_settings: dict[str, Any] | None = None,
        is_connected: bool = True,
    ) -> PlatformConnection:
        existing = await self.get_by_platform(platform)
        now = datetime.now(UTC)

        if existing:
            existing.is_connected = is_connected
            if encrypted_credentials is not None:
                existing.encrypted_credentials = encrypted_credentials
            if account_name is not None:
                existing.account_name = account_name
            if connection_settings is not None:
                existing.settings = connection_settings
            existing.last_synced_at = now
            existing.updated_at = now
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        new_conn = PlatformConnection(
            platform=platform.lower(),
            is_connected=is_connected,
            account_name=account_name,
            encrypted_credentials=encrypted_credentials,
            settings=connection_settings or {},
            last_synced_at=now,
        )
        self.db.add(new_conn)
        await self.db.commit()
        await self.db.refresh(new_conn)
        return new_conn

    async def disconnect(self, platform: str) -> bool:
        existing = await self.get_by_platform(platform)
        if not existing:
            return False

        existing.is_connected = False
        existing.encrypted_credentials = None
        existing.account_name = None
        existing.updated_at = datetime.now(UTC)
        await self.db.commit()
        return True
