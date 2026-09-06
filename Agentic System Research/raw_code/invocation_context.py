# File: invocation_context.py
"""
Layer 1: Invocation Context.

Ephemeral memory for one model inference or tool turn:
- Strictly token and size bounded.
- Stages data by lightweight reference (URI, UUID, hash) rather than full payload dumping.
- Isolated to the active turn and completely discarded afterward.
- Never serves as durable state or source of truth.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("invocation_context")


@dataclasses.dataclass(frozen=True)
class StagedReference:
    """Lightweight pointer referencing external evidence or artifacts."""
    reference_id: str
    uri: str
    content_hash: str
    summary_excerpt: str
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


class InvocationContext:
    """
    Disposable, token-budgeted working frame for a single inference or tool execution.
    Staged references point to out-of-context storage.
    """

    def __init__(self, invocation_id: str, task_id: str, agent_id: str,
                 token_budget: int = 4096, max_references: int = 10):
        self.invocation_id = invocation_id
        self.task_id = task_id
        self.agent_id = agent_id
        self.token_budget = token_budget
        self.max_references = max_references
        self.tokens_used = 0
        self._staged_references: Dict[str, StagedReference] = {}
        self._instructions: List[str] = []
        self.is_active = True
        self.created_at = datetime.now(timezone.utc)

    def stage_reference(self, uri: str, content_hash: str, summary: str,
                        metadata: Optional[Dict[str, Any]] = None) -> StagedReference:
        if not self.is_active:
            raise RuntimeError(f"Cannot stage references on disposed InvocationContext '{self.invocation_id}'.")
        if len(self._staged_references) >= self.max_references:
            raise ValueError(f"Max references limit reached ({self.max_references}) in InvocationContext.")

        ref_id = f"ref_{uuid.uuid4().hex[:8]}"
        ref = StagedReference(
            reference_id=ref_id,
            uri=uri,
            content_hash=content_hash,
            summary_excerpt=summary[:240],
            metadata=metadata or {}
        )
        self._staged_references[ref_id] = ref
        logger.debug("Staged reference %s (hash: %s) in invocation %s", ref_id, content_hash[:8], self.invocation_id)
        return ref

    def add_instruction(self, instruction_text: str) -> None:
        if not self.is_active:
            raise RuntimeError(f"Cannot add instructions to disposed InvocationContext '{self.invocation_id}'.")
        self._instructions.append(instruction_text)

    def consume_tokens(self, token_count: int) -> None:
        if not self.is_active:
            raise RuntimeError(f"Cannot record tokens on disposed InvocationContext '{self.invocation_id}'.")
        self.tokens_used += token_count
        if self.tokens_used > self.token_budget:
            logger.warning("Token budget exceeded in InvocationContext %s: %d > %d",
                           self.invocation_id, self.tokens_used, self.token_budget)

    def is_budget_exceeded(self) -> bool:
        return self.tokens_used > self.token_budget

    def render_prompt_context(self) -> str:
        """Renders lightweight, token-efficient references for model context ingress."""
        if not self.is_active:
            raise RuntimeError("Cannot render prompt context from disposed InvocationContext.")
        lines = [
            f"=== INVOCATION CONTEXT [ID: {self.invocation_id}] ===",
            "--- INSTRUCTIONS ---"
        ]
        lines.extend(self._instructions)
        lines.append("--- STAGED REFERENCES (Full bodies held in persistent store) ---")
        if not self._staged_references:
            lines.append("(No external references staged)")
        for ref in self._staged_references.values():
            lines.append(f"• [{ref.reference_id}] URI: {ref.uri} | Hash: {ref.content_hash[:12]}... | Summary: {ref.summary_excerpt}")
        return chr(10).join(lines)

    def dispose(self) -> None:
        """Explicitly purges volatile context memory to guarantee zero state retention."""
        self.is_active = False
        self._staged_references.clear()
        self._instructions.clear()
        logger.debug("InvocationContext %s successfully disposed.", self.invocation_id)