"""Comprehensive verification suite for Milestone 6 (M6) Acceptance Checkpoint.

M6 verifies the outbound actuation, telemetry & omnichannel go-live boundary:
T25 (Outbound Boundary) + T26 (Website/CMS) + T27 (Paid Ads) + T28 (Social) + T29 (Telemetry) -> M6 COMPLETE -> T30 Eligible
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import pytest

from app.orchestration.dag_scheduler import DagScheduler
from app.schemas.dispatch import (
    CmsDeploymentResult,
    PaidCampaignDeploymentResult,
    SocialPostDeploymentResult,
)
from app.schemas.governance import WorkerRole
from app.schemas.task_state import (
    CanonicalTaskState,
    MilestoneStatus,
    TaskDependency,
    TaskStatus,
)
from app.schemas.telemetry import (
    OmnichannelTelemetryReadiness,
    TelemetryHandshakeProbe,
    TelemetrySourceType,
    TelemetrySurface,
)
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class _FakeTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task {task_id} not found")
        return self.states[task_id]


def _build_valid_m6_fixtures(
    tenant_id: str = "tenant-alpha",
) -> tuple[
    TaskStateService,
    CanonicalTaskState,
    CanonicalTaskState,
    CanonicalTaskState,
    CanonicalTaskState,
    CanonicalTaskState,
    CmsDeploymentResult,
    PaidCampaignDeploymentResult,
    SocialPostDeploymentResult,
    OmnichannelTelemetryReadiness,
    FakeProvenanceRepository,
]:
    repo = _FakeTaskStateRepository()
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    service = TaskStateService(repo, provenance_recorder=prov_recorder)

    t25 = CanonicalTaskState(
        task_id="task-t25",
        directive_id="dir-1",
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.COMPLETED,
        cts_state={"tenant_id": tenant_id},
        governance_approved=True,
    )
    t26 = CanonicalTaskState(
        task_id="task-t26",
        directive_id="dir-1",
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.COMPLETED,
        cts_state={"tenant_id": tenant_id},
        governance_approved=True,
    )
    t27 = CanonicalTaskState(
        task_id="task-t27",
        directive_id="dir-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.COMPLETED,
        cts_state={"tenant_id": tenant_id},
        governance_approved=True,
    )
    t28 = CanonicalTaskState(
        task_id="task-t28",
        directive_id="dir-1",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.COMPLETED,
        cts_state={"tenant_id": tenant_id},
        governance_approved=True,
    )
    t29 = CanonicalTaskState(
        task_id="task-t29",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.COMPLETED,
        cts_state={"tenant_id": tenant_id},
        governance_approved=True,
    )

    repo.states[t25.task_id] = t25
    repo.states[t26.task_id] = t26
    repo.states[t27.task_id] = t27
    repo.states[t28.task_id] = t28
    repo.states[t29.task_id] = t29

    cms_dep = CmsDeploymentResult(
        deployment_id="dep-cms-1",
        dispatch_id="disp-cms-1",
        task_id="task-t26",
        tenant_id=tenant_id,
        channel="cms",
        action_type="publish",
        status_code="200",
        status="published",
        applied_items=[{"path": "/home", "version": "v1.0"}],
        applied_hashes=["sha256-hash-cms"],
    )

    paid_dep = PaidCampaignDeploymentResult(
        deployment_id="dep-paid-1",
        dispatch_id="disp-paid-1",
        task_id="task-t27",
        tenant_id=tenant_id,
        channel="meta",
        action_type="publish",
        campaign_id="meta-camp-100",
        status_code="200",
        status="published",
        applied_budget=1500.0,
        applied_bid=2.50,
        creative_refs=["creative-ad-1"],
        details={"approved_budget": 2000.0, "approved_bid": 3.00},
    )

    social_dep = SocialPostDeploymentResult(
        deployment_id="dep-soc-1",
        dispatch_id="disp-soc-1",
        task_id="task-t28",
        tenant_id=tenant_id,
        channel="instagram",
        action_type="publish",
        post_id="ig-post-200",
        status_code="200",
        status="published",
        content_hash="hash-clean-post",
        media_asset_ids=["asset-img-1"],
    )

    telemetry_readiness = OmnichannelTelemetryReadiness(
        readiness_id="readiness-t29-1",
        tenant_id=tenant_id,
        is_ready=True,
        dependencies={"t26": "dep-cms-1", "t27": "dep-paid-1", "t28": "dep-soc-1"},
        active_surfaces=[
            TelemetrySurface(channel="cms", source_type=TelemetrySourceType.WEBHOOK, endpoint="https://telemetry.enterprise.os/cms", tenant_id=tenant_id, is_active=True),
            TelemetrySurface(channel="meta", source_type=TelemetrySourceType.WEBHOOK, endpoint="https://telemetry.enterprise.os/meta", tenant_id=tenant_id, is_active=True),
            TelemetrySurface(channel="instagram", source_type=TelemetrySourceType.WEBHOOK, endpoint="https://telemetry.enterprise.os/instagram", tenant_id=tenant_id, is_active=True),
        ],
        probes=[
            TelemetryHandshakeProbe(channel="cms", source_type=TelemetrySourceType.WEBHOOK, success=True),
            TelemetryHandshakeProbe(channel="meta", source_type=TelemetrySourceType.WEBHOOK, success=True),
            TelemetryHandshakeProbe(channel="instagram", source_type=TelemetrySourceType.WEBHOOK, success=True),
        ],
        blocked_reasons=[],
    )

    return (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        prov_repo,
    )


@pytest.mark.asyncio
async def test_m6_complete_when_all_t25_t29_accepted_and_verified() -> None:
    """M6 evaluates to COMPLETE when T25-T29 and all deployments and telemetry readiness are valid."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        prov_repo,
    ) = _build_valid_m6_fixtures()

    checkpoint = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )

    assert checkpoint.milestone_id == "M6"
    assert checkpoint.status == MilestoneStatus.COMPLETE
    assert len(checkpoint.blockers) == 0
    assert checkpoint.metadata["t30_eligible"] is True
    assert checkpoint.metadata["active_surfaces_count"] == 3

    # Check that T29 CTS state was updated with milestone_m6
    saved_t29 = await service.get_state(t29.task_id)
    assert "milestone_m6" in saved_t29.cts_state
    assert saved_t29.cts_state["milestone_m6"]["status"] == "complete"
    assert saved_t29.cts_state["milestone_m6"]["metadata"]["t30_eligible"] is True

    # Check provenance event recorded
    records = await prov_repo.chain("tenant-alpha")
    m6_events = [r for r in records if r.activity == "milestone_checkpoint_m6"]
    assert len(m6_events) == 1
    assert m6_events[0].metadata["status"] == "complete"
    assert m6_events[0].metadata["t30_eligible"] is True


