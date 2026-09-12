"""Verifies Governance & State Milestone M1 acceptance criteria and validator."""

from __future__ import annotations

import uuid
import pytest

from app.orchestration.governance_milestone import (
    GovernanceMilestoneValidator,
)
from app.schemas.governance import (
    AutonomyTier,
    Directive,
    RiskLevel,
    TenantScope,
    VersionedPolicyEnvelope,
)
from app.schemas.task_state import CanonicalTaskState, TaskStatus, WorkerRole
from app.services.policy_engine import PolicyEngine


@pytest.fixture
def sample_approved_directive() -> Directive:
    scope = TenantScope(tenant_id="tenant-alpha", brand_ids=["brand-x"], allowed_channels=["meta"])
    return Directive(
        directive_id="dir-001",
        tenant_id="tenant-alpha",
        objective="Grow customer acquisition under strict legal claims",
        budget_cap=10000.0,
        risk_ceiling=RiskLevel.MEDIUM,
        scope=scope,
        autonomy_limit=AutonomyTier.TIER_2_AUTONOMOUS,
        operational_constraints=["Mandatory HITL on spend > $5k"],
        permitted_claims=["100% Organic", "Clinically Proven"],
        prohibited_actions=["unauthorized_data_export"],
        is_approved=True,
    )


@pytest.fixture
def sample_versioned_envelope(sample_approved_directive: Directive) -> VersionedPolicyEnvelope:
    engine = PolicyEngine()
    return engine.build_versioned_envelope(
        sample_approved_directive,
        sample_approved_directive.scope,
        version="1.0.0",
    )


@pytest.fixture
def sample_governed_tasks(sample_approved_directive: Directive) -> list[CanonicalTaskState]:
    return [
        CanonicalTaskState(
            task_id="task-1",
            directive_id=sample_approved_directive.directive_id,
            worker_role=WorkerRole.STRATEGY,
            status=TaskStatus.PENDING,
            governance_approved=True,
            prerequisite_locks=[],
        ),
        CanonicalTaskState(
            task_id="task-2",
            directive_id=sample_approved_directive.directive_id,
            worker_role=WorkerRole.CREATIVE_CONTENT,
            status=TaskStatus.PENDING,
            governance_approved=True,
            prerequisite_locks=[],
        ),
    ]


def test_milestone_m1_passes_when_all_conditions_satisfied(
    sample_approved_directive: Directive,
    sample_versioned_envelope: VersionedPolicyEnvelope,
    sample_governed_tasks: list[CanonicalTaskState],
) -> None:
    validator = GovernanceMilestoneValidator()

    report = validator.validate_milestone(
        directives=[sample_approved_directive],
        policy_envelopes=[sample_versioned_envelope],
        tasks=sample_governed_tasks,
        provenance_records_count=3,
    )

    assert report.is_complete is True
    assert report.milestone_id == "M1"
    assert len(report.results) == 7
    assert all(r.satisfied for r in report.results)


def test_milestone_m1_fails_if_directives_unapproved(
    sample_approved_directive: Directive,
    sample_versioned_envelope: VersionedPolicyEnvelope,
    sample_governed_tasks: list[CanonicalTaskState],
) -> None:
    validator = GovernanceMilestoneValidator()
    unapproved = sample_approved_directive.model_copy(update={"is_approved": False})

    report = validator.validate_milestone(
        directives=[unapproved],
        policy_envelopes=[sample_versioned_envelope],
        tasks=sample_governed_tasks,
        provenance_records_count=1,
    )

    assert report.is_complete is False
    c1 = next(r for r in report.results if r.condition_id == 1)
    assert c1.satisfied is False


def test_milestone_m1_fails_if_policy_envelopes_missing(
    sample_approved_directive: Directive,
    sample_governed_tasks: list[CanonicalTaskState],
) -> None:
    validator = GovernanceMilestoneValidator()

    report = validator.validate_milestone(
        directives=[sample_approved_directive],
        policy_envelopes=[],
        tasks=sample_governed_tasks,
        provenance_records_count=1,
    )

    assert report.is_complete is False
    c2 = next(r for r in report.results if r.condition_id == 2)
    assert c2.satisfied is False
