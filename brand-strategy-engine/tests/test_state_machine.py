"""Tests for the pipeline state machine, linear stage progression, and revision loops."""

import pytest
from src.orchestrator.state_machine import PipelineStage, StateMachine
from src.schemas.initiative import ApprovalStatus


def test_linear_stage_progression(sample_master_state):
    state = sample_master_state
    assert state.current_stage == "Initialization"

    # Advance through stages
    assert StateMachine.advance_stage(state) == PipelineStage.ANALYST
    assert StateMachine.advance_stage(state) == PipelineStage.AUDIENCE
    assert StateMachine.advance_stage(state) == PipelineStage.BRAND
    assert StateMachine.advance_stage(state) == PipelineStage.SEO
    assert StateMachine.advance_stage(state) == PipelineStage.GROWTH
    assert StateMachine.advance_stage(state) == PipelineStage.VALIDATOR


def test_transition_validation():
    assert StateMachine.can_transition("Initialization", "Analyst") is True
    assert StateMachine.can_transition("Analyst", "Audience") is True
    assert StateMachine.can_transition("Analyst", "Growth") is False  # Cannot skip stages
    assert StateMachine.can_transition("Validator", "Completed") is True  # Valid completion
    assert StateMachine.can_transition("Validator", "Growth") is True  # Valid revision loop
    assert StateMachine.can_transition("Validator", "Brand") is False  # Invalid backwards skip


def test_validation_verdict_all_approved(sample_master_state):
    state = sample_master_state
    state.current_stage = PipelineStage.VALIDATOR.value
    state.strategic_artifacts.growth_initiatives[0].approval_status = ApprovalStatus.APPROVED

    next_stage, approved, purged = StateMachine.process_validation_verdict(state)
    assert next_stage == PipelineStage.COMPLETED
    assert len(approved) == 1
    assert len(purged) == 0
    assert state.validation_report.status in ("Approved", "Passed")


def test_validation_verdict_revision_loop_and_ceiling(sample_master_state):
    state = sample_master_state
    state.current_stage = PipelineStage.VALIDATOR.value
    init = state.strategic_artifacts.growth_initiatives[0]
    init.approval_status = ApprovalStatus.REJECTED

    # Cycle 1: Revision requested
    stage, approved, purged = StateMachine.process_validation_verdict(state)
    assert stage == PipelineStage.GROWTH
    assert state.iteration_counter == 1
    assert len(purged) == 0
    assert init.approval_status == ApprovalStatus.REVISION_REQUESTED
    assert init.iteration_cycle == 1

    # Cycle 2: Revision requested
    stage, approved, purged = StateMachine.process_validation_verdict(state)
    assert stage == PipelineStage.GROWTH
    assert state.iteration_counter == 2
    assert init.iteration_cycle == 2

    # Cycle 3: Revision requested
    stage, approved, purged = StateMachine.process_validation_verdict(state)
    assert stage == PipelineStage.GROWTH
    assert state.iteration_counter == 3
    assert init.iteration_cycle == 3

    # Cycle 4: Exceeds hard ceiling of 3 cycles -> Force purge unverified items!
    stage, approved, purged = StateMachine.process_validation_verdict(state)
    assert stage == PipelineStage.COMPLETED
    assert len(purged) == 1
    assert purged[0].recommendation_id == init.recommendation_id
    assert purged[0].approval_status == ApprovalStatus.REJECTED
    assert len(state.strategic_artifacts.growth_initiatives) == 0  # Purged from final state
    assert state.validation_report.status == "Completed_With_Purged_Unverified_Items"
    assert any(e.check_type == "max_iteration_ceiling_purge" for e in state.validation_report.audit_trail)


def test_stage_gate_precondition_checks(sample_master_state):
    """Verifies strict sequential stage gating and precondition enforcement from Stage 0 to Stage 6."""
    state = sample_master_state

    # Stage 0 & 1: BrandProfile and URL initialized
    ok, _ = StateMachine.validate_stage_preconditions(state, PipelineStage.INITIALIZATION)
    assert ok is True
    ok, _ = StateMachine.validate_stage_preconditions(state, PipelineStage.ANALYST)
    assert ok is True

    # Stage 2: Requires Stage 1 DOM or VNC artifacts
    ok, _ = StateMachine.validate_stage_preconditions(state, PipelineStage.AUDIENCE)
    assert ok is True  # sample_master_state has visual_evidence_vnc

    # Stage 3: Requires Stage 2 audience analysis
    ok, reason = StateMachine.validate_stage_preconditions(state, PipelineStage.BRAND)
    assert ok is False
    assert reason is not None and "audience_analysis" in reason

    # Commit Stage 2 artifact
    state.strategic_artifacts.audience_analysis = {"icp_profile": {"role": "CTO"}}
    ok, _ = StateMachine.validate_stage_preconditions(state, PipelineStage.BRAND)
    assert ok is True

    # Stage 4: Requires Stage 3 brand positioning
    ok, reason = StateMachine.validate_stage_preconditions(state, PipelineStage.SEO)
    assert ok is False
    assert reason is not None and "brand_positioning" in reason

    # Commit Stage 3 artifact
    state.strategic_artifacts.brand_positioning = {"category_of_one": "Pioneer"}
    ok, _ = StateMachine.validate_stage_preconditions(state, PipelineStage.SEO)
    assert ok is True

    # Stage 5: Requires Stage 4 SEO plan
    ok, reason = StateMachine.validate_stage_preconditions(state, PipelineStage.GROWTH)
    assert ok is False
    assert reason is not None and "seo_and_content_plan" in reason

    # Commit Stage 4 artifact
    state.strategic_artifacts.seo_and_content_plan = {"technical_health": {"score": 90}}
    ok, _ = StateMachine.validate_stage_preconditions(state, PipelineStage.GROWTH)
    assert ok is True

    # Stage 6: Requires Stage 5 growth initiatives
    ok, _ = StateMachine.validate_stage_preconditions(state, PipelineStage.VALIDATOR)
    assert ok is True  # sample_master_state has growth_initiatives


def test_targeted_revision_routing_payload(sample_strategic_initiative):
    """Verifies targeted revision routing payload generation with structured AuditEntry diagnostics."""
    from src.orchestrator.manager import StrategyOrchestrator
    from src.schemas.validation import AuditEntry, ValidationReport

    orchestrator = StrategyOrchestrator()
    init = sample_strategic_initiative
    init.approval_status = ApprovalStatus.REJECTED

    report = ValidationReport(
        status="Failed_Needs_Revision",
        total_audited=1,
        failed_count=1,
        audit_trail=[
            AuditEntry(
                recommendation_id=init.recommendation_id,
                check_type="provenance_check",
                passed=False,
                failure_reason="Unverified evidence provenance: ev_fake not found in research repository (ungrounded hallucination).",
                target_agent="Agent_5_Growth",
            )
        ],
    )

    routing_payload = orchestrator.route_revisions(
        target=[init],
        target_agent="Agent_5_Growth",
        validation_report=report,
    )

    assert routing_payload["target_agent"] == "Agent_5_Growth"
    assert routing_payload["action"] == "revise_initiatives"
    assert len(routing_payload["failed_initiatives"]) == 1
    assert len(routing_payload["audit_trail"]) == 1
    assert routing_payload["audit_trail"][0].passed is False
    assert "ungrounded hallucination" in routing_payload["audit_trail"][0].failure_reason