@pytest.mark.asyncio
async def test_m6_partial_when_any_task_missing_or_in_progress() -> None:
    """M6 evaluates to PARTIAL when an upstream task is missing or in progress."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    # Case 1: T28 missing
    checkpoint_missing = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=None,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert checkpoint_missing.status == MilestoneStatus.PARTIAL
    assert checkpoint_missing.metadata["t30_eligible"] is False
    assert any("T28 task state missing" in b for b in checkpoint_missing.blockers)

    # Case 2: T27 IN_PROGRESS
    t27_in_progress = t27.model_copy(update={"status": TaskStatus.IN_PROGRESS})
    checkpoint_in_prog = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27_in_progress,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert checkpoint_in_prog.status == MilestoneStatus.PARTIAL
    assert checkpoint_in_prog.metadata["t30_eligible"] is False
    assert any("T27 is not completed" in b for b in checkpoint_in_prog.blockers)


@pytest.mark.asyncio
async def test_m6_failed_when_any_linked_task_failed() -> None:
    """M6 evaluates to FAILED when any linked task or critical deployment reports failure."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    # Task T26 FAILED
    t26_failed = t26.model_copy(update={"status": TaskStatus.FAILED})
    cp_task_failed = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26_failed,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert cp_task_failed.status == MilestoneStatus.FAILED
    assert cp_task_failed.metadata["t30_eligible"] is False
    assert any("T26 is in failed state" in b for b in cp_task_failed.blockers)

    # Deployment record failed (CMS 500 error)
    cms_dep_failed = cms_dep.model_copy(update={"status": "failed", "status_code": "500"})
    cp_dep_failed = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep_failed,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert cp_dep_failed.status == MilestoneStatus.FAILED
    assert cp_dep_failed.metadata["t30_eligible"] is False
    assert any("T26 CMS deployment failed" in b for b in cp_dep_failed.blockers)


