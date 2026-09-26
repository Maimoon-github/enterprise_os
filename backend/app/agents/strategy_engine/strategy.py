"""W_STRAT: omnichannel roadmaps, funnels, media mix, and budgets."""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import BoundedWorkerAgent, WorkerReasoningOutput
from app.agents.strategy_engine.subagents import (
    AllocationReasoningOutput,
    StrategyAllocationAgent,
)
from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.client import SandboxClient
from app.schemas.agent_contracts import (
    ConfidenceInterval,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    TaskGrant,
)
from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxInvocationMandate
from app.schemas.strategy import StrategyDirective, StrategyResultEnvelope


class StrategyAgent(BoundedWorkerAgent):
    """W_STRAT Strategy Engine.

    Consumes validated outputs from T16 (Product Evidence), T17 (Customer Voice),
    and T18 (Competitor Intelligence) through the Intelligence Engine bounded grant,
    verifies dependency compliance and tenant isolation, invokes S_ALLOC purpose-scoped
    reasoning, formulates the S_ALLOC optimization mandate, invokes S_ALLOC within the
    sandbox, and interprets the sanitized output into evidence-backed omnichannel roadmaps,
    funnel models, budget proposals, and scenario comparisons.
    """

    capability: SandboxCapability = SandboxCapability.ALLOC

    def __init__(
        self,
        sandbox_client: SandboxClient,
        llm_client: Any | None = None,
        allocation_agent: StrategyAllocationAgent | None = None,
    ) -> None:
        super().__init__(sandbox_client, llm_client=llm_client)
        self._allocation_agent = allocation_agent or StrategyAllocationAgent()

    @property
    def allocation_agent(self) -> StrategyAllocationAgent:
        """Advisory S_ALLOC media and budget sub-agent."""
        return self._allocation_agent

    def _verify_and_normalize_dependencies(
        self, grant: TaskGrant, context: dict[str, object]
    ) -> tuple[
        float,
        list[str],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, Any],
        str,
        list[str],
    ]:
        """Verify presence and validity of T16, T17, and T18 dependencies and enforce tenant isolation.

        Fails closed safely if any required dependency evidence is missing or off-tenant.
        """
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"

        # -------------------------------------------------------------
        # 1. Verify T16: Product Evidence & Approved Claims
        # -------------------------------------------------------------
        approved_claims: list[dict[str, Any]] = []

        # Check Claims Dossier object or JSON
        dossier = context.get("claims_dossier") or grant.cts_state.get("claims_dossier")
        if dossier:
            if isinstance(dossier, dict):
                d_tenant = dossier.get("tenant_id")
                if d_tenant and d_tenant != grant_tenant:
                    raise ValueError(
                        f"Tenant isolation breach in T16 product evidence: dossier tenant '{d_tenant}' "
                        f"does not match grant tenant '{grant_tenant}'."
                    )
                for c in dossier.get("claims", []):
                    if isinstance(c, dict):
                        if c.get("validation_status") == "SUPPORTED" or c.get("confidence", 0) >= 0.7:
                            approved_claims.append(c)
            elif isinstance(dossier, str):
                try:
                    parsed_d = json.loads(dossier)
                    if isinstance(parsed_d, dict):
                        d_tenant = parsed_d.get("tenant_id")
                        if d_tenant and d_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in T16 product evidence: dossier tenant '{d_tenant}' "
                                f"does not match grant tenant '{grant_tenant}'."
                            )
                        for c in parsed_d.get("claims", []):
                            if isinstance(c, dict) and (c.get("validation_status") == "SUPPORTED" or c.get("confidence", 0) >= 0.7):
                                approved_claims.append(c)
                except json.JSONDecodeError:
                    pass

        # Check raw claims list or validated evidence
        raw_claims = (
            context.get("approved_claims")
            or context.get("supported_claims")
            or context.get("claims")
            or grant.cts_state.get("approved_claims")
            or grant.cts_state.get("claims")
        )
        if raw_claims and isinstance(raw_claims, list):
            for idx, c in enumerate(raw_claims):
                if isinstance(c, dict):
                    c_tenant = c.get("tenant_id")
                    if c_tenant and c_tenant != grant_tenant:
                        raise ValueError(
                            f"Tenant isolation breach in T16 claims: claim tenant '{c_tenant}' "
                            f"does not match grant tenant '{grant_tenant}'."
                        )
                    approved_claims.append(c)
                else:
                    approved_claims.append({"id": f"claim-{idx + 1}", "text": str(c), "status": "SUPPORTED"})

        # Check validated_evidence in grant
        for ev in grant.validated_evidence:
            ev_tenant = ev.get("tenant_id")
            if ev_tenant and ev_tenant != grant_tenant:
                raise ValueError(
                    f"Tenant isolation breach in validated evidence: evidence tenant '{ev_tenant}' "
                    f"does not match grant tenant '{grant_tenant}'."
                )
            if "claim" in ev or "clinical" in ev.get("text", "").lower() or "dossier" in ev.get("doc_id", ""):
                approved_claims.append({
                    "id": ev.get("doc_id", "doc-claim"),
                    "text": ev.get("text", ev.get("claim", "")),
                    "status": "SUPPORTED",
                })

        has_explicit_dependencies = (
            bool(context.get("require_dependencies"))
            or any(
                k in context
                for k in (
                    "claims_dossier",
                    "customer_voice_analysis",
                    "competitor_intelligence",
                    "approved_claims",
                    "supported_claims",
                    "claims",
                    "objections",
                    "objection_profiles",
                    "customer_objections",
                    "competitor_signals",
                    "competitor",
                    "benchmark_price",
                )
            )
            or any(
                k in grant.cts_state
                for k in (
                    "claims_dossier",
                    "customer_voice_analysis",
                    "competitor_intelligence",
                    "approved_claims",
                    "supported_claims",
                    "claims",
                    "objections",
                    "objection_profiles",
                    "customer_objections",
                    "competitor_signals",
                )
            )
        )

        if not approved_claims and has_explicit_dependencies:
            raise ValueError(
                "Missing or invalid T16 dependency: Verified product/claims evidence is required to formulate strategy."
            )

        # -------------------------------------------------------------
        # 2. Verify T17: Customer Voice & Objection Profiles
        # -------------------------------------------------------------
        objections: list[dict[str, Any]] = []

        # Check customer voice analysis result object or JSON
        analysis = (
            context.get("customer_voice_analysis")
            or grant.cts_state.get("customer_voice_analysis")
        )
        if analysis:
            if isinstance(analysis, dict):
                a_tenant = analysis.get("tenant_id")
                if a_tenant and a_tenant != grant_tenant:
                    raise ValueError(
                        f"Tenant isolation breach in T17 customer voice: analysis tenant '{a_tenant}' "
                        f"does not match grant tenant '{grant_tenant}'."
                    )
                for p in analysis.get("objection_profiles", []):
                    if isinstance(p, dict):
                        objections.append(p)
            elif isinstance(analysis, str):
                try:
                    parsed_a = json.loads(analysis)
                    if isinstance(parsed_a, dict):
                        a_tenant = parsed_a.get("tenant_id")
                        if a_tenant and a_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in T17 customer voice: analysis tenant '{a_tenant}' "
                                f"does not match grant tenant '{grant_tenant}'."
                            )
                        for p in parsed_a.get("objection_profiles", []):
                            if isinstance(p, dict):
                                objections.append(p)
                except json.JSONDecodeError:
                    pass

        raw_objections = (
            context.get("objections")
            or context.get("objection_profiles")
            or context.get("customer_objections")
            or grant.cts_state.get("objections")
        )
        if raw_objections and isinstance(raw_objections, list):
            for idx, obj in enumerate(raw_objections):
                if isinstance(obj, dict):
                    o_tenant = obj.get("tenant_id")
                    if o_tenant and o_tenant != grant_tenant:
                        raise ValueError(
                            f"Tenant isolation breach in T17 objections: objection tenant '{o_tenant}' "
                            f"does not match grant tenant '{grant_tenant}'."
                        )
                    objections.append(obj)
                else:
                    objections.append({
                        "objection_id": f"obj-{idx + 1}",
                        "theme": str(obj),
                        "frequency": 1,
                    })

        for ev in grant.validated_evidence:
            if "objection" in ev or "sentiment" in ev or "feedback" in ev.get("doc_id", ""):
                objections.append({
                    "objection_id": ev.get("doc_id", "ev-obj"),
                    "theme": ev.get("theme", ev.get("objection", ev.get("text", ""))),
                    "frequency": 1,
                })

        if not objections and has_explicit_dependencies:
            raise ValueError(
                "Missing or invalid T17 dependency: Anonymized customer voice insights and objection profiles are required to formulate strategy."
            )

        # -------------------------------------------------------------
        # 3. Verify T18: Competitor Intelligence & Market Signals
        # -------------------------------------------------------------
        competitor_signals: dict[str, Any] = {}

        raw_comp = (
            context.get("competitor_intelligence")
            or context.get("competitor_signals")
            or context.get("competitor")
            or grant.cts_state.get("competitor_intelligence")
            or grant.cts_state.get("competitor_signals")
        )
        if raw_comp:
            if isinstance(raw_comp, dict):
                c_tenant = raw_comp.get("tenant_id")
                if c_tenant and c_tenant != grant_tenant:
                    raise ValueError(
                        f"Tenant isolation breach in T18 competitor intel: competitor tenant '{c_tenant}' "
                        f"does not match grant tenant '{grant_tenant}'."
                    )
                competitor_signals = dict(raw_comp)
            elif isinstance(raw_comp, str):
                try:
                    parsed_c = json.loads(raw_comp)
                    if isinstance(parsed_c, dict):
                        c_tenant = parsed_c.get("tenant_id")
                        if c_tenant and c_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in T18 competitor intel: competitor tenant '{c_tenant}' "
                                f"does not match grant tenant '{grant_tenant}'."
                            )
                        competitor_signals = parsed_c
                    else:
                        competitor_signals = {"competitor": raw_comp}
                except json.JSONDecodeError:
                    competitor_signals = {"competitor": raw_comp}

        if not competitor_signals and "benchmark_price" in context:
            competitor_signals = {
                "competitor": str(context.get("competitor", "MarketCompetitor")),
                "benchmark_price": str(context["benchmark_price"]),
                "active_ads": str(context.get("active_ads", "10")),
                "threat_level": str(context.get("threat_level", "medium")),
            }

        for ev in grant.validated_evidence:
            if "competitor" in ev or "pricing" in ev or "scrape" in ev.get("doc_id", ""):
                competitor_signals.update({
                    "competitor": ev.get("competitor", "Competitor"),
                    "benchmark_price": ev.get("benchmark_price", "49.99"),
                    "threat_level": ev.get("threat_level", "medium"),
                })

        if not competitor_signals and has_explicit_dependencies:
            raise ValueError(
                "Missing or invalid T18 dependency: Competitor intelligence signals are required to formulate strategy."
            )

        # -------------------------------------------------------------
        # 4. Normalize Budget Ceiling & Allowed Channels
        # -------------------------------------------------------------
        raw_budget = (
            context.get("budget_ceiling")
            or context.get("budget_cap")
            or context.get("budget")
            or grant.cts_state.get("budget_cap")
            or (grant.budget_breakdown.get("spend") if grant.budget_breakdown else None)
            or 10000.0
        )
        try:
            budget_ceiling = float(str(raw_budget))
            if budget_ceiling < 0:
                budget_ceiling = 0.0
        except (ValueError, TypeError):
            budget_ceiling = 10000.0

        # Cap against IE-authorized budget cap from grant if available
        if grant.cts_state.get("budget_cap"):
            try:
                grant_cap = float(str(grant.cts_state["budget_cap"]))
                if grant_cap >= 0:
                    budget_ceiling = min(budget_ceiling, grant_cap)
            except (ValueError, TypeError):
                pass

        # Channels from grant tenant scope (prevent context from expanding tenant scope)
        tenant_allowed = (
            [c.strip().lower() for c in grant.tenant_scope.allowed_channels if c.strip()]
            if grant.tenant_scope and grant.tenant_scope.allowed_channels
            else []
        )
        context_channels = context.get("channels")
        requested_channels: list[str] = []
        if context_channels:
            if isinstance(context_channels, list):
                requested_channels = [str(c).strip().lower() for c in context_channels if str(c).strip()]
            elif isinstance(context_channels, str):
                requested_channels = [c.strip().lower() for c in context_channels.split(",") if c.strip()]

        if tenant_allowed and requested_channels:
            allowed_channels = [c for c in requested_channels if c in tenant_allowed]
            if not allowed_channels:
                allowed_channels = list(tenant_allowed)
        elif tenant_allowed:
            allowed_channels = list(tenant_allowed)
        elif requested_channels:
            allowed_channels = requested_channels
        else:
            allowed_channels = ["meta", "google", "tiktok", "linkedin"]

        time_horizon = str(context.get("time_horizon", grant.cts_state.get("time_horizon", "90_days")))

        # Policy & Brand constraints
        constraints: list[str] = list(grant.policy_constraints)
        if grant.brand_rules:
            constraints.extend(f"{k}:{v}" for k, v in grant.brand_rules.items())
        raw_constraints = context.get("constraints")
        if isinstance(raw_constraints, list):
            constraints.extend(str(c) for c in raw_constraints)

        return (
            budget_ceiling,
            allowed_channels,
            approved_claims,
            objections,
            competitor_signals,
            time_horizon,
            constraints,
        )

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        """Formulate deterministic S_ALLOC execution payload from verified dependencies."""
        (
            budget_ceiling,
            allowed_channels,
            approved_claims,
            objections,
            competitor_signals,
            time_horizon,
            constraints,
        ) = self._verify_and_normalize_dependencies(grant, context)

        # Validate typed StrategyDirective boundary before sandbox serialization
        StrategyDirective.from_grant(
            grant,
            {
                **context,
                "budget_ceiling": budget_ceiling,
                "channels": allowed_channels,
                "time_horizon": time_horizon,
            },
        )

        channels_str = ",".join(allowed_channels)
        tenant_id = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"

        payload: dict[str, str] = {
            "task_id": grant.task_id,
            "tenant_id": tenant_id,
            "brand_id": grant.brand_id,
            "operation": "optimize_budget",
            "objective": grant.objective or "propose_omnichannel_strategy_and_media_allocation",
            "budget": str(budget_ceiling),
            "budget_cap": str(budget_ceiling),
            "budget_ceiling": str(budget_ceiling),
            "channels": channels_str,
            "allowed_channels": channels_str,
            "time_horizon": time_horizon,
            "t16_claims": json.dumps(approved_claims),
            "t17_objections": json.dumps(objections),
            "t18_competitor": json.dumps(competitor_signals),
            "constraints": json.dumps(constraints),
        }

        # Pass through optional modeling telemetry and constraints if present in context
        for opt_key in (
            "kpi_name",
            "media_history",
            "performance_telemetry",
            "control_variables",
            "incrementality_evidence",
            "channel_constraints",
            "s_alloc_reasoning",
        ):
            if opt_key in context:
                val = context[opt_key]
                payload[opt_key] = json.dumps(val) if isinstance(val, (dict, list)) else str(val)

        # Pass through any explicit ROAS priors in context
        for ch in allowed_channels:
            prior_key = f"prior_roas_{ch}"
            if prior_key in context:
                payload[prior_key] = str(context[prior_key])

        return payload

    def interpret_result(
        self, sanitized_output: dict[str, str]
    ) -> tuple[list[str], ConfidenceInterval]:
        """Interpret S_ALLOC sanitized output into structured findings and confidence interval."""
        evidence: list[str] = []

        plan_data: dict[str, Any] = {}
        if "strategy_plan" in sanitized_output:
            try:
                plan_data = json.loads(sanitized_output["strategy_plan"])
            except Exception:
                pass

        if plan_data:
            plan_id = plan_data.get("plan_id", "strat-unknown")
            budget_ceiling = plan_data.get("budget_ceiling", 0.0)
            total_allocated = plan_data.get("total_allocated", 0.0)
            rec_scenario = plan_data.get("recommended_scenario", "balanced")
            blended_roas = sanitized_output.get("expected_blended_roas", "0.0")

            evidence.append(
                f"Omnichannel Strategy Plan [{plan_id}]: Total Allocated: ${total_allocated:,.2f} "
                f"(Ceiling: ${budget_ceiling:,.2f}) | Recommended Scenario: {rec_scenario} | "
                f"Expected Blended ROAS: {blended_roas}x"
            )

            # Channel allocations breakdown
            ch_allocs = plan_data.get("channel_allocations", [])
            for ca in ch_allocs:
                if isinstance(ca, dict):
                    ch = ca.get("channel", "unknown")
                    amt = ca.get("allocated_amount", 0.0)
                    pct = ca.get("percentage_of_total", 0.0)
                    role = ca.get("role", "")
                    evidence.append(f"Channel [{ch.upper()}]: ${amt:,.2f} ({pct}%) — Role: {role}")

            # Funnel stages breakdown
            stages = plan_data.get("funnel_stages", [])
            for st in stages:
                if isinstance(st, dict):
                    st_name = st.get("stage_name", st.get("stage", ""))
                    amt = st.get("allocated_amount", 0.0)
                    pct = st.get("percentage_of_total", 0.0)
                    hyp = st.get("transition_hypothesis", "")
                    evidence.append(f"Funnel Stage [{st_name}]: ${amt:,.2f} ({pct}%) | Hypothesis: {hyp}")

            # Scenarios
            scenarios = plan_data.get("scenarios", [])
            for sc in scenarios:
                if isinstance(sc, dict):
                    sc_name = sc.get("scenario_name", sc.get("scenario_id", ""))
                    roas = sc.get("expected_blended_roas", 0.0)
                    risk = sc.get("risk_level", "medium")
                    rec_marker = " [RECOMMENDED]" if sc.get("is_recommended") else ""
                    evidence.append(f"Scenario [{sc_name}]{rec_marker}: Expected ROAS {roas}x | Risk Tier: {risk}")

            # Assumptions and caveats
            for asm in plan_data.get("assumptions", []):
                evidence.append(f"Assumption: {asm}")
            for cav in plan_data.get("unsupported_estimates_or_caveats", []):
                evidence.append(f"Caveat / Model Limitation: {cav}")

            # Confidence
            conf_data = plan_data.get("confidence", {})
            pt = float(conf_data.get("point_estimate", 0.85))
            low = float(conf_data.get("lower_bound", 0.72))
            high = float(conf_data.get("upper_bound", 0.94))
            confidence = ConfidenceInterval(point_estimate=pt, lower_bound=low, upper_bound=high)
        else:
            # Fallback legacy parsing
            budget_total = sanitized_output.get("budget_total", "0.0")
            allocated = sanitized_output.get("allocations", "{}")
            blended_roas = sanitized_output.get("expected_blended_roas", "0.0")
            primary_ch = sanitized_output.get("primary_channel", "unknown")

            evidence.append(f"Media Allocation Proposal: Total Budget: ${budget_total} | Primary Channel: {primary_ch}")
            evidence.append(f"Expected Blended ROAS: {blended_roas}x")
            evidence.append(f"Channel Allocations: {allocated}")

            confidence = ConfidenceInterval(point_estimate=0.75, lower_bound=0.60, upper_bound=0.88)

        return evidence, confidence

    def extract_strategy_plan(self, envelope: EvidenceEnvelope) -> OmnichannelStrategyPlan | None:
        """Extract typed OmnichannelStrategyPlan from an EvidenceEnvelope."""
        raw_plan = envelope.payload.get("strategy_plan")
        if not raw_plan:
            return None
        try:
            return OmnichannelStrategyPlan.model_validate_json(raw_plan)
        except Exception:
            return None

    async def run(self, grant: TaskGrant, context: dict[str, Any]) -> EvidenceEnvelope:
        """Execute W_STRAT strategy formulation with advisory S_ALLOC reasoning."""
        if self.capability is None:
            raise PolicyViolationError(
                f"Worker {grant.worker_role.value if grant.worker_role else 'unknown'} has no authorized sandbox capability."
            )
        if self._sandbox_client is None:
            raise PolicyViolationError(
                f"Worker {grant.worker_role.value if grant.worker_role else 'unknown'} has no sandbox client configured."
            )
        capability = self.capability
        sandbox_client = self._sandbox_client

        reasoning_output: WorkerReasoningOutput | None = None
        llm_metadata: dict[str, Any] = {}

        if self._llm_client is not None:
            reasoning_output, llm_metadata = await self._reason_domain(grant, context)

        alloc_reasoning, alloc_metadata = await self._allocation_agent.reason(grant, context)

        augmented_context = dict(context)
        if "s_alloc_reasoning" not in augmented_context:
            augmented_context["s_alloc_reasoning"] = alloc_reasoning.model_dump()

        payload = self.build_payload(grant, augmented_context)
        operation = payload.get("operation", "default")
        egress_grant = context.get("egress_grant")
        mandate = SandboxInvocationMandate(
            task_id=grant.task_id,
            worker_role=grant.worker_role,
            tenant_id=grant.tenant_scope.tenant_id if grant.tenant_scope else "default",
            capability=capability,
            operation=operation,
            payload=payload,
            network_policy=NetworkPolicy.DISABLED,
            egress_grant=egress_grant,  # type: ignore[arg-type]
            timeout_seconds=grant.token_budget if grant.token_budget > 0 else 120,
        )
        result = await sandbox_client.invoke(mandate)

        findings: list[str] = []
        artifacts: list[str] = []
        risks: list[str] = []

        if reasoning_output:
            findings.extend(reasoning_output.preliminary_findings)
            risks.extend(reasoning_output.identified_risks)

        findings.append(
            f"S_ALLOC Advisory: Scenario '{alloc_reasoning.scenario_emphasis}' "
            f"prioritizing {', '.join(alloc_reasoning.kpi_priorities)}."
        )
        if alloc_reasoning.rationale_summary:
            findings.append(f"S_ALLOC Rationale: {alloc_reasoning.rationale_summary}")
        risks.extend(alloc_reasoning.risk_flags)

        if not result.success:
            evidence = [f"sandbox execution failed: {result.error or 'unknown error'}"]
            confidence = ConfidenceInterval(point_estimate=0.0, lower_bound=0.0, upper_bound=0.0)
            risks.append(result.error or "sandbox execution failed")
        else:
            evidence, confidence = self.interpret_result(result.sanitized_output)
            findings.extend([line for line in evidence if not line.startswith("error")])
            if "strategy_plan" in result.sanitized_output or "strategy_roadmap" in result.sanitized_output:
                artifacts.append(f"strategy:{grant.task_id}")
            if result.generated_artifacts:
                artifacts.extend(result.generated_artifacts)

        findings = sorted(list(set(findings)))
        artifacts = sorted(list(set(artifacts)))
        risks = sorted(list(set(risks)))

        provenance: dict[str, Any] = {
            "agent": grant.worker_role.value if grant.worker_role else "unknown",
            "capability": capability.value,
            "task_id": grant.task_id,
            "execution_id": result.execution_id,
            "sandbox_execution_id": result.execution_id,
            "status": result.status.value,
        }
        if llm_metadata:
            provenance.update({
                "llm_reasoning_used": "true",
                "llm_provider": str(llm_metadata.get("provider", "unset")),
                "llm_model": str(llm_metadata.get("actual_model", "unset")),
                "is_local_model": "true" if llm_metadata.get("is_local") else "false",
                "prompt_tokens": str(llm_metadata.get("prompt_tokens", 0)),
                "completion_tokens": str(llm_metadata.get("completion_tokens", 0)),
                "total_tokens": str(llm_metadata.get("total_tokens", 0)),
                "estimated_cost_usd": str(llm_metadata.get("estimated_cost_usd", 0.0)),
                "governed_tools_authorized": ",".join(reasoning_output.selected_tools) if reasoning_output else "",
            })
        if alloc_metadata:
            provenance.update({
                "s_alloc_reasoning_used": "true",
                "s_alloc_llm_model": str(alloc_metadata.get("actual_model", alloc_metadata.get("reasoning_mode", "fallback"))),
                "s_alloc_llm_provider": str(alloc_metadata.get("provider", "local")),
                "s_alloc_scenario_emphasis": alloc_reasoning.scenario_emphasis,
                "s_alloc_confidence": str(alloc_reasoning.estimated_confidence),
                "s_alloc_total_tokens": str(alloc_metadata.get("total_tokens", 0)),
            })
            if "profile_id" in alloc_metadata:
                provenance["s_alloc_profile_id"] = str(alloc_metadata["profile_id"])
            if "profile_digest" in alloc_metadata:
                provenance["s_alloc_profile_digest"] = str(alloc_metadata["profile_digest"])
        if result.provenance:
            provenance.update(result.provenance)

        envelope = EvidenceEnvelope(
            task_id=grant.task_id,
            worker_role=grant.worker_role,
            confidence=confidence,
            evidence=evidence,
            payload=result.sanitized_output,
            findings=findings,
            generated_artifacts=artifacts,
            supporting_evidence=evidence,
            provenance=provenance,
            proposed_state_changes={
                "status": "completed" if result.success else "failed",
                "capability": capability.value,
            },
            unresolved_risks_or_assumptions=risks,
        )
        return StrategyResultEnvelope.from_evidence_envelope(envelope)