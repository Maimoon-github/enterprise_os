"""S_ALLOC purpose-scoped reasoning and typed mandate bridge (L6-03).

The LLM is advisory only: it interprets objectives, KPI priorities, scenario emphasis,
assumptions, and risks. Host provider execution is removed from production composition.
Quantitative allocation remains deterministic inside the S_ALLOC isolated sandbox boundary.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent_contracts import TaskGrant
from app.schemas.strategy import (
    AllocationConstraint,
    SAllocDomainStatus,
    SAllocMandate,
    SAllocResult,
    StrategyDirective,
)

from ..profiles import S_ALLOC_PROFILE, SpecialistModelProfile


class AllocationReasoningOutput(BaseModel):
    """Bounded strategic conclusions emitted by the S_ALLOC reasoning schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_interpretation: str = Field(min_length=1)
    kpi_priorities: list[str] = Field(default_factory=list)
    scenario_emphasis: Literal["balanced", "aggressive", "conservative"] = "balanced"
    modeling_assumptions: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    rationale_summary: str = Field(min_length=1)
    estimated_confidence: float = Field(default=0.65, ge=0.0, le=1.0)


class StrategyAllocationAgent:
    """Purpose-scoped typed mandate bridge for S_ALLOC.

    Acts as the bounded dispatch and result validation bridge between Strategy
    and the isolated sandbox runtime. Contains no host provider execution in production.
    """

    def __init__(
        self,
        profile: SpecialistModelProfile | None = None,
        llm_client: Any | None = None,
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
            estimated_confidence=0.65,
        )

    def build_mandate(
        self,
        grant: TaskGrant,
        context: dict[str, Any],
        directive: StrategyDirective | None = None,
    ) -> SAllocMandate:
        """Construct, attenuate, and seal the authoritative typed child mandate for S_ALLOC."""
        tenant_id = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        brand_id = grant.brand_id or "default"
        task_id = grant.task_id

        raw_budget = (
            context.get("budget")
            or context.get("budget_cap")
            or context.get("budget_ceiling", 0.0)
        )
        budget_ceiling = max(0.0, float(raw_budget))

        raw_channels = (
            context.get("channels")
            or (list(grant.tenant_scope.allowed_channels) if grant.tenant_scope else [])
            or ["meta", "google", "tiktok"]
        )
        if isinstance(raw_channels, str):
            channels = [x.strip().lower() for x in raw_channels.split(",") if x.strip()]
        else:
            channels = [str(x).strip().lower() for x in raw_channels if str(x).strip()]
        channels = list(dict.fromkeys(channels)) or ["meta", "google", "tiktok"]

        constraints: list[AllocationConstraint] = []
        if directive is not None:
            budget_ceiling = min(budget_ceiling, directive.budget_ceiling)
            constraints = list(directive.allocation_constraints)
            if directive.authorized_channels:
                channels = [c for c in channels if c in directive.authorized_channels]

        time_quota = min(
            self._profile.time_quota_seconds,
            int(context.get("timeout_seconds", self._profile.time_quota_seconds)),
        )
        token_quota = min(
            self._profile.token_quota,
            grant.token_budget
            if grant.token_budget and grant.token_budget > 0
            else self._profile.token_quota,
        )

        prov = getattr(grant, "provenance", None)
        parent_grant_hash = prov.get("grant_hash", "") if isinstance(prov, dict) else ""

        mandate = SAllocMandate(
            tenant_id=tenant_id,
            brand_id=brand_id,
            task_id=task_id,
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            stage_attempt_id=f"att-{uuid.uuid4().hex[:8]}",
            parent_grant_id=grant.task_id,
            parent_grant_version="v1",
            parent_grant_hash=parent_grant_hash,
            scenario_ids=["scenario_balanced", "scenario_aggressive", "scenario_conservative"],
            worker_id="W_STRAT",
            delegated_by="W_STRAT",
            purpose=grant.objective or "media_and_budget_allocation",
            expires_at=grant.expires_at,
            authorized_channels=channels,
            currency="USD",
            currency_precision=2,
            budget_ceiling=budget_ceiling,
            cost_basis="gross",
            allocation_constraints=constraints,
            time_horizon=str(context.get("time_horizon", "90_days")),
            token_quota=token_quota,
            time_quota_seconds=time_quota,
            mroi_floor=float(context.get("mroi_floor", 0.0)),
        )
        mandate.validate_attenuation(grant, directive)
        mandate.input_sha256 = mandate.compute_input_digest()
        return mandate

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

        if self._llm_client is not None:
            if directive is None:
                try:
                    directive = StrategyDirective.from_grant(grant, context)
                except Exception:
                    directive = None

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
            except Exception:
                return fallback, {"reasoning_mode": "llm_error_fallback", **base_meta}

        return fallback, {"reasoning_mode": "deterministic_bridge", **base_meta}

