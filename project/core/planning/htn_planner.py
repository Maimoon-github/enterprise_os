# pyright: reportMissingImports=false
"""Hierarchical Task Network (HTN) Planner and Dynamic Replanning Core (TSK-05).
Deconstructs branding goals across Macro (90-day), Meso (campaigns), and Micro (tasks) tiers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from core.state import AuditMetrics, BrandProfile


class TaskTier(str, Enum):
    MACRO = "macro"
    MESO = "meso"
    MICRO = "micro"


class MicroTask(BaseModel):
    """Discrete operational action consumable by Re-Act execution nodes."""

    task_id: str
    tier: Literal["micro"] = "micro"
    parent_meso_id: str
    parent_macro_id: str
    title: str
    action_type: str  # "cro_fix", "content_generation", "analytics_audit", "copy_review"
    priority: str = "high"  # "critical", "high", "medium", "low"
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    assigned_agent: str = "execution_core"


class MesoCampaign(BaseModel):
    """Funnel-specific campaign sprint (ToFu, MoFu, BoFu)."""

    campaign_id: str
    tier: Literal["meso"] = "meso"
    parent_macro_id: str
    title: str
    funnel_stage: Literal["ToFu", "MoFu", "BoFu"]
    target_metric: str
    tasks: List[MicroTask] = Field(default_factory=list)


class MacroStage(BaseModel):
    """Macro 90-day strategic roadmap phase."""

    stage_id: str
    tier: Literal["macro"] = "macro"
    day_range: str  # "Days 1–30", "Days 31–60", "Days 61–90"
    theme: str
    campaigns: List[MesoCampaign] = Field(default_factory=list)


class HTNPlanner:
    """Hierarchical Task Network planner with dynamic replanning feedback triggers."""

    def __init__(self, baseline_traffic: int = 20000, target_cac: float = 35.0):
        self.baseline_traffic = baseline_traffic
        self.target_cac = target_cac

    def decompose(
        self,
        brand: Optional[BrandProfile] = None,
        audit: Optional[AuditMetrics] = None,
        current_day: int = 15,
    ) -> List[Dict[str, Any]]:
        """Deconstruct 90-day macro horizon into meso funnel campaigns and micro task queue."""
        brand_name = brand.brand_name if brand else "Enterprise Brand"

        # 1. Macro Roadmap Definition
        macro_stage_id = "MACRO-01" if current_day <= 30 else ("MACRO-02" if current_day <= 60 else "MACRO-03")
        macro_theme = (
            "Foundation, Storefront Perception & Positioning Audit"
            if current_day <= 30
            else ("Content Authority Engine & Multi-Channel Distribution" if current_day <= 60 else "Scaling, CRO Optimization & Conversion Acceleration")
        )

        micro_tasks: List[MicroTask] = []

        # 2. Meso Campaigns
        # Campaign A: BoFu Storefront CRO & Friction Elimination
        meso_bofu = MesoCampaign(
            campaign_id="MESO-BOFU-01",
            parent_macro_id=macro_stage_id,
            title=f"{brand_name} Checkout Conversion Rate Optimization",
            funnel_stage="BoFu",
            target_metric="Conversion Rate & Checkout Completion",
        )

        # Micro tasks derived from Baymard issues
        if audit and audit.baymard_issues:
            for idx, issue in enumerate(audit.baymard_issues, 1):
                micro_tasks.append(
                    MicroTask(
                        task_id=f"TASK-BOFU-{idx:02d}",
                        parent_meso_id=meso_bofu.campaign_id,
                        parent_macro_id=macro_stage_id,
                        title=f"Resolve Usability Friction: {issue.split(':')[0]}",
                        action_type="cro_fix",
                        priority="critical",
                        parameters={"issue_detail": issue, "brand": brand_name},
                        assigned_agent="cro_specialist",
                    )
                )
        else:
            micro_tasks.append(
                MicroTask(
                    task_id="TASK-BOFU-01",
                    parent_meso_id=meso_bofu.campaign_id,
                    parent_macro_id=macro_stage_id,
                    title="Audit Storefront Checkout Funnel Performance",
                    action_type="analytics_audit",
                    priority="high",
                    parameters={"focus": "checkout_steps", "brand": brand_name},
                    assigned_agent="cro_specialist",
                )
            )

        # Campaign B: ToFu Educational Thought Leadership (Content Pillar 1)
        meso_tofu = MesoCampaign(
            campaign_id="MESO-TOFU-01",
            parent_macro_id=macro_stage_id,
            title=f"{brand_name} Organic Authority & Thought Leadership",
            funnel_stage="ToFu",
            target_metric="Reach & Qualified Website Sessions",
        )
        micro_tasks.append(
            MicroTask(
                task_id="TASK-TOFU-01",
                parent_meso_id=meso_tofu.campaign_id,
                parent_macro_id=macro_stage_id,
                title="Draft 35% Educational Value-First LinkedIn Carousel",
                action_type="content_generation",
                priority="high",
                parameters={"pillar": "35% Educational", "format": "carousel_5_slides"},
                assigned_agent="copy_writer",
            )
        )
        micro_tasks.append(
            MicroTask(
                task_id="TASK-TOFU-02",
                parent_meso_id=meso_tofu.campaign_id,
                parent_macro_id=macro_stage_id,
                title="Produce SEO Authority Primer on Core Customer Problem",
                action_type="content_generation",
                priority="medium",
                parameters={"pillar": "35% Educational", "target_audience": brand.target_audience if brand else ""},
                assigned_agent="copy_writer",
            )
        )

        # Campaign C: MoFu Proof & Demonstrations (Content Pillar 2)
        meso_mofu = MesoCampaign(
            campaign_id="MESO-MOFU-01",
            parent_macro_id=macro_stage_id,
            title=f"{brand_name} Proof, Demos & Case Study Validation",
            funnel_stage="MoFu",
            target_metric="Engagement Rate & Lead Qualification",
        )
        micro_tasks.append(
            MicroTask(
                task_id="TASK-MOFU-01",
                parent_meso_id=meso_mofu.campaign_id,
                parent_macro_id=macro_stage_id,
                title="Draft 25% Social Proof & Customer Transformation Case Study",
                action_type="content_generation",
                priority="high",
                parameters={"pillar": "25% Proof/Demos", "format": "case_study"},
                assigned_agent="copy_writer",
            )
        )

        # Sort tasks by priority: critical -> high -> medium -> low
        priority_weights = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        micro_tasks.sort(key=lambda t: priority_weights.get(t.priority, 99))

        return [task.model_dump() for task in micro_tasks]

    def should_replan(
        self,
        audit: AuditMetrics,
        traffic_threshold: Optional[int] = None,
        cac_threshold: Optional[float] = None,
    ) -> bool:
        """Evaluate performance telemetry against baseline variance thresholds."""
        t_thresh = traffic_threshold or self.baseline_traffic
        c_thresh = cac_threshold or self.target_cac

        # Trigger 1: Traffic drop below threshold
        traffic_dropped = audit.traffic > 0 and audit.traffic < t_thresh

        # Trigger 2: Customer Acquisition Cost spiked above threshold
        cac_spiked = audit.cac > c_thresh

        # Trigger 3: Severe conversion friction detected
        has_critical_friction = any("critical" in i.lower() or "baymard-01" in i.lower() or "baymard-02" in i.lower() for i in audit.baymard_issues)

        # Trigger 4: Health ratio degraded below target 3.0
        health_degraded = audit.health_ratio > 0 and audit.health_ratio < 3.0

        return traffic_dropped or cac_spiked or has_critical_friction or health_degraded

    def replan(
        self,
        current_queue: List[Dict[str, Any]],
        audit: AuditMetrics,
        brand: Optional[BrandProfile] = None,
    ) -> List[Dict[str, Any]]:
        """Dynamically reorder and inject corrective tasks based on metric variances."""
        brand_name = brand.brand_name if brand else "Brand"
        rebuilt_queue: List[Dict[str, Any]] = []

        # If CAC spiked: prioritize organic ToFu and MoFu proof to reduce paid acquisition costs
        if audit.cac > self.target_cac:
            rebuilt_queue.append(
                MicroTask(
                    task_id="TASK-REPLAN-CAC-01",
                    parent_meso_id="MESO-CAC-REMEDIATION",
                    parent_macro_id="MACRO-REPLAN",
                    title=f"Shift Paid to Organic: High-Leverage Referral & Proof Campaign for {brand_name}",
                    action_type="content_generation",
                    priority="critical",
                    parameters={"trigger": "cac_spike", "observed_cac": audit.cac, "target_cac": self.target_cac},
                    assigned_agent="growth_strategist",
                ).model_dump()
            )

        # If traffic dropped below baseline: inject viral hook distribution and SEO blitz
        if audit.traffic > 0 and audit.traffic < self.baseline_traffic:
            rebuilt_queue.append(
                MicroTask(
                    task_id="TASK-REPLAN-TRAFFIC-01",
                    parent_meso_id="MESO-TRAFFIC-RECOVERY",
                    parent_macro_id="MACRO-REPLAN",
                    title=f"Traffic Recovery Blitz: Multi-Channel Thought Leadership Campaign for {brand_name}",
                    action_type="content_generation",
                    priority="critical",
                    parameters={"trigger": "traffic_deficit", "observed_traffic": audit.traffic, "baseline": self.baseline_traffic},
                    assigned_agent="copy_writer",
                ).model_dump()
            )

        # If Baymard issues exist: ensure high-priority remediation is prepended
        if audit.baymard_issues:
            for idx, issue in enumerate(audit.baymard_issues, 1):
                task_id = f"TASK-REPLAN-CRO-{idx:02d}"
                if not any(t.get("task_id") == task_id for t in current_queue):
                    rebuilt_queue.append(
                        MicroTask(
                            task_id=task_id,
                            parent_meso_id="MESO-CRO-RECOVERY",
                            parent_macro_id="MACRO-REPLAN",
                            title=f"Urgent Friction Remediation: {issue.split(':')[0]}",
                            action_type="cro_fix",
                            priority="critical",
                            parameters={"friction_issue": issue},
                            assigned_agent="cro_specialist",
                        ).model_dump()
                    )

        # Retain pending existing tasks from previous queue without duplicates
        existing_ids = {t.get("task_id") for t in rebuilt_queue}
        for task in current_queue:
            if task.get("task_id") not in existing_ids and task.get("status") != "completed":
                rebuilt_queue.append(task)

        return rebuilt_queue