@pytest.mark.asyncio
async def test_m6_blocked_when_task_held_or_locked() -> None:
    """M6 evaluates to BLOCKED when a task is HELD or has active locks."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    t25_held = t25.model_copy(update={"status": TaskStatus.HELD, "hold_reason": "Security review underway"})
    checkpoint = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25_held,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert checkpoint.metadata["t30_eligible"] is False
    assert any("T25 is HELD" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m6_blocked_on_tenant_mismatch() -> None:
    """M6 evaluates to BLOCKED when any task or deployment record belongs to an unexpected tenant."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    t27_diff_tenant = t27.model_copy(update={"cts_state": {"tenant_id": "tenant-rogue"}})
    checkpoint = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27_diff_tenant,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert any("T27 tenant mismatch" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m6_blocked_on_unauthorized_ad_platform() -> None:
    """M6 evaluates to BLOCKED when an unsupported ad platform or unauthorized LinkedIn deployment is present."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    # 1. Unsupported platform
    unsupported_paid = paid_dep.model_copy(update={"channel": "snapchat"})
    cp_unsupported = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=unsupported_paid,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert cp_unsupported.status == MilestoneStatus.BLOCKED
    assert any("not a permitted canonical ad platform" in b for b in cp_unsupported.blockers)

    # 2. LinkedIn without explicit authorization
    unauth_linkedin = paid_dep.model_copy(update={"channel": "linkedin", "details": {}})
    cp_linkedin_unauth = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=unauth_linkedin,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert cp_linkedin_unauth.status == MilestoneStatus.BLOCKED
    assert any("platform 'linkedin' was deployed without explicit authorization" in b for b in cp_linkedin_unauth.blockers)

    # 3. LinkedIn with explicit authorization passes
    auth_linkedin = paid_dep.model_copy(update={"channel": "linkedin", "details": {"authorized": True}})
    cp_linkedin_auth = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=auth_linkedin,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert cp_linkedin_auth.status == MilestoneStatus.COMPLETE


@pytest.mark.asyncio
async def test_m6_blocked_on_unauthorized_social_channel() -> None:
    """M6 evaluates to BLOCKED when an unsupported social channel or unauthorized TikTok social deployment is present."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    # 1. Unsupported channel
    unsupported_soc = social_dep.model_copy(update={"channel": "threads"})
    cp_unsupported = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=unsupported_soc,
        telemetry_readiness=telemetry_readiness,
    )
    assert cp_unsupported.status == MilestoneStatus.BLOCKED
    assert any("not a permitted canonical social channel" in b for b in cp_unsupported.blockers)

    # 2. TikTok without explicit authorization
    unauth_tiktok = social_dep.model_copy(update={"channel": "tiktok", "details": {}})
    cp_tiktok_unauth = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=unauth_tiktok,
        telemetry_readiness=telemetry_readiness,
    )
    assert cp_tiktok_unauth.status == MilestoneStatus.BLOCKED
    assert any("channel 'tiktok' was published without explicit authorization" in b for b in cp_tiktok_unauth.blockers)

    # 3. TikTok with explicit authorization passes
    auth_tiktok = social_dep.model_copy(update={"channel": "tiktok", "details": {"authorized": True}})
    cp_tiktok_auth = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=auth_tiktok,
        telemetry_readiness=telemetry_readiness,
    )
    assert cp_tiktok_auth.status == MilestoneStatus.COMPLETE


@pytest.mark.asyncio
async def test_m6_blocked_on_telemetry_listener_probe_failure() -> None:
    """M6 evaluates to BLOCKED when telemetry engine readiness reports probe or listener failure."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    failing_telemetry = telemetry_readiness.model_copy(
        update={
            "is_ready": False,
            "blocked_reasons": ["Meta webhook secret verification timed out", "Instagram listener unhealthy"],
        }
    )

    checkpoint = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=failing_telemetry,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert checkpoint.metadata["t30_eligible"] is False
    assert any("T29 telemetry engine is not ready" in b for b in checkpoint.blockers)
    assert any("T29 probe failure: Meta webhook secret verification timed out" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m6_blocked_on_spend_or_bid_escalation() -> None:
    """M6 evaluates to BLOCKED when paid media deployment exceeds approved spend or bid caps."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    # Applied budget 5000.0 exceeds approved 2000.0
    escalated_paid = paid_dep.model_copy(
        update={
            "applied_budget": 5000.0,
            "details": {"approved_budget": 2000.0, "approved_bid": 3.0},
        }
    )

    checkpoint = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=escalated_paid,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert any("T27 spend escalation: applied 5000.0 > approved 2000.0" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m6_blocked_on_tampered_copy_or_media_asset() -> None:
    """M6 evaluates to BLOCKED when social deployment reports tampered copy or assets."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    tampered_social = social_dep.model_copy(update={"details": {"tampered": True}})

    checkpoint = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=tampered_social,
        telemetry_readiness=telemetry_readiness,
    )

    assert checkpoint.status == MilestoneStatus.BLOCKED
    assert any("T28 social post copy or media asset was tampered" in b for b in checkpoint.blockers)


@pytest.mark.asyncio
async def test_m6_evaluation_deterministic_and_idempotent() -> None:
    """Multiple evaluations of identical state produce identical milestone checkpoints."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    cp1 = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )

    cp2 = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )

    assert cp1.status == cp2.status == MilestoneStatus.COMPLETE
    assert cp1.blockers == cp2.blockers == []
    assert cp1.metadata == cp2.metadata


