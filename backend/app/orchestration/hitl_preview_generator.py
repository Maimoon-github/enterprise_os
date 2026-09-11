"""Builds mandatory human-review action previews."""
from __future__ import annotations

from uuid import uuid4

from app.schemas.action_preview import ActionPreview, PreviewKind


class HitlPreviewGenerator:
    def generate(
        self,
        task_id: str,
        tenant_id: str,
        kind: PreviewKind,
        summary: str,
        **extra,
    ) -> ActionPreview:
        return ActionPreview(
            preview_id=str(uuid4()),
            task_id=task_id,
            tenant_id=tenant_id,
            kind=kind,
            summary=summary,
            **extra,
        )
