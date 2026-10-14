"""Pipeline state machine enforcing linear transitions and adversarial revision cycles."""

from enum import Enum
from typing import List, Optional, Tuple, Union
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
    def validate_stage_preconditions(
        cls,
        state: MasterEngineState,
        target_stage: Union[PipelineStage, str],
    ) -> Tuple[bool, Optional[str]]:
        """
        Enforces strict sequential stage gating, verifying that upstream specialist
        prerequisites are committed and schema-validated before permitting transition.
        """
        try:
            target = PipelineStage(target_stage)
        except ValueError:
            return False, f"Invalid target stage '{target_stage}'"

        if target == PipelineStage.INITIALIZATION:
            if not state.brand_profile or not state.brand_profile.website_url:
                return False, "Stage 0 requires a valid BrandProfile with a non-empty website_url."
            return True, None

        elif target == PipelineStage.ANALYST:
            # Stage 1: Empirical VNC Reconnaissance requires Stage 0 completed
            if not state.brand_profile or not state.brand_profile.website_url:
                return False, "Stage 1 requires BrandProfile and target URL to be initialized."
            return True, None

        elif target == PipelineStage.AUDIENCE:
            # Stage 2: Audience & Friction Modeling requires Stage 1 artifacts
            repo = state.research_repository
            has_dom = bool(repo.dom_snapshots)
            has_vnc = bool(repo.visual_evidence_vnc)
            if not (has_dom or has_vnc):
                return False, "Stage 2 requires Stage 1 empirical DOM snapshots or visual VNC evidence."
            return True, None

        elif target == PipelineStage.BRAND:
            # Stage 3: Brand & Narrative Positioning requires Stage 2 audience analysis
            art = state.strategic_artifacts
            if not art.audience_analysis:
                return False, "Stage 3 requires Stage 2 strategic_artifacts.audience_analysis to be committed."
            return True, None

        elif target == PipelineStage.SEO:
            # Stage 4: SEO & Content Gap Auditing requires Stage 3 brand positioning
            art = state.strategic_artifacts
            if not art.brand_positioning:
                return False, "Stage 4 requires Stage 3 strategic_artifacts.brand_positioning to be committed."
            return True, None

        elif target == PipelineStage.GROWTH:
            # Stage 5: Strategic Synthesis requires Stage 4 SEO & content plan
            art = state.strategic_artifacts
            if not art.seo_and_content_plan:
                return False, "Stage 5 requires Stage 4 strategic_artifacts.seo_and_content_plan to be committed."
            return True, None

        elif target == PipelineStage.VALIDATOR:
            # Stage 6: Adversarial Audit requires Stage 5 growth initiatives
            art = state.strategic_artifacts
            if not art.growth_initiatives:
                return False, "Stage 6 requires Stage 5 strategic_artifacts.growth_initiatives to be populated."
            return True, None

        elif target == PipelineStage.COMPLETED:
            # Publication requires Stage 6 validation verdict
            if state.validation_report.status not in ("Approved", "Passed", "Completed_With_Purged_Unverified_Items"):
                return False, "Completion requires validation_report to be Approved, Passed, or Completed with purges."
            return True, None

        return True, None

    @classmethod
    def advance_stage(cls, state: MasterEngineState, enforce_preconditions: bool = False) -> PipelineStage:
        """Advances state to the next sequential stage in the pipeline."""
        curr = PipelineStage(state.current_stage)
        next_stage = cls.STAGE_TRANSITIONS.get(curr, PipelineStage.COMPLETED)
        if enforce_preconditions:
            ok, reason = cls.validate_stage_preconditions(state, next_stage)
            if not ok:
                raise ValueError(f"Stage transition precondition failed: {reason}")
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
            state.validation_report.status = "Passed"
            return PipelineStage.COMPLETED, approved, []

        # Initiatives were rejected
        state.iteration_counter += 1

        if state.iteration_counter > cls.MAX_REVISION_LOOPS:
            # Exceeded hard ceiling of 3 cycles: Permanently purge unverified recommendations
            purged = rejected
            for p in purged:
                p.approval_status = ApprovalStatus.REJECTED
                state.validation_report.audit_trail.append(
                    AuditEntry(
                        recommendation_id=p.recommendation_id,
                        check_type="max_iteration_ceiling_purge",
                        passed=False,
                        failure_reason=f"Permanently dropped from final strategy dossier after exceeding maximum {cls.MAX_REVISION_LOOPS} revision cycles.",
                        target_agent=getattr(p, "initiating_agent", "Agent_5_Growth"),
                    )
                )
            state.strategic_artifacts.growth_initiatives = approved
            state.current_stage = PipelineStage.COMPLETED.value
            state.validation_report.status = "Completed_With_Purged_Unverified_Items"
            return PipelineStage.COMPLETED, approved, purged
        else:
            # Route back for revision
            for r in rejected:
                r.iteration_cycle = state.iteration_counter
                r.approval_status = ApprovalStatus.REVISION_REQUESTED
            state.current_stage = PipelineStage.GROWTH.value
            state.validation_report.status = f"Revision_Loop_Cycle_{state.iteration_counter}"
            return PipelineStage.GROWTH, approved, []
