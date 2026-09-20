"""W_CREAT: Layer-5 Creative & Content Engine coordinator.

Coordinates the deterministic creative workflow, enforces strict claim grounding
and scope boundaries, and packages QA-approved immutable artifacts for IE/HITL handoff.
W_CREAT operates with purpose-scoped LLM planning and ZERO sandbox capability.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import BoundedWorkerAgent
from app.core.exceptions import PolicyViolationError
from app.orchestration.creative_content_workflow import CreativeContentWorkflow
from app.schemas.agent_contracts import (
    ConfidenceInterval,
    CreativePackage,
    CreativePlan,
    EvidenceEnvelope,
    QAStatus,
    TaskGrant,
)
from app.schemas.governance import WorkerRole


class CreativeContentAgent(BoundedWorkerAgent):
    """W_CREAT Creative & Content Engine Coordinator.

    Converts verified product evidence (T16) and approved omnichannel strategy (T19)
    into channel-ready creative drafts, hooks, CTAs, visual briefs, social-post
    variants, and content schedules through governed workflow execution.

    Operates with purpose-scoped LLM reasoning and ZERO sandbox capability.
    Enforces strict claim grounding: all factual statements must map to T16-approved
    evidence without fallback fabrication. Policy constraints strictly override brand persona.
    """

    capability = None

    def __init__(
        self,
        sandbox_client: Any = None,
        llm_client: Any = None,
        workflow: CreativeContentWorkflow | None = None,
    ) -> None:
        if sandbox_client is not None:
            raise PolicyViolationError(
                "W_CREAT coordinator is zero-sandbox and must not receive a SandboxClient."
            )
        super().__init__(sandbox_client=None, llm_client=llm_client)
        self._workflow = workflow or CreativeContentWorkflow()

    def build_payload(self, grant: TaskGrant, context: dict[str, Any]) -> dict[str, str]:
        """Reject sandbox payload construction: W_CREAT has zero sandbox capability."""
        raise PolicyViolationError(
            f"Worker {grant.worker_role.value if grant.worker_role else 'W_CREAT'} "
            "has zero sandbox capability and must not formulate sandbox payloads."
        )

    def _verify_and_normalize_dependencies(
        self, grant: TaskGrant, context: dict[str, object]
    ) -> tuple[
        list[dict[str, Any]],
        dict[str, Any],
        list[str],
        list[str],
        list[str],
        list[str],
        str,
        str,
        str,
    ]:
        """Verify presence and validity of T16 and T19 dependencies and enforce tenant isolation.

        Fails closed strictly if required dependency evidence is missing, off-tenant,
        or unauthorized. Never fabricates claims, channels, or strategies.
        """
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"

        # -------------------------------------------------------------
        # 1. Verify T16: Product Evidence & Approved Claims
        # -------------------------------------------------------------
        approved_claims: list[dict[str, Any]] = []

        dossier = context.get("claims_dossier") or grant.cts_state.get("claims_dossier")
        if dossier:
            if isinstance(dossier, dict):
                d_tenant = dossier.get("tenant_id")
                if d_tenant and d_tenant != grant_tenant:
                    raise ValueError(
                        f"Tenant isolation breach in T16 product evidence: dossier tenant "
                        f"'{d_tenant}' does not match grant tenant '{grant_tenant}'."
                    )
                for c in dossier.get("claims", []):
                    if isinstance(c, dict) and (
                        c.get("validation_status") in ("SUPPORTED", "VALIDATED")
                        or float(str(c.get("confidence", 0.0))) >= 0.7
                    ):
                        approved_claims.append(c)
            elif isinstance(dossier, str):
                try:
                    parsed_d = json.loads(dossier)
                    if isinstance(parsed_d, dict):
                        d_tenant = parsed_d.get("tenant_id")
                        if d_tenant and d_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in T16 product evidence: dossier tenant "
                                f"'{d_tenant}' does not match grant tenant '{grant_tenant}'."
                            )
                        for c in parsed_d.get("claims", []):
                            if isinstance(c, dict) and (
                                c.get("validation_status") in ("SUPPORTED", "VALIDATED")
                                or float(str(c.get("confidence", 0.0))) >= 0.7
                            ):
                                approved_claims.append(c)
                except json.JSONDecodeError:
                    pass

        raw_claims = (
            context.get("approved_claims")
            or context.get("supported_claims")
            or context.get("claims")
            or grant.cts_state.get("approved_claims")
            or grant.cts_state.get("claims")
        )
        if raw_claims:
            if isinstance(raw_claims, list):
                for rc in raw_claims:
                    if isinstance(rc, dict):
                        rc_tenant = rc.get("tenant_id")
                        if rc_tenant and rc_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in T16 claims item: tenant '{rc_tenant}' "
                                f"does not match grant tenant '{grant_tenant}'."
                            )
                        status = rc.get("validation_status", rc.get("status", "SUPPORTED"))
                        if (
                            status in ("SUPPORTED", "VALIDATED")
                            or float(str(rc.get("confidence", 1.0))) >= 0.7
                        ):
                            approved_claims.append(rc)
                    elif isinstance(rc, str):
                        approved_claims.append({"id": f"claim-{len(approved_claims)}", "text": rc})
            elif isinstance(raw_claims, str):
                try:
                    parsed_rc = json.loads(raw_claims)
                    if isinstance(parsed_rc, list):
                        for rc in parsed_rc:
                            if isinstance(rc, dict):
                                rc_tenant = rc.get("tenant_id")
                                if rc_tenant and rc_tenant != grant_tenant:
                                    raise ValueError(
                                        "Tenant isolation breach in T16 claims item: tenant "
                                        f"'{rc_tenant}' does not match grant tenant "
                                        f"'{grant_tenant}'."
                                    )
                                status = rc.get("validation_status", rc.get("status", "SUPPORTED"))
                                if (
                                    status in ("SUPPORTED", "VALIDATED")
                                    or float(str(rc.get("confidence", 1.0))) >= 0.7
                                ):
                                    approved_claims.append(rc)
                    else:
                        approved_claims.append({"id": "claim-0", "text": str(parsed_rc)})
                except json.JSONDecodeError:
                    approved_claims.append({"id": "claim-0", "text": raw_claims})

        if not approved_claims:
            raise ValueError(
                f"Missing or invalid T16 Product Evidence dependency: No supported product claims "
                f"found for tenant '{grant_tenant}' in context or CTS state."
            )

        # Standardize claim IDs
        for i, c in enumerate(approved_claims):
            if "id" not in c:
                c["id"] = c.get("claim_id", f"claim-{i}")

        # -------------------------------------------------------------
        # 2. Verify T19: Omnichannel Strategy Plan
        # -------------------------------------------------------------
        strategy_plan: dict[str, Any] = {}
        strat_obj = (
            context.get("strategy_plan")
            or context.get("strategy")
            or context.get("omnichannel_strategy")
            or grant.cts_state.get("strategy_plan")
            or grant.cts_state.get("strategy")
        )

        if strat_obj:
            if isinstance(strat_obj, dict):
                s_tenant = strat_obj.get("tenant_id")
                if s_tenant and s_tenant != grant_tenant:
                    raise ValueError(
                        f"Tenant isolation breach in T19 omnichannel strategy: strategy tenant "
                        f"'{s_tenant}' does not match grant tenant '{grant_tenant}'."
                    )
                strategy_plan = strat_obj
            elif isinstance(strat_obj, str):
                try:
                    parsed_s = json.loads(strat_obj)
                    if isinstance(parsed_s, dict):
                        s_tenant = parsed_s.get("tenant_id")
                        if s_tenant and s_tenant != grant_tenant:
                            raise ValueError(
                                "Tenant isolation breach in T19 omnichannel strategy: strategy "
                                f"tenant '{s_tenant}' does not match grant tenant '{grant_tenant}'."
                            )
                        strategy_plan = parsed_s
                except json.JSONDecodeError:
                    pass
            elif hasattr(strat_obj, "model_dump"):
                dumped = strat_obj.model_dump()
                s_tenant = dumped.get("tenant_id")
                if s_tenant and s_tenant != grant_tenant:
                    raise ValueError(
                        f"Tenant isolation breach in T19 omnichannel strategy: strategy tenant "
                        f"'{s_tenant}' does not match grant tenant '{grant_tenant}'."
                    )
                strategy_plan = dumped

        if not strategy_plan:
            raise ValueError(
                f"Missing or invalid T19 Omnichannel Strategy dependency: No strategy plan "
                f"found for tenant '{grant_tenant}' in context or CTS state."
            )

        # -------------------------------------------------------------
        # 3. Channels from Strategy & Grant Scope (No default fabrication)
        # -------------------------------------------------------------
        raw_channels: list[str] = []
        if "channel_allocations" in strategy_plan:
            for ca in strategy_plan["channel_allocations"]:
                if isinstance(ca, dict) and "channel" in ca:
                    raw_channels.append(str(ca["channel"]).strip().lower())
                elif hasattr(ca, "channel"):
                    raw_channels.append(str(ca.channel).strip().lower())

        if not raw_channels and "channels" in strategy_plan:
            c_val = strategy_plan["channels"]
            if isinstance(c_val, list):
                raw_channels = [str(c).strip().lower() for c in c_val if str(c).strip()]
            elif isinstance(c_val, str):
                raw_channels = [c.strip().lower() for c in c_val.split(",") if c.strip()]

        # Cross-reference against grant allowed_channels
        if grant.tenant_scope and grant.tenant_scope.allowed_channels:
            allowed_set = {
                c.strip().lower() for c in grant.tenant_scope.allowed_channels if c.strip()
            }
            channels = [c for c in raw_channels if c in allowed_set]
        else:
            channels = raw_channels

        if not channels:
            raise ValueError(
                f"No valid authorized channels found for tenant '{grant_tenant}' "
                f"within grant scope."
            )

        # Deduplicate channels preserving order
        deduped_ch: list[str] = []
        seen_ch: set[str] = set()
        for c in channels:
            if c not in seen_ch:
                seen_ch.add(c)
                deduped_ch.append(c)
        channels = deduped_ch

        # -------------------------------------------------------------
        # 4. Policy Precedence & Brand Persona Rules
        # -------------------------------------------------------------
        policy_rules = (
            list(getattr(grant, "policy_constraints", []))
            if getattr(grant, "policy_constraints", None)
            else []
        )
        context_policy = context.get("policy_constraints")
        if context_policy:
            if isinstance(context_policy, list):
                policy_rules.extend([str(p) for p in context_policy])
            elif isinstance(context_policy, str):
                policy_rules.extend([p.strip() for p in context_policy.split(",") if p.strip()])

        persona = context.get("brand_persona")
        brand_voice = getattr(persona, "voice", "authoritative")
        persona_prohibited = getattr(persona, "prohibited_terms", ())
        persona_disclaimers = getattr(persona, "required_disclaimers", ())

        prohibited_terms_set: set[str] = set()
        for term in persona_prohibited:
            if term:
                prohibited_terms_set.add(str(term).strip().lower())
        for rule in policy_rules:
            if "prohibit" in rule.lower() or "forbid" in rule.lower() or "block" in rule.lower():
                clean_term = rule.replace("prohibit:", "").replace("prohibit", "").strip().lower()
                if clean_term:
                    prohibited_terms_set.add(clean_term)

        raw_proh = context.get("prohibited_terms")
        if raw_proh:
            if isinstance(raw_proh, list):
                for p in raw_proh:
                    prohibited_terms_set.add(str(p).strip().lower())
            elif isinstance(raw_proh, str):
                for p in raw_proh.split(","):
                    if p.strip():
                        prohibited_terms_set.add(p.strip().lower())

        required_disclaimers: list[str] = []
        for d in persona_disclaimers:
            if d and str(d).strip():
                required_disclaimers.append(str(d).strip())

        context_disclaimers = context.get("required_disclaimers")
        if context_disclaimers:
            if isinstance(context_disclaimers, list):
                for d in context_disclaimers:
                    if str(d).strip() not in required_disclaimers:
                        required_disclaimers.append(str(d).strip())
            elif isinstance(context_disclaimers, str):
                for d in context_disclaimers.split(";"):
                    if d.strip() and d.strip() not in required_disclaimers:
                        required_disclaimers.append(d.strip())

        # -------------------------------------------------------------
        # 5. Check for Unsupported Claims
        # -------------------------------------------------------------
        unapproved_claims: list[str] = []
        approved_texts = [
            str(c.get("text", c.get("claim_text", ""))).strip().lower() for c in approved_claims
        ]
        raw_unverified = context.get("unapproved_claims") or context.get("raw_claims")
        if raw_unverified:
            candidates: list[str] = []
            if isinstance(raw_unverified, list):
                for item in raw_unverified:
                    t = item.get("text", str(item)) if isinstance(item, dict) else str(item)
                    candidates.append(t)
            elif isinstance(raw_unverified, str):
                candidates = [raw_unverified]
            for cand in candidates:
                if cand.strip().lower() not in approved_texts:
                    unapproved_claims.append(cand.strip())

        objective = str(
            grant.objective
            or context.get("objective")
            or strategy_plan.get("objective")
            or "enterprise campaign"
        )
        target_audience = str(
            context.get("target_audience")
            or strategy_plan.get("target_audience")
            or "target audience"
        )

        return (
            approved_claims,
            strategy_plan,
            channels,
            sorted(list(prohibited_terms_set)),
            required_disclaimers,
            unapproved_claims,
            brand_voice,
            objective,
            target_audience,
        )

    async def run(self, grant: TaskGrant, context: dict[str, Any]) -> EvidenceEnvelope:
        """Execute W_CREAT coordination: validate grant, plan, coordinate workflow, and package."""
        if grant.worker_role != WorkerRole.CREATIVE_CONTENT:
            raise PolicyViolationError(
                f"Worker role mismatch: expected '{WorkerRole.CREATIVE_CONTENT.value}', "
                f"got '{grant.worker_role.value if grant.worker_role else 'None'}'."
            )

        # 1. Validate dependencies & scope (fails closed if missing or off-tenant)
        (
            approved_claims,
            strategy_plan,
            channels,
            prohibited_terms,
            required_disclaimers,
            unapproved_claims,
            brand_voice,
            objective,
            target_audience,
        ) = self._verify_and_normalize_dependencies(grant, context)

        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        claim_ids = [str(c["id"]) for c in approved_claims]

        # 2. W_CREAT LLM Planning: produce bounded CreativePlan
        llm_metadata: dict[str, Any] = {}
        if self._llm_client is not None:
            system_prompt = (
                "You are W_CREAT, the Layer-5 Creative coordinator in Enterprise OS. "
                "Produce a structured CreativePlan strictly bounded by the supplied TaskGrant, "
                "approved channels, and approved evidence manifest. "
                "Boundaries: "
                "- Zero direct access to databases, RAG, or outbound APIs (Model A). "
                "- Zero sandbox capability. Tool execution occurs in specialist sandboxes. "
                "- You must not expand channel scope or invent unsupported claims."
            )
            grant_summary = {
                "task_id": grant.task_id,
                "tenant_id": grant_tenant,
                "brand_id": grant.brand_id,
                "objective": objective,
                "target_audience": target_audience,
                "approved_channels": channels,
                "approved_claims": claim_ids,
                "prohibited_terms": prohibited_terms,
            }
            try:
                (
                    plan_candidate,
                    llm_metadata,
                ) = await self._llm_client.generate_structured_with_metadata(
                    system_prompt=system_prompt,
                    user_prompt=json.dumps(grant_summary, sort_keys=True),
                    response_model=CreativePlan,
                )
                plan = plan_candidate
            except Exception:
                plan = CreativePlan(
                    tenant_id=grant_tenant,
                    task_id=grant.task_id,
                    approved_objectives=[objective],
                    approved_channels=channels,
                    required_deliverables=["copy_pack", "visual_pack", "adapted_pack"],
                    evidence_manifest=claim_ids,
                    prohibited_scope=prohibited_terms,
                    expected_artifact_types=[
                        "AdCopyVariant",
                        "VisualBrief",
                        "SocialPostVariant",
                        "ContentScheduleItem",
                    ],
                    target_audience=target_audience,
                )
        else:
            plan = CreativePlan(
                tenant_id=grant_tenant,
                task_id=grant.task_id,
                approved_objectives=[objective],
                approved_channels=channels,
                required_deliverables=["copy_pack", "visual_pack", "adapted_pack"],
                evidence_manifest=claim_ids,
                prohibited_scope=prohibited_terms,
                expected_artifact_types=[
                    "AdCopyVariant",
                    "VisualBrief",
                    "SocialPostVariant",
                    "ContentScheduleItem",
                ],
                target_audience=target_audience,
            )

        # 3. Post-planning scope validation: CreativePlan cannot expand grant scope
        for ch in plan.approved_channels:
            if ch not in channels:
                raise PolicyViolationError(
                    f"CreativePlan expanded channel scope to unauthorized channel: '{ch}'. "
                    f"Authorized channels: {channels}."
                )
        for cid in plan.evidence_manifest:
            if cid not in claim_ids:
                raise PolicyViolationError(
                    f"CreativePlan introduced unapproved evidence claim: '{cid}'. "
                    f"Authorized claims: {claim_ids}."
                )
        plan.compute_artifact_hash()

        # 4. Invoke existing Creative workflow boundary
        workflow_context = {
            **context,
            "required_disclaimers": ";".join(required_disclaimers),
            "brand_voice": brand_voice,
            "unapproved_claims": unapproved_claims,
        }
        workflow_result = await self._workflow.run(
            grant=grant,
            plan=plan,
            context=workflow_context,
        )

        qa_report = workflow_result.qa_report

        # 5. Handle QA Evaluation (BLOCK, REVISE, PASS)
        if qa_report.status == QAStatus.BLOCK:
            return EvidenceEnvelope(
                task_id=grant.task_id,
                worker_role=grant.worker_role,
                confidence=ConfidenceInterval(point_estimate=0.0, lower_bound=0.0, upper_bound=0.0),
                evidence=[f"QA Evaluation BLOCKED: {f.message}" for f in qa_report.findings],
                payload={"qa_report": qa_report.model_dump_json()},
                findings=[f.message for f in qa_report.findings],
                generated_artifacts=[],
                supporting_evidence=[],
                provenance={
                    "agent": "W_CREAT",
                    "capability": "NONE",
                    "task_id": grant.task_id,
                    "plan_hash": plan.artifact_hash,
                    "qa_report_hash": qa_report.artifact_hash,
                    "qa_status": QAStatus.BLOCK.value,
                },
                proposed_state_changes={"status": "blocked", "qa_status": QAStatus.BLOCK.value},
                unresolved_risks_or_assumptions=[
                    f"Creative deliverable blocked by QA: {qa_report.reason_code or 'BLOCK'}"
                ],
            )

        if qa_report.status == QAStatus.REVISE:
            return EvidenceEnvelope(
                task_id=grant.task_id,
                worker_role=grant.worker_role,
                confidence=ConfidenceInterval(point_estimate=0.4, lower_bound=0.2, upper_bound=0.6),
                evidence=[
                    f"QA Revision Required ({qa_report.reason_code}): {f.message}"
                    for f in qa_report.findings
                ],
                payload={"qa_report": qa_report.model_dump_json()},
                findings=[f.message for f in qa_report.findings],
                generated_artifacts=[],
                supporting_evidence=[],
                provenance={
                    "agent": "W_CREAT",
                    "capability": "NONE",
                    "task_id": grant.task_id,
                    "plan_hash": plan.artifact_hash,
                    "qa_report_hash": qa_report.artifact_hash,
                    "qa_status": QAStatus.REVISE.value,
                },
                proposed_state_changes={
                    "status": "needs_revision",
                    "qa_status": QAStatus.REVISE.value,
                },
                unresolved_risks_or_assumptions=[
                    f"Creative deliverable requires revision: {qa_report.reason_code or 'REVISE'}"
                ],
            )

        # 6. Package unchanged QA-approved artifacts (Zero Post-QA Content Mutation)
        ad_variants = (
            workflow_result.adapted_pack.ad_copy_variants
            if workflow_result.adapted_pack
            else (workflow_result.copy_pack.variants if workflow_result.copy_pack else [])
        )
        visual_briefs = (
            workflow_result.adapted_pack.visual_briefs
            if workflow_result.adapted_pack
            else (
                workflow_result.visual_pack.production_briefs if workflow_result.visual_pack else []
            )
        )
        social_posts = (
            workflow_result.adapted_pack.social_posts if workflow_result.adapted_pack else []
        )
        schedules = (
            workflow_result.adapted_pack.calendar_proposal if workflow_result.adapted_pack else []
        )

        package = CreativePackage(
            package_id=f"pkg-{grant.task_id}",
            tenant_id=grant_tenant,
            brand_id=grant.brand_id or "default",
            objective=objective,
            target_audience=target_audience,
            funnel_stage="full_funnel",
            ad_copy_variants=ad_variants,
            social_posts=social_posts,
            visual_briefs=visual_briefs,
            schedules=schedules,
            approved_claim_refs=claim_ids,
            flagged_unsupported_claims=unapproved_claims,
            compliance_warnings=[],
            persona_voice=brand_voice,
            provenance={
                "coordinator": "W_CREAT",
                "plan_hash": plan.artifact_hash,
                "qa_hash": qa_report.artifact_hash,
            },
            confidence=ConfidenceInterval(point_estimate=0.88, lower_bound=0.78, upper_bound=0.95),
            claim_evidence_refs=claim_ids,
            qa_status=QAStatus.PASS.value,
            qa_findings=[f.message for f in qa_report.findings],
            artifact_hashes=workflow_result.artifact_hashes,
        )

        artifacts = [
            f"creative:{grant.task_id}",
            f"copy:{grant.task_id}",
        ]
        evidence_lines = [
            (
                f"Creative Package [{package.package_id}]: Objective: {objective} | "
                f"Audience: {target_audience} | Brand Voice: {brand_voice}"
            ),
            f"Ad Copy Variants Generated: {len(ad_variants)}",
            f"Visual Direction Briefs: {len(visual_briefs)}",
            f"Content Release Schedule: {len(schedules)} slots planned",
            (
                f"QA Status: {qa_report.status.value} (Approved Hash: "
                f"{qa_report.evaluated_artifact_hash[:16]}...)"
            ),
        ]
        for f in unapproved_claims:
            evidence_lines.append(f"Warning: Unsupported claim flagged and excluded: {f}")

        provenance = {
            "agent": "W_CREAT",
            "capability": "NONE",
            "task_id": grant.task_id,
            "plan_hash": plan.artifact_hash,
            "qa_report_hash": qa_report.artifact_hash,
            "qa_status": QAStatus.PASS.value,
        }
        if llm_metadata:
            provenance.update(
                {
                    "llm_planning_used": "true",
                    "llm_provider": str(llm_metadata.get("provider", "unset")),
                    "llm_model": str(llm_metadata.get("actual_model", "unset")),
                    "prompt_tokens": str(llm_metadata.get("prompt_tokens", 0)),
                    "completion_tokens": str(llm_metadata.get("completion_tokens", 0)),
                    "total_tokens": str(llm_metadata.get("total_tokens", 0)),
                }
            )

        return EvidenceEnvelope(
            task_id=grant.task_id,
            worker_role=grant.worker_role,
            confidence=ConfidenceInterval(point_estimate=0.88, lower_bound=0.78, upper_bound=0.95),
            evidence=evidence_lines,
            payload={"creative_package": package.model_dump_json()},
            findings=sorted(list(set(evidence_lines + workflow_result.findings))),
            generated_artifacts=artifacts,
            supporting_evidence=evidence_lines,
            provenance=provenance,
            proposed_state_changes={
                "status": "completed",
                "capability": "NONE",
                "qa_status": QAStatus.PASS.value,
            },
            unresolved_risks_or_assumptions=[],
        )

    def extract_creative_package(self, envelope: EvidenceEnvelope) -> CreativePackage | None:
        """Helper to extract strongly typed CreativePackage from an EvidenceEnvelope."""
        raw_pkg = envelope.payload.get("creative_package")
        if not raw_pkg:
            return None
        if isinstance(raw_pkg, str):
            try:
                return CreativePackage.model_validate_json(raw_pkg)
            except Exception:
                return None
        if isinstance(raw_pkg, dict):
            try:
                return CreativePackage.model_validate(raw_pkg)
            except Exception:
                return None
        return None
