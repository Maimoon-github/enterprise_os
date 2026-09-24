"""Verifies mandatory approval for spend, claims, code, and dispatch."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.exceptions import ApprovalRequiredError
from app.schemas.action_preview import ActionPreview, ActionPreviewKind
from app.schemas.governance import RiskLevel
from app.services.hitl import HitlCoordinator


def _preview(kind: ActionPreviewKind, **kwargs: Any) -> ActionPreview:
    return ActionPreview(
        preview_id="preview-1",
        task_id="task-1",
        kind=kind,
        summary="proposed action",
        risk_level=RiskLevel.MEDIUM,
        **kwargs,
    )


@pytest.mark.parametrize(
    "kind, kwargs",
    [
        (ActionPreviewKind.SPEND, {"spend_amount": 500.0}),
        (ActionPreviewKind.CLAIM, {}),
        (ActionPreviewKind.COPY, {}),
        (ActionPreviewKind.CODE_DIFF, {"diff": "+ added line"}),
    ],
)
def test_action_preview_always_requires_approval(kind: ActionPreviewKind, kwargs: dict) -> None:
    preview = _preview(kind, **kwargs)

    assert preview.requires_approval is True


def test_hitl_coordinator_blocks_dispatch_without_decision() -> None:
    coordinator = HitlCoordinator()
    coordinator.submit_for_approval(_preview(ActionPreviewKind.SPEND, spend_amount=100.0))

    with pytest.raises(ApprovalRequiredError):
        coordinator.require_approved("preview-1")


def test_hitl_coordinator_blocks_dispatch_after_rejection() -> None:
    coordinator = HitlCoordinator()
    coordinator.submit_for_approval(_preview(ActionPreviewKind.CLAIM))

    coordinator.decide("preview-1", approved=False, approver="[email protected]")

    with pytest.raises(ApprovalRequiredError):
        coordinator.require_approved("preview-1")


def test_hitl_coordinator_allows_dispatch_after_approval() -> None:
    coordinator = HitlCoordinator()
    coordinator.submit_for_approval(_preview(ActionPreviewKind.CODE_DIFF, diff="+ line"))

    coordinator.decide("preview-1", approved=True, approver="[email protected]")
    decision = coordinator.require_approved("preview-1")

    assert decision.approved is True
    assert decision.approver == "[email protected]"


def test_deciding_on_unknown_preview_raises() -> None:
    coordinator = HitlCoordinator()

    with pytest.raises(ApprovalRequiredError):
        coordinator.decide("does-not-exist", approved=True, approver="[email protected]")


def test_hitl_coordinator_blocks_dispatch_on_hold() -> None:
    coordinator = HitlCoordinator()
    coordinator.submit_for_approval(_preview(ActionPreviewKind.SPEND, spend_amount=250.0))

    decision = coordinator.decide("preview-1", decision="HOLD", approver="[email protected]", approver_role="finance")
    assert decision.approved is False
    assert decision.clearance is not None
    assert decision.clearance.is_valid is False

    with pytest.raises(ApprovalRequiredError, match="strictly blocked"):
        coordinator.require_approved("preview-1")


def test_hitl_coordinator_invalidate_approval_blocks_dispatch() -> None:
    coordinator = HitlCoordinator()
    coordinator.submit_for_approval(_preview(ActionPreviewKind.CLAIM))

    coordinator.decide("preview-1", decision="APPROVE", approver="[email protected]", approver_role="legal")
    assert coordinator.require_approved("preview-1").approved is True

    coordinator.invalidate_approval("preview-1", reason="Underlying strategy revised")
    with pytest.raises(ApprovalRequiredError, match="strictly blocked"):
        coordinator.require_approved("preview-1")