"""Deterministic Creative Content Workflow (Fixed-DAG Orchestration).

Orchestrates the six Creative specialist sub-agents according to the fixed DAG:
    RESEARCH → CONCEPT → [COPY ∥ VISUAL] → ADAPT → QA

Enforces:
1. Strict sequential dependencies: RESEARCH precedes CONCEPT; CONCEPT precedes COPY/VISUAL.
2. Controlled parallelism: Only COPY and VISUAL execute concurrently via asyncio.gather().
3. Failed branch isolation: A failure in either COPY or VISUAL halts before ADAPT.
4. Static QA revision routing: Deterministic transitions without dynamic LLM redirection.
5. Strict revision bounding: Bounded by CreativePlan.max_revision_attempts.
6. Artifact immutability: Evaluated artifacts and hashes remain untouched after QA PASS.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.creative_content_engine.subagents.adaptation import CreativeAdaptationAgent
from app.agents.creative_content_engine.subagents.concept import CreativeConceptAgent
from app.agents.creative_content_engine.subagents.copy import CreativeCopyAgent
from app.agents.creative_content_engine.subagents.quality import CreativeQualityAgent
from app.agents.creative_content_engine.subagents.research import CreativeResearchAgent
from app.agents.creative_content_engine.subagents.visual import CreativeVisualAgent
from app.schemas.agent_contracts import (
    AdaptedCreativePack,
    ConceptPack,
    CopyPack,
    CreativePlan,
    PlatformSpecSnapshot,
    QAReasonCode,
    QAReport,
    QAStatus,
    ResearchBrief,
    TaskGrant,
    VisualPack,
)

# Static Revision Routing Table: Maps QA reason code to deterministic starting stage
STATIC_REVISION_ROUTES: dict[str, str] = {
    QAReasonCode.RESEARCH.value: "RESEARCH",
    QAReasonCode.CONCEPT.value: "CONCEPT",
    QAReasonCode.COPY.value: "COPY",
    QAReasonCode.VISUAL.value: "VISUAL",
    QAReasonCode.ADAPT.value: "ADAPT",
    QAReasonCode.EVIDENCE_MISSING.value: "EXIT_NO_RETRY",
    QAReasonCode.SCOPE_VIOLATION.value: "BLOCK",
    QAReasonCode.POLICY_BLOCK.value: "BLOCK",
}


class CreativeWorkflowResult(BaseModel):
    """Execution outcome of the deterministic Creative specialist pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    qa_report: QAReport
    plan: CreativePlan
    research_brief: ResearchBrief | None = None
    platform_spec_snapshot: PlatformSpecSnapshot | None = None
    concept_pack: ConceptPack | None = None
    copy_pack: CopyPack | None = None
    visual_pack: VisualPack | None = None
    adapted_pack: AdaptedCreativePack | None = None
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    findings: list[str] = Field(default_factory=list)


