"""Asynchronous in-memory scratchpad with TTL-based state storage and stage-level buffer management."""

import asyncio
import time
from typing import Any, Dict, Optional


class ShortTermMemory:
    """Intra-session working memory and transient buffer manager."""

    def __init__(self, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._stage_buffers: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Stores a value with optional TTL in seconds."""
        async with self._lock:
            self._store[key] = value
            expiry_time = time.time() + (ttl if ttl is not None else self.default_ttl)
            self._expiry[key] = expiry_time

    async def get(self, key: str) -> Optional[Any]:
        """Retrieves an unexpired value, purging if expired."""
        async with self._lock:
            if key not in self._store:
                return None
            if time.time() > self._expiry.get(key, 0):
                self._store.pop(key, None)
                self._expiry.pop(key, None)
                return None
            return self._store[key]

    async def delete(self, key: str) -> bool:
        """Deletes a key from storage."""
        async with self._lock:
            removed = self._store.pop(key, None) is not None
            self._expiry.pop(key, None)
            return removed

    async def save_stage_buffer(self, session_id: str, stage: str, data: Any) -> None:
        """Buffers intermediate stage execution artifacts."""
        async with self._lock:
            if session_id not in self._stage_buffers:
                self._stage_buffers[session_id] = {}
            self._stage_buffers[session_id][stage] = data

    async def get_stage_buffer(self, session_id: str, stage: str) -> Optional[Any]:
        """Retrieves execution artifacts from a completed stage."""
        async with self._lock:
            return self._stage_buffers.get(session_id, {}).get(stage)

    async def clear_session(self, session_id: str) -> None:
        """Purges transient buffers for a session."""
        async with self._lock:
            self._stage_buffers.pop(session_id, None)
