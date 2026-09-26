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
from app.schemas.strategy import StrategyDirective

from ..profiles import S_ALLOC_PROFILE, SpecialistModelProfile


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

    def __init__(
        self,
        llm_client: LlmClient | None = None,
        profile: SpecialistModelProfile | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._profile = profile or S_ALLOC_PROFILE
        if self._profile.output_schema_name != AllocationReasoningOutput.__name__:
            raise ValueError(
                f"Profile output schema '{self._profile.output_schema_name}' mismatch with "
                f"{AllocationReasoningOutput.__name__}"
            )

    @property
    def profile(self) -> SpecialistModelProfile:
        return self._profile

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
            risks.append(
                "Historical media/performance inputs are absent; "
                "treat modeled response as a planning proxy."
            )
        if not context.get("incrementality_evidence"):
            risks.append("No incrementality calibration evidence supplied.")

        return AllocationReasoningOutput(
            objective_interpretation=objective,
            kpi_priorities=[str(kpi), "marginal ROI", "budget constraint compliance"],
            scenario_emphasis=emphasis,
            modeling_assumptions=[
                "Quantitative execution must remain inside S_ALLOC deterministic tools."
            ],
            risk_flags=risks,
            rationale_summary=(
                "Select a bounded planning scenario, then defer all numerical "
                "allocation to S_ALLOC tools."
            ),
            estimated_confidence=0.6 if risks else 0.75,
        )

    async def reason(
        self,
        grant: TaskGrant,
        context: dict[str, Any],
        directive: StrategyDirective | None = None,
    ) -> tuple[AllocationReasoningOutput, dict[str, Any]]:
        """Return bounded conclusions and model metadata without exposing chain-of-thought."""

        fallback = self._fallback(grant, context)
        profile_digest = self._profile.compute_digest()
        base_meta = {
            "profile_id": self._profile.profile_id,
            "profile_version": self._profile.profile_version,
            "profile_digest": profile_digest,
            "prompt_version": self._profile.prompt_version,
        }

        if self._llm_client is None:
            return fallback, {"reasoning_mode": "deterministic_fallback", **base_meta}

        # Normalize via StrategyDirective (T2 contract) if not supplied
        if directive is None:
            try:
                directive = StrategyDirective.from_grant(grant, context)
            except Exception:
                directive = None

        # Build prompt payload strictly from verified Directive and explicit allowlist.
        # NEVER serialize raw context, settings, credentials, env vars, or unverified keys.
        if directive is not None:
            summary = {
                "task_id": grant.task_id,
                "tenant_id": directive.tenant_id,
                "brand_id": directive.brand_id,
                "objective": directive.objective,
                "budget_ceiling": directive.budget_ceiling,
                "authorized_channels": directive.authorized_channels,
                "kpi_name": directive.kpi_name,
                "time_horizon": directive.time_horizon,
                "has_performance_telemetry": bool(context.get("performance_telemetry")),
                "has_media_history": bool(context.get("media_history")),
                "has_incrementality_evidence": bool(context.get("incrementality_evidence")),
                "allocation_constraints": [
                    c.model_dump() for c in directive.allocation_constraints
                ],
            }
        else:
            tenant_id = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
            summary = {
                "task_id": grant.task_id,
                "tenant_id": tenant_id,
                "brand_id": grant.brand_id,
                "objective": grant.objective,
                "budget_ceiling": context.get("budget_ceiling") or context.get("budget_cap"),
                "authorized_channels": (
                    list(grant.tenant_scope.allowed_channels) if grant.tenant_scope else []
                ),
                "kpi_name": context.get("kpi_name") or context.get("primary_kpi"),
                "has_performance_telemetry": bool(context.get("performance_telemetry")),
                "has_media_history": bool(context.get("media_history")),
                "has_incrementality_evidence": bool(context.get("incrementality_evidence")),
                "allocation_constraints": [],
            }

        user_prompt = json.dumps(summary, ensure_ascii=False, sort_keys=True, default=str)
        temp = self._profile.validate_temperature(self._profile.temperature_default)

        try:
            result, metadata = await self._llm_client.generate_structured_with_metadata(
                system_prompt=self._profile.system_prompt,
                user_prompt=user_prompt,
                response_model=AllocationReasoningOutput,
                temperature=temp,
                max_output_tokens=self._profile.max_output_tokens,
            )
            metadata.update(base_meta)
            return result, metadata
        except LlmResponseError:
            return fallback, {"reasoning_mode": "llm_error_fallback", **base_meta}