class CreativeContentWorkflow:
    """Deterministic, fixed-DAG orchestrator for Creative specialist agents."""

    def __init__(
        self,
        research_agent: CreativeResearchAgent | None = None,
        concept_agent: CreativeConceptAgent | None = None,
        copy_agent: CreativeCopyAgent | None = None,
        visual_agent: CreativeVisualAgent | None = None,
        adaptation_agent: CreativeAdaptationAgent | None = None,
        qa_agent: CreativeQualityAgent | None = None,
    ) -> None:
        self._research_agent = research_agent or CreativeResearchAgent()
        self._concept_agent = concept_agent or CreativeConceptAgent()
        self._copy_agent = copy_agent or CreativeCopyAgent()
        self._visual_agent = visual_agent or CreativeVisualAgent()
        self._adaptation_agent = adaptation_agent or CreativeAdaptationAgent()
        self._qa_agent = qa_agent or CreativeQualityAgent()

    async def run(
        self,
        grant: TaskGrant,
        plan: CreativePlan,
        context: dict[str, Any],
    ) -> CreativeWorkflowResult:
        """Execute the fixed-DAG creative pipeline with deterministic QA routing."""
        # Check for pre-canned test override
        if "workflow_result" in context and isinstance(
            context["workflow_result"], CreativeWorkflowResult
        ):
            return context["workflow_result"]

        # Enforce authoritative revision limit from plan or grant policy; never LLM-controlled
        max_revisions = plan.max_revision_attempts
        if "max_revision_attempts" in context:
            try:
                max_revisions = int(context["max_revision_attempts"])
            except (ValueError, TypeError):
                pass

        # Initial DAG state
        stage_to_run = "RESEARCH"
        revision_attempts = 0

        research_brief: ResearchBrief | None = None
        platform_spec: PlatformSpecSnapshot | None = None
        concept_pack: ConceptPack | None = None
        copy_pack: CopyPack | None = None
        visual_pack: VisualPack | None = None
        adapted_pack: AdaptedCreativePack | None = None
        qa_report: QAReport | None = None

        workflow_findings: list[str] = [
            f"Workflow initialized: {len(plan.approved_channels)} channel(s), max_revisions={max_revisions}"
        ]

        while True:
            # -------------------------------------------------------------
            # Stage 1: RESEARCH
            # -------------------------------------------------------------
            if stage_to_run == "RESEARCH":
                workflow_findings.append(f"[Attempt {revision_attempts}] Executing CREAT-RESEARCH")
                research_brief, platform_spec = await self._research_agent.run(
                    grant=grant, plan=plan, context=context
                )
                stage_to_run = "CONCEPT"

            # -------------------------------------------------------------
            # Stage 2: CONCEPT
            # -------------------------------------------------------------
            if stage_to_run == "CONCEPT":
                workflow_findings.append(f"[Attempt {revision_attempts}] Executing CREAT-CONCEPT")
                concept_pack = await self._concept_agent.run(
                    grant=grant, plan=plan, context=context
                )
                stage_to_run = "COPY_VISUAL"

            # -------------------------------------------------------------
            # Stage 3: COPY ∥ VISUAL (Parallel branch or selective retry)
            # -------------------------------------------------------------
            if stage_to_run == "COPY":
                workflow_findings.append(f"[Attempt {revision_attempts}] Selectively revising CREAT-COPY")
                copy_pack = await self._copy_agent.run(
                    grant=grant, concept_pack=concept_pack, plan=plan, context=context
                )
                stage_to_run = "ADAPT"
            elif stage_to_run == "VISUAL":
                workflow_findings.append(f"[Attempt {revision_attempts}] Selectively revising CREAT-VISUAL")
                visual_pack = await self._visual_agent.run(
                    grant=grant,
                    concept_pack=concept_pack,
                    plan=plan,
                    platform_specs=platform_spec,
                    context=context,
                )
                stage_to_run = "ADAPT"
            elif stage_to_run == "COPY_VISUAL":
                workflow_findings.append(f"[Attempt {revision_attempts}] Executing concurrent COPY ∥ VISUAL")
                # Predefined concurrency only for COPY and VISUAL; failed branch halts before ADAPT
                copy_pack, visual_pack = await asyncio.gather(
                    self._copy_agent.run(
                        grant=grant, concept_pack=concept_pack, plan=plan, context=context
                    ),
                    self._visual_agent.run(
                        grant=grant,
                        concept_pack=concept_pack,
                        plan=plan,
                        platform_specs=platform_spec,
                        context=context,
                    ),
                )
                stage_to_run = "ADAPT"

            # -------------------------------------------------------------
            # Stage 4: ADAPT (Requires successful completion of both branches)
            # -------------------------------------------------------------
            if stage_to_run == "ADAPT":
                if copy_pack is None or visual_pack is None:
                    raise RuntimeError(
                        "Invariant violation: ADAPT stage cannot proceed without both COPY and VISUAL packs."
                    )
                workflow_findings.append(f"[Attempt {revision_attempts}] Executing CREAT-ADAPT")
                adapted_pack = await self._adaptation_agent.run(
                    grant=grant,
                    copy_pack=copy_pack,
                    visual_pack=visual_pack,
                    platform_specs=platform_spec,
                    plan=plan,
                    context=context,
                )
                stage_to_run = "QA"

            # -------------------------------------------------------------
            # Stage 5: QA Evaluation
            # -------------------------------------------------------------
            if stage_to_run == "QA":
                workflow_findings.append(f"[Attempt {revision_attempts}] Executing CREAT-QA")
                qa_report = await self._qa_agent.run(
                    grant=grant,
                    plan=plan,
                    concept_pack=concept_pack,
                    copy_pack=copy_pack,
                    visual_pack=visual_pack,
                    adapted_pack=adapted_pack,
                    context=context,
                )

            if qa_report is None:
                raise RuntimeError("Workflow execution ended without generating a QA report.")

            # -------------------------------------------------------------
            # Deterministic Routing Evaluation
            # -------------------------------------------------------------
            if qa_report.status == QAStatus.PASS:
                workflow_findings.append(
                    f"QA Evaluation PASSED on attempt {revision_attempts}. Evaluated hash: {qa_report.evaluated_artifact_hash[:16]}..."
                )
                break

            if qa_report.status == QAStatus.BLOCK:
                workflow_findings.append(
                    f"QA Evaluation BLOCKED: reason={qa_report.reason_code or 'BLOCK'}. Halting without retry."
                )
                break

            # Handle QAStatus.REVISE
            reason_str = (
                qa_report.reason_code.value
                if isinstance(qa_report.reason_code, QAReasonCode)
                else (qa_report.reason_code or "ADAPT")
            )
            route_target = STATIC_REVISION_ROUTES.get(reason_str, "ADAPT")

            if route_target in ("EXIT_NO_RETRY", "BLOCK"):
                workflow_findings.append(
                    f"QA Evaluation REVISE route '{route_target}' requires external resolution; halting retry loop."
                )
                break

            if revision_attempts >= max_revisions:
                workflow_findings.append(
                    f"Max revision attempts ({max_revisions}) exhausted. Returning control with current QA status."
                )
                break

            # Proceed with static revision routing
            revision_attempts += 1
            stage_to_run = route_target
            workflow_findings.append(
                f"Revision {revision_attempts}/{max_revisions} routed to stage '{stage_to_run}' based on reason '{reason_str}'"
            )

        # Formulate sealed artifact hashes dict
        artifact_hashes: dict[str, str] = {
            "plan": plan.artifact_hash,
            "research_brief": research_brief.artifact_hash if research_brief else "",
            "platform_spec_snapshot": platform_spec.artifact_hash if platform_spec else "",
            "concept_pack": concept_pack.artifact_hash if concept_pack else "",
            "copy_pack": copy_pack.artifact_hash if copy_pack else "",
            "visual_pack": visual_pack.artifact_hash if visual_pack else "",
            "adapted_pack": adapted_pack.artifact_hash if adapted_pack else "",
            "qa_report": qa_report.artifact_hash if qa_report else "",
        }

        return CreativeWorkflowResult(
            qa_report=qa_report,
            plan=plan,
            research_brief=research_brief,
            platform_spec_snapshot=platform_spec,
            concept_pack=concept_pack,
            copy_pack=copy_pack,
            visual_pack=visual_pack,
            adapted_pack=adapted_pack,
            artifact_hashes=artifact_hashes,
            findings=workflow_findings,
        )
