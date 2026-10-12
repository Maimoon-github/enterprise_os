# pyright: reportMissingImports=false
"""Weekly Operating Cadence and Autonomous Rhythm Coordinator (TSK-09).
Orchestrates the multi-day operating lifecycle across 4 distinct phases:
- Monday: Strategic Perception & HTN Planning
- Tuesday-Thursday: Multi-Channel 1-to-N Production
- Friday: Deterministic Guardrails & Human-in-the-Loop Review
- Saturday-Sunday: Commercial Telemetry & Learning Flywheel Synthesis
"""

from __future__ import annotations

import datetime
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from agent_sandbox import Sandbox  # type: ignore
except ImportError:
    from agent_sandbox.client import Sandbox  # type: ignore

from core.state import AgentState, BrandProfile


class DailyCadenceTask(BaseModel):
    """Specification for a single day's operational lifecycle."""

    weekday_index: int  # 0 = Monday, 6 = Sunday
    day_name: str  # "Monday", "Tuesday", etc.
    phase: str  # "planning", "production", "governance", "telemetry"
    objective: str
    target_nodes: List[str]
    deliverables: List[str]


class WeeklyOperatingSchedule(BaseModel):
    """Complete 7-day operating schedule for the enterprise agent."""

    brand_name: str
    week_label: str = "Week 12 (Days 61-90 Cycle)"
    daily_tasks: List[DailyCadenceTask] = Field(default_factory=list)
    active_phase: str = "planning"


class WeeklyCadenceScheduler:
    """Coordinates and executes weekly operating rhythm for the autonomous brand engine."""

    SCHEDULE_TEMPLATE: List[Dict[str, Any]] = [
        {
            "weekday_index": 0,
            "day_name": "Monday",
            "phase": "planning",
            "objective": "Storefront perception audit, HTN strategic task decomposition, and 4-pillar slot allocation (35/25/20/20).",
            "target_nodes": ["perception_and_audit_node", "strategic_reasoning_node"],
            "deliverables": ["StoreAuditSignal", "HTNTaskQueue", "PillarBalanceReport"],
        },
        {
            "weekday_index": 1,
            "day_name": "Tuesday",
            "phase": "production",
            "objective": "Execute 1-to-N content repurposing engine for Educational (35%) and Proof/Demos (25%) pillars.",
            "target_nodes": ["content_execution_node"],
            "deliverables": ["LinkedIn Thought Leadership", "5-Slide Educational Carousel"],
        },
        {
            "weekday_index": 2,
            "day_name": "Wednesday",
            "phase": "production",
            "objective": "Produce short-form video scripts and multimedia demonstration assets across channels.",
            "target_nodes": ["content_execution_node"],
            "deliverables": ["60-Second Short-Form Video Script", "Audio/Visual Storyboard"],
        },
        {
            "weekday_index": 3,
            "day_name": "Thursday",
            "phase": "production",
            "objective": "Derive Brand Story (20%) and Conversion Offer (20%) assets; draft email nurturing broadcasts.",
            "target_nodes": ["content_execution_node"],
            "deliverables": ["Email Nurturing Broadcast", "Conversion Landing Copy"],
        },
        {
            "weekday_index": 4,
            "day_name": "Friday",
            "phase": "governance",
            "objective": "Enforce deterministic brand guardrails, anti-hallucination grounding, and Human-in-the-Loop review gates.",
            "target_nodes": ["compliance_guardrail_node", "human_gate_node"],
            "deliverables": ["ComplianceVerificationResult", "GroundingVerificationResult", "HitLApprovalRecord"],
        },
        {
            "weekday_index": 5,
            "day_name": "Saturday",
            "phase": "telemetry",
            "objective": "Collect weekend commerce analytics, HAR network telemetry, and Baymard checkout friction signals.",
            "target_nodes": ["perception_and_audit_node", "funnel_optimization_node"],
            "deliverables": ["StorefrontHARTelemetry", "AuditMetrics"],
        },
        {
            "weekday_index": 6,
            "day_name": "Sunday",
            "phase": "telemetry",
            "objective": "Run isolated sandbox unit economics modeling, funnel diagnostics, and episodic memory distillation.",
            "target_nodes": ["funnel_optimization_node"],
            "deliverables": ["UnitEconomicsMetrics", "FunnelDiagnosticReport", "DistillationReport"],
        },
    ]

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url or os.getenv("SANDBOX_BASE_URL", "http://127.0.0.1:8080")
        self.api_key = api_key or os.getenv("SANDBOX_API_KEY", "aio-secret-key")
        self.headers = {"X-AIO-API-Key": self.api_key} if self.api_key else {}
        self.client = Sandbox(base_url=self.base_url, headers=self.headers)

    def get_task_for_day(self, day_identifier: int | str) -> DailyCadenceTask:
        """Retrieve the operational cadence task definition for a given day name or index."""
        if isinstance(day_identifier, int):
            idx = day_identifier % 7
            data = next(d for d in self.SCHEDULE_TEMPLATE if d["weekday_index"] == idx)
        else:
            norm_name = day_identifier.strip().capitalize()
            data = next((d for d in self.SCHEDULE_TEMPLATE if d["day_name"] == norm_name), self.SCHEDULE_TEMPLATE[0])
        return DailyCadenceTask(**data)

    def generate_weekly_operating_schedule(
        self,
        brand_name: str,
        week_label: str = "Week 12 (Days 61-90 Cycle)",
    ) -> WeeklyOperatingSchedule:
        """Generates the full 7-day schedule and persists it to /home/gem/weekly_operating_cadence.md."""
        tasks = [DailyCadenceTask(**item) for item in self.SCHEDULE_TEMPLATE]
        schedule = WeeklyOperatingSchedule(
            brand_name=brand_name,
            week_label=week_label,
            daily_tasks=tasks,
            active_phase="planning",
        )

        output_path = "/home/gem/weekly_operating_cadence.md"
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        md_content = f"""# {brand_name} Weekly Operating Cadence & Autonomous Rhythm

**Operating Cycle**: {week_label}
**Generated at**: {now_str}

---

## 7-Day Operating Rhythm:

"""
        for t in tasks:
            md_content += (
                f"### {t.day_name} — Phase: `{t.phase.upper()}`\n"
                f"- **Core Objective**: {t.objective}\n"
                f"- **Target LangGraph Nodes**: `{', '.join(t.target_nodes)}`\n"
                f"- **Key Deliverables**: {', '.join(t.deliverables)}\n\n"
            )

        try:
            self.client.file.write_file(file=output_path, content=md_content)
        except Exception:
            pass

        return schedule

    def dispatch_cadence_step(
        self,
        day_identifier: int | str,
        state: AgentState,
    ) -> Dict[str, Any]:
        """Maps the current day's operational phase into appropriate LangGraph state transitions."""
        task = self.get_task_for_day(day_identifier)
        metadata = dict(state.get("metadata") or {})
        metadata["current_cadence_day"] = task.day_name
        metadata["current_cadence_phase"] = task.phase

        # Transition agent phase in state
        phase_map: Dict[str, Any] = {
            "planning": "reasoning",
            "production": "action",
            "governance": "human_gate",
            "telemetry": "evaluation",
        }
        next_phase = phase_map.get(task.phase, "reasoning")

        return {
            "phase": next_phase,
            "metadata": metadata,
            "artifacts": ["/home/gem/weekly_operating_cadence.md"],
        }
