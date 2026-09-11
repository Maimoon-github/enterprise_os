"""Coordinates mandatory human approval and revision decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.exceptions import ApprovalRequiredError
from app.schemas.action_preview import ActionPreview


@dataclass
class ApprovalDecision:
    """The outcome of a human reviewer's decision on an action preview."""

    preview_id: str
    approved: bool
    approver: str
    decided_at: datetime
    revision_notes: str | None = None


class HitlCoordinator:
    """Tracks pending action previews and records human approval decisions.

    Persistence of decisions is delegated to callers (typically via
    ``app.services.provenance``); this coordinator owns only the in-flight
    approval workflow state.
    """

    def __init__(self) -> None:
        self._pending: dict[str, ActionPreview] = {}
        self._decisions: dict[str, ApprovalDecision] = {}

    def submit_for_approval(self, preview: ActionPreview) -> None:
        """Register ``preview`` as awaiting human review."""

        self._pending[preview.preview_id] = preview

    def is_pending(self, preview_id: str) -> bool:
        return preview_id in self._pending

    def decide(
        self,
        preview_id: str,
        *,
        approved: bool,
        approver: str,
        revision_notes: str | None = None,
    ) -> ApprovalDecision:
        """Record a human decision for a pending preview and return it."""

        if preview_id not in self._pending:
            raise ApprovalRequiredError(
                f"No pending action preview '{preview_id}' awaiting approval."
            )

        decision = ApprovalDecision(
            preview_id=preview_id,
            approved=approved,
            approver=approver,
            decided_at=datetime.now(UTC),
            revision_notes=revision_notes,
        )
        self._decisions[preview_id] = decision
        del self._pending[preview_id]
        return decision

    def get_decision(self, preview_id: str) -> ApprovalDecision | None:
        return self._decisions.get(preview_id)

    def require_approved(self, preview_id: str) -> ApprovalDecision:
        """Return the decision for ``preview_id``, raising if it was not approved."""

        decision = self._decisions.get(preview_id)
        if decision is None or not decision.approved:
            raise ApprovalRequiredError(
                f"Action preview '{preview_id}' has not been approved for dispatch."
            )
        return decision