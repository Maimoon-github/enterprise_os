"""Builds mandatory human-review action previews.

Every action preview this module produces defaults to
``requires_approval=True``; nothing downstream is permitted to construct an
``ActionPreview`` that skips human review.
"""

from __future__ import annotations

from app.orchestration.evidence_synthesis import SynthesizedEvidence
from app.schemas.action_preview import ActionPreview, ActionPreviewKind
from app.schemas.governance import RiskLevel


class HitlPreviewGenerator:
    """Builds an ``ActionPreview`` dossier from synthesized worker evidence."""

    def generate(
        self,
        *,
        preview_id: str,
        evidence: SynthesizedEvidence,
        kind: ActionPreviewKind,
        risk_level: RiskLevel,
        spend_amount: float | None = None,
        diff: str | None = None,
    ) -> ActionPreview:
        """Return a human-reviewable preview; approval is always required."""

        summary_lines = evidence.evidence[:5]
        summary = (
            f"Task {evidence.task_id}: confidence "
            f"{evidence.confidence.point_estimate:.2f} "
            f"[{evidence.confidence.lower_bound:.2f}, {evidence.confidence.upper_bound:.2f}]. "
            + " | ".join(summary_lines)
        )
        return ActionPreview(
            preview_id=preview_id,
            task_id=evidence.task_id,
            kind=kind,
            summary=summary,
            diff=diff,
            spend_amount=spend_amount,
            risk_level=risk_level,
            requires_approval=True,
        )