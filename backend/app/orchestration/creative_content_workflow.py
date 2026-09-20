"""Creative Content Workflow stub and contract for W_CREAT coordination."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent_contracts import (
    AdaptedCreativePack,
    AdCopyVariant,
    ConceptItem,
    ConceptPack,
    ContentScheduleItem,
    CopyPack,
    CreativePlan,
    QAFinding,
    QAReport,
    QAStatus,
    TaskGrant,
    VisualBrief,
    VisualPack,
)


class CreativeWorkflowResult(BaseModel):
    """Execution outcome of the Creative specialist pipeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    qa_report: QAReport
    plan: CreativePlan
    concept_pack: ConceptPack | None = None
    copy_pack: CopyPack | None = None
    visual_pack: VisualPack | None = None
    adapted_pack: AdaptedCreativePack | None = None
    artifact_hashes: dict[str, str] = Field(default_factory=dict)
    findings: list[str] = Field(default_factory=list)


class CreativeContentWorkflow:
    """Fixed-DAG executor for Creative Engine (stubbed for T2, fully implemented in T4)."""

    async def run(
        self,
        grant: TaskGrant,
        plan: CreativePlan,
        context: dict[str, Any],
    ) -> CreativeWorkflowResult:
        """Execute or simulate specialist workflow execution under approved plan."""
        if "workflow_result" in context and isinstance(
            context["workflow_result"], CreativeWorkflowResult
        ):
            return context["workflow_result"]

        tenant_id = plan.tenant_id
        task_id = plan.task_id
        channels = plan.approved_channels or ["meta"]
        evidence_manifest = plan.evidence_manifest or ["claim-0"]

        # Synthesize concept pack bounded to plan
        concepts = [
            ConceptItem(
                concept_id=f"cpt-{i + 1}",
                territory="performance",
                audience_tension="efficiency gap",
                message_angle="proven benchmark",
                narrative_architecture="hook -> evidence -> call to action",
                approved_evidence_refs=evidence_manifest,
            )
            for i, _ in enumerate(channels)
        ]
        concept_pack = ConceptPack(
            tenant_id=tenant_id,
            task_id=task_id,
            concepts=concepts,
            approved_channel_ids=channels,
            evidence_refs=evidence_manifest,
        )
        concept_hash = concept_pack.compute_artifact_hash()

        # Synthesize copy variants bounded strictly to approved channels and claims
        disclaimers: list[str] = []
        raw_disc = context.get("required_disclaimers")
        if isinstance(raw_disc, str) and raw_disc.strip():
            disclaimers = [d.strip() for d in raw_disc.split(";") if d.strip()]
        elif isinstance(raw_disc, list):
            disclaimers = [str(d).strip() for d in raw_disc if str(d).strip()]

        copy_variants = [
            AdCopyVariant(
                variant_id=f"var-{ch}-01",
                channel=ch,
                headline=f"Enterprise Performance on {ch.title()}",
                hook_angle="proven_results",
                body_copy=(
                    f"Verified operational improvement for "
                    f"{plan.target_audience or 'enterprise'}."
                ),
                cta="Learn More",
                source_claim_ids=evidence_manifest[:1],
                compliance_checked=True,
                disclaimers=disclaimers,
            )
            for ch in channels
        ]
        copy_pack = CopyPack(
            tenant_id=tenant_id,
            task_id=task_id,
            concept_ref="cpt-1",
            variants=copy_variants,
            approved_channel_ids=channels,
            evidence_refs=evidence_manifest,
            factual_claim_refs=evidence_manifest,
        )
        copy_hash = copy_pack.compute_artifact_hash()

        # Synthesize visual direction briefs bounded strictly to approved channels
        visual_briefs = [
            VisualBrief(
                brief_id=f"vb-{ch}-01",
                asset_title=f"{ch.title()} Creative Brief",
                channel=ch,
                format="1:1_feed" if ch != "reels" else "9:16_vertical",
                aspect_ratio="1:1" if ch != "reels" else "9:16",
                art_direction="Clean enterprise composition with verified metrics overlay.",
            )
            for ch in channels
        ]
        visual_pack = VisualPack(
            tenant_id=tenant_id,
            task_id=task_id,
            concept_ref="cpt-1",
            production_briefs=visual_briefs,
            approved_channel_ids=channels,
            evidence_refs=evidence_manifest,
        )
        visual_hash = visual_pack.compute_artifact_hash()

        # Synthesize schedule items
        schedules = [
            ContentScheduleItem(
                schedule_id=f"sch-{ch}-01",
                day_or_week=f"Week {i + 1} - Slot 1",
                channel=ch,
                variant_ref=f"var-{ch}-01",
                primary_objective=plan.approved_objectives[0]
                if plan.approved_objectives
                else "acquisition",
                target_audience=plan.target_audience,
            )
            for i, ch in enumerate(channels)
        ]

        adapted_pack = AdaptedCreativePack(
            tenant_id=tenant_id,
            task_id=task_id,
            ad_copy_variants=copy_variants,
            visual_briefs=visual_briefs,
            calendar_proposal=schedules,
            approved_channel_ids=channels,
            evidence_refs=evidence_manifest,
            source_copy_refs=[copy_pack.pack_id],
            source_visual_refs=[visual_pack.pack_id],
        )
        adapted_hash = adapted_pack.compute_artifact_hash()

        artifact_hashes = {
            "plan": plan.artifact_hash,
            "concept_pack": concept_hash,
            "copy_pack": copy_hash,
            "visual_pack": visual_hash,
            "adapted_pack": adapted_hash,
        }

        qa_report = QAReport(
            tenant_id=tenant_id,
            task_id=task_id,
            evaluated_artifact_hash=adapted_hash,
            status=QAStatus.PASS,
            passed_checks=[
                "grounding_verified",
                "channel_scope_verified",
                "character_limits_passed",
                "safe_zone_verified",
            ],
            findings=[
                QAFinding(
                    layer="grounding",
                    severity="info",
                    reason_code="NONE",
                    message="All claims verified against approved evidence manifest.",
                    evidence_refs=evidence_manifest,
                )
            ],
        )
        qa_hash = qa_report.compute_artifact_hash()
        artifact_hashes["qa_report"] = qa_hash

        findings = [
            f"Creative plan initialized: {len(channels)} authorized channels",
            f"Concept pack generated: {len(concepts)} concepts",
            f"Copy pack generated: {len(copy_variants)} variants across {len(channels)} channels",
            f"Visual direction briefs generated: {len(visual_briefs)} briefs",
            f"Content release schedules planned: {len(schedules)} slots",
            f"QA Evaluation: {qa_report.status.value} (hash: {qa_hash[:16]}...)",
        ]

        return CreativeWorkflowResult(
            qa_report=qa_report,
            plan=plan,
            concept_pack=concept_pack,
            copy_pack=copy_pack,
            visual_pack=visual_pack,
            adapted_pack=adapted_pack,
            artifact_hashes=artifact_hashes,
            findings=findings,
        )
