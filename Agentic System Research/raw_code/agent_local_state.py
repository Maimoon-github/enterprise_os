# File: agent_local_state.py
"""
Layer 2: Agent-Local Working State.

Private volatile state for one agent instance:
- Stores intermediate calculations, hypotheses, parsing results, and candidate drafts.
- Strictly isolated to the owner agent; peer/sibling access is prohibited.
- Volatile process memory; never persisted as enterprise state without governed promotion.
- Enforces local bounds on scratchpad size and draft count.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent_local_state")


@dataclasses.dataclass(frozen=True)
class WorkingThought:
    thought_id: str
    timestamp: datetime
    content: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class DraftFragment:
    fragment_id: str
    label: str
    content: str
    timestamp: datetime


class AgentLocalWorkingState:
    """
    Private volatile scratchpad belonging exclusively to a single agent instance.
    Direct peer or sibling agent inspection is denied.
    """

    def __init__(self, agent_id: str, max_scratchpad_items: int = 100):
        self.agent_id = agent_id
        self.max_scratchpad_items = max_scratchpad_items
        self._thoughts: List[WorkingThought] = []
        self._calculations: Dict[str, Any] = {}
        self._drafts: Dict[str, DraftFragment] = {}
        self._created_at = datetime.now(timezone.utc)

    def _assert_owner(self, caller_agent_id: str) -> None:
        if caller_agent_id != self.agent_id:
            raise PermissionError(f"Unauthorized access: Agent '{caller_agent_id}' cannot inspect private state of '{self.agent_id}'.")

    def record_thought(self, caller_agent_id: str, content: str,
                       metadata: Optional[Dict[str, Any]] = None) -> WorkingThought:
        self._assert_owner(caller_agent_id)
        if len(self._thoughts) >= self.max_scratchpad_items:
            self._thoughts.pop(0)  # Bounded FIFO eviction of oldest local scratchpad entry

        thought = WorkingThought(
            thought_id=f"th_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc),
            content=content,
            metadata=metadata or {}
        )
        self._thoughts.append(thought)
        return thought

    def set_calculation(self, caller_agent_id: str, key: str, value: Any) -> None:
        self._assert_owner(caller_agent_id)
        self._calculations[key] = value

    def get_calculation(self, caller_agent_id: str, key: str, default: Any = None) -> Any:
        self._assert_owner(caller_agent_id)
        return self._calculations.get(key, default)

    def record_draft(self, caller_agent_id: str, label: str, content: str) -> DraftFragment:
        self._assert_owner(caller_agent_id)
        frag_id = f"df_{uuid.uuid4().hex[:8]}"
        fragment = DraftFragment(
            fragment_id=frag_id,
            label=label,
            content=content,
            timestamp=datetime.now(timezone.utc)
        )
        self._drafts[label] = fragment
        return fragment

    def get_draft(self, caller_agent_id: str, label: str) -> Optional[DraftFragment]:
        self._assert_owner(caller_agent_id)
        return self._drafts.get(label)

    def get_all_drafts(self, caller_agent_id: str) -> Dict[str, DraftFragment]:
        self._assert_owner(caller_agent_id)
        return dict(self._drafts)

    def clear(self, caller_agent_id: str) -> None:
        self._assert_owner(caller_agent_id)
        self._thoughts.clear()
        self._calculations.clear()
        self._drafts.clear()