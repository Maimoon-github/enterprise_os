import logging
from collections.abc import Sequence
from typing import Any

from app.core.config import settings
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger("orchestrator.checkpointer")

_checkpointer_instance: BaseCheckpointSaver | None = None
_pool_instance: AsyncConnectionPool | None = None


def normalize_postgres_url(url: str) -> str:
    """Normalize async SQLAlchemy postgresql+asyncpg:// URL to standard psycopg postgresql:// conninfo."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


class DynamicCheckpointer(BaseCheckpointSaver):
    """Dynamic checkpointer proxy that delegates all synchronous and asynchronous operations

    to the active checkpointer instance (AsyncPostgresSaver in production, MemorySaver in tests).
    """

    def __init__(self, checkpointer_getter=None):
        super().__init__()
        self._getter = checkpointer_getter or get_checkpointer

    @property
    def target(self) -> BaseCheckpointSaver:
        return self._getter()

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return self.target.get_tuple(config)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        return await self.target.aget_tuple(config)

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ):
        return self.target.list(config, filter=filter, before=before, limit=limit)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ):
        return await self.target.alist(config, filter=filter, before=before, limit=limit)

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self.target.put(config, checkpoint, metadata, new_versions)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await self.target.aput(config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        return self.target.put_writes(config, writes, task_id)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        return await self.target.aput_writes(config, writes, task_id)


async def init_checkpointer() -> BaseCheckpointSaver:
    """Initialize the PostgreSQL checkpointer pool and run schema migration/setup().

    Falls back cleanly to an in-memory saver if PostgreSQL connection cannot be established.
    """
    global _checkpointer_instance, _pool_instance
    if _checkpointer_instance is not None and not isinstance(_checkpointer_instance, MemorySaver):
        return _checkpointer_instance

    conn_str = normalize_postgres_url(settings.SYNC_DATABASE_URL or settings.DATABASE_URL)
    try:
        pool = AsyncConnectionPool(
            conninfo=conn_str,
            max_size=20,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row},
        )
        await pool.open()
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        _pool_instance = pool
        _checkpointer_instance = saver
        logger.info("LangGraph AsyncPostgresSaver checkpointer initialized with schema setup.")
        return saver
    except Exception as exc:
        logger.warning(
            "Failed to initialize PostgreSQL checkpointer (%s). Falling back to MemorySaver.",
            exc,
        )
        _checkpointer_instance = MemorySaver()
        return _checkpointer_instance


async def close_checkpointer() -> None:
    """Tear down database connection pool during application shutdown."""
    global _checkpointer_instance, _pool_instance
    if _pool_instance is not None:
        await _pool_instance.close()
        _pool_instance = None
    _checkpointer_instance = None


def get_checkpointer() -> BaseCheckpointSaver:
    """Return the active checkpointer or an in-memory fallback for isolated test execution."""
    global _checkpointer_instance
    if _checkpointer_instance is None:
        _checkpointer_instance = MemorySaver()
    return _checkpointer_instance
