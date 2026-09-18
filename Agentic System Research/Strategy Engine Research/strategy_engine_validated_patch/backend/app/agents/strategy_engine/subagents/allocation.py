"""S_ALLOC purpose-scoped reasoning sub-agent.

The LLM is advisory only: it interprets objectives, KPI priorities, scenario emphasis,
assumptions, and risks. It cannot grant capabilities, change tenant scope, increase a
budget ceiling, access persistence/RAG, or execute external actions. Quantitative
allocation remains deterministic inside the S_ALLOC sandbox tool boundary.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.integrations.llm.client import LlmClient, LlmResponseError
from app.schemas.agent_contracts import TaskGrant


class AllocationReasoningOutput(BaseModel):
    """Bounded strategic conclusions emitted by the S_ALLOC reasoning LLM."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_interpretation: str = Field(min_length=1)
    kpi_priorities: list[str] = Field(default_factory=list)
    scenario_emphasis: Literal["balanced", "aggressive", "conservative"] = "balanced"
    modeling_assumptions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    rationale_summary: str = Field(min_length=1)
    estimated_confidence: float = Field(default=0.65, ge=0.0, le=1.0)


class StrategyAllocationAgent:
    """Purpose-scoped LLM reasoning component for S_ALLOC.

    This module deliberately has no dependency on ``StrategyAgent`` and no direct data
    or network client. It reasons only over an already-authorized TaskGrant plus the
    policy-screened context supplied by orchestration.
    """

    def __init__(self, llm_client: LlmClient | None = None) -> None:
        self._llm_client = llm_client

    @staticmethod
    def _fallback(grant: TaskGrant, context: dict[str, Any]) -> AllocationReasoningOutput:
        objective = (grant.objective or "Develop an evidence-grounded media plan").strip()
        objective_lower = objective.lower()
        if any(term in objective_lower for term in ("efficiency", "profit", "roas", "margin")):
            emphasis: Literal["balanced", "aggressive", "conservative"] = "conservative"
        elif any(term in objective_lower for term in ("awareness", "reach", "scale", "growth")):
            emphasis = "aggressive"
        else:
            emphasis = "balanced"

        kpi = context.get("kpi_name") or context.get("primary_kpi") or "incremental business KPI"
        risks: list[str] = []
        if not context.get("performance_telemetry") and not context.get("media_history"):
            risks.append("Historical media/performance inputs are absent; treat modeled response as a planning proxy.")
        if not context.get("incrementality_evidence"):
            risks.append("No incrementality calibration evidence supplied.")

        return AllocationReasoningOutput(
            objective_interpretation=objective,
            kpi_priorities=[str(kpi), "marginal ROI", "budget constraint compliance"],
            scenario_emphasis=emphasis,
            modeling_assumptions=["Quantitative execution must remain inside S_ALLOC deterministic tools."],
            risk_flags=risks,
            rationale_summary="Select a bounded planning scenario, then defer all numerical allocation to S_ALLOC tools.",
            estimated_confidence=0.6 if risks else 0.75,
        )

    async def reason(
        self,
        grant: TaskGrant,
        context: dict[str, Any],
    ) -> tuple[AllocationReasoningOutput, dict[str, Any]]:
        """Return bounded conclusions and model metadata without exposing chain-of-thought."""

        fallback = self._fallback(grant, context)
        if self._llm_client is None:
            return fallback, {"reasoning_mode": "deterministic_fallback"}

        tenant_id = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        summary = {
            "task_id": grant.task_id,
            "tenant_id": tenant_id,
            "brand_id": grant.brand_id,
            "objective": grant.objective,
            "budget_cap": context.get("budget_cap") or context.get("budget_ceiling"),
            "allowed_channels": (
                list(grant.tenant_scope.allowed_channels) if grant.tenant_scope else []
            ),
            "kpi_name": context.get("kpi_name") or context.get("primary_kpi"),
            "has_performance_telemetry": bool(context.get("performance_telemetry")),
            "has_media_history": bool(context.get("media_history")),
            "has_incrementality_evidence": bool(context.get("incrementality_evidence")),
            "constraints": context.get("channel_constraints") or context.get("constraints") or [],
        }

        system_prompt = (
            "You are S_ALLOC, the Strategy Engine's media-and-budget reasoning sub-agent. "
            "Return strategic conclusions only; never reveal hidden reasoning. "
            "You have no direct RAG, database, Intelligence Engine, campaign-platform, or "
            "StrategyAgent access. You cannot expand tenant/channel scope, authorize spend, "
            "change the supplied budget ceiling, or perform numerical allocation yourself. "
            "Your role is to identify KPI priorities, bounded scenario emphasis, modeling "
            "assumptions, and risks for deterministic sandbox tools."
        )
        user_prompt = json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)

        try:
            result, metadata = await self._llm_client.generate_structured_with_metadata(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=AllocationReasoningOutput,
            )
            return result, metadata
        except LlmResponseError:
            return fallback, {"reasoning_mode": "llm_error_fallback"}
