# File: session_memory.py
"""
Layer 3: Session / Short-Term Memory.

Task/workstream-scoped state spanning active execution:
- Partitioned strictly by tenant_id and task_id.
- Isolated per active workstream; cross-tenant and cross-task leakage prohibited.
- Tracks intermediate milestones, task observations, and coordinating state.
- Evicts or archives upon task completion or cancellation.
"""

from __future__ import annotations

import dataclasses
import enum
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("session_memory")


class SessionEntryType(str, enum.Enum):
    OBSERVATION = "OBSERVATION"
    MILESTONE = "MILESTONE"
    PROPOSAL = "PROPOSAL"
    COORDINATION = "COORDINATION"


@dataclasses.dataclass(frozen=True)
class SessionEntry:
    entry_id: str
    timestamp: datetime
    agent_id: str
    entry_type: SessionEntryType
    content: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


class SessionMemory:
    """
    Task-scoped scratchpad for an active execution lifecycle.
    Enforces strict tenant and task boundaries.
    """

    def __init__(self, session_id: str, task_id: str, worker_id: str, tenant_id: str):
        self.session_id = session_id
        self.task_id = task_id
        self.worker_id = worker_id
        self.tenant_id = tenant_id
        self._scratchpad: List[SessionEntry] = []
        self._created_at = datetime.now(timezone.utc)
        self._is_archived = False

    def _assert_access(self, requesting_tenant_id: str, requesting_task_id: str,
                       requesting_worker_id: str) -> None:
        if self._is_archived:
            raise RuntimeError(f"Session '{self.session_id}' has been archived.")
        if requesting_tenant_id != self.tenant_id:
            raise PermissionError(f"Tenant isolation breach: caller tenant '{requesting_tenant_id}' != session tenant '{self.tenant_id}'")
        if requesting_task_id != self.task_id:
            raise PermissionError(f"Task isolation breach: caller task '{requesting_task_id}' != session task '{self.task_id}'")
        if requesting_worker_id != self.worker_id:
            raise PermissionError(f"Cross-worker session access denied: worker '{requesting_worker_id}' cannot access session of '{self.worker_id}'")

    def record_entry(self, requesting_tenant_id: str, requesting_task_id: str,
                     requesting_worker_id: str, entry_type: SessionEntryType,
                     content: str, metadata: Optional[Dict[str, Any]] = None) -> SessionEntry:
        self._assert_access(requesting_tenant_id, requesting_task_id, requesting_worker_id)
        entry = SessionEntry(
            entry_id=f"ses_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc),
            agent_id=requesting_worker_id,
            entry_type=entry_type,
            content=content,
            metadata=metadata or {}
        )
        self._scratchpad.append(entry)
        logger.debug("Recorded session entry %s for task %s (type: %s)", entry.entry_id, self.task_id, entry_type.value)
        return entry

    def get_entries(self, requesting_tenant_id: str, requesting_task_id: str,
                    requesting_worker_id: str) -> List[SessionEntry]:
        self._assert_access(requesting_tenant_id, requesting_task_id, requesting_worker_id)
        return list(self._scratchpad)

    def archive(self, requesting_tenant_id: str, requesting_task_id: str,
                requesting_worker_id: str) -> List[SessionEntry]:
        """Archives and evicts active session memory upon task completion/cancellation."""
        self._assert_access(requesting_tenant_id, requesting_task_id, requesting_worker_id)
        archived_copy = list(self._scratchpad)
        self._scratchpad.clear()
        self._is_archived = True
        logger.info("Session %s for task %s archived and evicted.", self.session_id, self.task_id)
        return archived_copy