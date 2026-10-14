"""Pipeline state machine enforcing linear transitions and adversarial revision cycles."""

from enum import Enum
from typing import List, Tuple
from src.schemas.initiative import ApprovalStatus, StrategicInitiative
from src.schemas.state import MasterEngineState
from src.schemas.validation import AuditEntry


class PipelineStage(str, Enum):
    INITIALIZATION = "Initialization"
    ANALYST = "Analyst"
    AUDIENCE = "Audience"
    BRAND = "Brand"
    SEO = "SEO"
    GROWTH = "Growth"
    VALIDATOR = "Validator"
    REVISION_LOOP = "Revision_Loop"
    COMPLETED = "Completed"
    FAILED = "Failed"


class StateMachine:
    """Controls pipeline execution gating and manages max-3 revision loops."""

    MAX_REVISION_LOOPS = 3

    STAGE_TRANSITIONS = {
        PipelineStage.INITIALIZATION: PipelineStage.ANALYST,
        PipelineStage.ANALYST: PipelineStage.AUDIENCE,
        PipelineStage.AUDIENCE: PipelineStage.BRAND,
        PipelineStage.BRAND: PipelineStage.SEO,
        PipelineStage.SEO: PipelineStage.GROWTH,
        PipelineStage.GROWTH: PipelineStage.VALIDATOR,
    }

    VALIDATOR_TRANSITIONS = {
        PipelineStage.COMPLETED,
        PipelineStage.GROWTH,
    }

    @classmethod
    def can_transition(cls, current_stage: str, next_stage: str) -> bool:
        """Verifies if transition between stages is permitted."""
        try:
            curr = PipelineStage(current_stage)
            target = PipelineStage(next_stage)
            if curr == PipelineStage.VALIDATOR:
                return target in cls.VALIDATOR_TRANSITIONS
            return cls.STAGE_TRANSITIONS.get(curr) == target
        except ValueError:
            return False

    @classmethod
    def advance_stage(cls, state: MasterEngineState) -> PipelineStage:
        """Advances state to the next sequential stage in the pipeline."""
        curr = PipelineStage(state.current_stage)
        next_stage = cls.STAGE_TRANSITIONS.get(curr, PipelineStage.COMPLETED)
        state.current_stage = next_stage.value
        return next_stage

    @classmethod
    def process_validation_verdict(
        cls,
        state: MasterEngineState,
    ) -> Tuple[PipelineStage, List[StrategicInitiative], List[StrategicInitiative]]:
        """
        Evaluates validator findings. If revisions exist, manages iteration ceiling (max 3).
        Returns (next_stage, approved_initiatives, purged_initiatives).
        """
        initiatives = state.strategic_artifacts.growth_initiatives
        approved: List[StrategicInitiative] = []
        rejected: List[StrategicInitiative] = []

        for init in initiatives:
            if init.approval_status == ApprovalStatus.APPROVED:
                approved.append(init)
            else:
                rejected.append(init)

        if not rejected:
            # All passed verification
            state.current_stage = PipelineStage.COMPLETED.value
            state.validation_report.status = "Approved"
            return PipelineStage.COMPLETED, approved, []

        # Initiatives were rejected
        state.iteration_counter += 1

        if state.iteration_counter > cls.MAX_REVISION_LOOPS:
            # Exceeded hard ceiling of 3 cycles: Permanently purge unverified recommendations
            purged = rejected
            state.strategic_artifacts.growth_initiatives = approved
            state.current_stage = PipelineStage.COMPLETED.value
            state.validation_report.status = "Completed_With_Purged_Unverified_Items"
            for p in purged:
                state.validation_report.audit_trail.append(
                    AuditEntry(
                        recommendation_id=p.recommendation_id,
                        check_type="max_iteration_ceiling_purge",
                        passed=False,
                        failure_reason=f"Permanently dropped from final strategy dossier after exceeding maximum {cls.MAX_REVISION_LOOPS} revision cycles.",
                        target_agent=getattr(p, "initiating_agent", "Agent_5_Growth"),
                    )
                )
            return PipelineStage.COMPLETED, approved, purged
        else:
            # Route back for revision
            state.current_stage = PipelineStage.GROWTH.value
            state.validation_report.status = f"Revision_Loop_Cycle_{state.iteration_counter}"
            return PipelineStage.GROWTH, approved, []
