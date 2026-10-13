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


def test_validation_verdict_all_approved(sample_master_state):
    state = sample_master_state
    state.current_stage = PipelineStage.VALIDATOR.value
    state.strategic_artifacts.growth_initiatives[0].approval_status = ApprovalStatus.APPROVED

    next_stage, approved, purged = StateMachine.process_validation_verdict(state)
    assert next_stage == PipelineStage.COMPLETED
    assert len(approved) == 1
    assert len(purged) == 0
    assert state.validation_report.status == "Approved"


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

    # Cycle 2: Revision requested
    stage, approved, purged = StateMachine.process_validation_verdict(state)
    assert stage == PipelineStage.GROWTH
    assert state.iteration_counter == 2

    # Cycle 3: Revision requested
    stage, approved, purged = StateMachine.process_validation_verdict(state)
    assert stage == PipelineStage.GROWTH
    assert state.iteration_counter == 3

    # Cycle 4: Exceeds hard ceiling of 3 cycles -> Force purge unverified items!
    stage, approved, purged = StateMachine.process_validation_verdict(state)
    assert stage == PipelineStage.COMPLETED
    assert len(purged) == 1
    assert purged[0].recommendation_id == init.recommendation_id
    assert len(state.strategic_artifacts.growth_initiatives) == 0  # Purged from final state
    assert state.validation_report.status == "Completed_With_Purged_Unverified_Items"
