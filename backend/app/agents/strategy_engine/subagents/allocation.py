"""S_ALLOC purpose-scoped reasoning and typed mandate bridge (L6-03).

The LLM is advisory only: it interprets objectives, KPI priorities, scenario emphasis,
assumptions, and risks. Host provider execution is removed from production composition.
Quantitative allocation remains deterministic inside the S_ALLOC isolated sandbox boundary.
"""

from __future__ import annotations

import json
import math
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent_contracts import TaskGrant
from app.schemas.sandbox import (
    SandboxExecutionStatus,
    SandboxInvocationMandate,
    SandboxResult,
)
from app.schemas.strategy import (
    AllocationConstraint,
    ChannelSpendProposal,
    SAllocDomainStatus,
    SAllocMandate,
    SAllocResult,
    StrategyDirective,
    compute_canonical_sha256,
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

    @property
    def llm_client(self) -> Any:
        return self._llm_client

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

    def parse_and_validate_result(
        self,
        mandate: SAllocMandate | SandboxInvocationMandate | Any,
        sandbox_result: SandboxResult,
    ) -> SAllocResult:
        """Parse, validate, and seal the typed SAllocResult against the authoritative mandate."""
        structured = sandbox_result.structured_output or getattr(sandbox_result, "result_payload", None) or {}
        sanitized = sandbox_result.sanitized_output or {}

        # Parse scenario allocations if present
        scenario_allocs: dict[str, list[ChannelSpendProposal]] = {}
        raw_scenarios = structured.get("scenarios") or sanitized.get("scenarios")
        if isinstance(raw_scenarios, str):
            try:
                raw_scenarios = json.loads(raw_scenarios)
            except Exception:
                raw_scenarios = {}
        if isinstance(raw_scenarios, dict):
            for sc_name, sc_data in raw_scenarios.items():
                props: list[ChannelSpendProposal] = []
                allocs = sc_data.get("allocations", {}) if isinstance(sc_data, dict) else {}
                tot = sum(allocs.values()) if allocs else 1.0
                for ch, amt in allocs.items():
                    props.append(
                        ChannelSpendProposal(
                            channel=ch,
                            allocated_amount=float(amt),
                            percentage_of_total=round((float(amt) / tot) * 100.0, 2) if tot > 0 else 0.0,
                        )
                    )
                scenario_allocs[sc_name] = props

        # Parse marginal roas
        raw_mroas = structured.get("marginal_roas") or sanitized.get("marginal_roas")
        marginal_roas: dict[str, float] = {}
        if isinstance(raw_mroas, str):
            try:
                raw_mroas = json.loads(raw_mroas)
            except Exception:
                raw_mroas = {}
        if isinstance(raw_mroas, dict):
            for k, v in raw_mroas.items():
                try:
                    fval = float(v)
                    if math.isfinite(fval):
                        marginal_roas[str(k)] = fval
                except (ValueError, TypeError):
                    pass

        # Parse diagnostics
        raw_diag = structured.get("model_diagnostics") or sanitized.get("model_diagnostics")
        diagnostics: dict[str, Any] = {}
        if isinstance(raw_diag, str):
            try:
                diagnostics = json.loads(raw_diag)
            except Exception:
                diagnostics = {}
        elif isinstance(raw_diag, dict):
            diagnostics = raw_diag

        # Determine domain status
        raw_domain_status = (
            structured.get("domain_status")
            or sanitized.get("domain_status")
            or structured.get("status")
            or sanitized.get("status")
            or SAllocDomainStatus.OK.value
        )
        try:
            domain_status = SAllocDomainStatus(raw_domain_status)
        except ValueError:
            domain_status = SAllocDomainStatus.INVALID_INPUT

        if not sandbox_result.success or sandbox_result.status != SandboxExecutionStatus.COMPLETED:
            if sandbox_result.status == SandboxExecutionStatus.TIMEOUT:
                domain_status = SAllocDomainStatus.SOLVER_FAILED
            else:
                domain_status = SAllocDomainStatus.SOLVER_FAILED

        total_allocated = float(structured.get("allocated_total") or sanitized.get("allocated_total") or 0.0)
        budget_residual = float(structured.get("budget_residual") or sanitized.get("budget_residual") or 0.0)

        s_alloc_result = SAllocResult(
            execution_id=mandate.execution_id,
            task_id=mandate.task_id,
            stage_attempt_id=mandate.stage_attempt_id,
            tenant_id=mandate.tenant_id,
            input_sha256=(
                getattr(mandate, "input_sha256", None)
                or (mandate.compute_input_digest() if hasattr(mandate, "compute_input_digest") else None)
                or (compute_canonical_sha256(mandate.payload) if hasattr(mandate, "payload") else compute_canonical_sha256(mandate))
            ),
            status=domain_status,
            scenario_allocations=scenario_allocs,
            total_allocated=total_allocated,
            budget_residual=budget_residual,
            marginal_roas=marginal_roas,
            diagnostics=diagnostics,
            execution_receipt=sandbox_result.execution_receipt,
            teardown_receipt=sandbox_result.teardown_receipt,
        )
        s_alloc_result.verify_correlation(mandate, require_receipts=bool(sandbox_result.execution_receipt))
        s_alloc_result.output_sha256 = s_alloc_result.compute_output_digest()
        return s_alloc_result