@pytest.mark.asyncio
async def test_m6_invalidated_when_linked_task_reopened() -> None:
    """Transitioning an approved task back to HELD/IN_PROGRESS invalidates M6 completion."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        _,
    ) = _build_valid_m6_fixtures()

    initial = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )
    assert initial.status == MilestoneStatus.COMPLETE

    # Reopen T26 to HELD for emergency hotfix
    t26_reopened = t26.model_copy(update={"status": TaskStatus.HELD, "hold_reason": "Emergency rollback"})

    reopened_cp = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26_reopened,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )

    assert reopened_cp.status == MilestoneStatus.BLOCKED
    assert reopened_cp.metadata["t30_eligible"] is False
    assert any("T26 is HELD" in b for b in reopened_cp.blockers)


def test_m6_preserves_t29_to_t30_dag_dependency() -> None:
    """T30 execution eligibility is governed strictly by canonical DAG dependency on T29, not M6."""
    scheduler = DagScheduler()

    t29 = CanonicalTaskState(
        task_id="task-t29",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.IN_PROGRESS,
    )
    t30 = CanonicalTaskState(
        task_id="task-t30",
        directive_id="dir-1",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.PENDING,
        dependencies=[TaskDependency(upstream_task_id="task-t29", downstream_task_id="task-t30")],
    )

    # When T29 is IN_PROGRESS, T30 is not ready
    ready = scheduler.next_ready_tasks([t29, t30])
    assert t30 not in ready

    # When T29 is COMPLETED, T30 becomes ready via direct DAG edge
    t29_completed = t29.model_copy(update={"status": TaskStatus.COMPLETED})
    ready_after = scheduler.next_ready_tasks([t29_completed, t30])
    assert t30 in ready_after


@pytest.mark.asyncio
async def test_m6_zero_t30_ingestion_execution() -> None:
    """M6 evaluates acceptance state without executing any live T30 telemetry ingestion into CDB."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        prov_repo,
    ) = _build_valid_m6_fixtures()

    checkpoint = await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )

    assert checkpoint.status == MilestoneStatus.COMPLETE

    # Verify provenance activity contains zero live ingestion records (T30)
    records = await prov_repo.chain("tenant-alpha")
    for record in records:
        assert "t30" not in record.activity.lower()
        assert "live_ingest" not in record.activity.lower()
        assert "cdb_write" not in record.activity.lower()


@pytest.mark.asyncio
async def test_m6_secret_redaction_in_provenance() -> None:
    """M6 evaluation does not leak sensitive tokens, keys, or payloads into provenance."""
    (
        service,
        t25,
        t26,
        t27,
        t28,
        t29,
        cms_dep,
        paid_dep,
        social_dep,
        telemetry_readiness,
        prov_repo,
    ) = _build_valid_m6_fixtures()

    await service.evaluate_m6_checkpoint(
        tenant_id="tenant-alpha",
        t25_task=t25,
        t26_task=t26,
        t27_task=t27,
        t28_task=t28,
        t29_task=t29,
        cms_deployment=cms_dep,
        paid_deployment=paid_dep,
        social_deployment=social_dep,
        telemetry_readiness=telemetry_readiness,
    )

    records = await prov_repo.chain("tenant-alpha")
    for record in records:
        metadata_str = str(record.metadata).lower()
        assert "bearer" not in metadata_str
        assert "private_key" not in metadata_str
        assert "client_secret" not in metadata_str
