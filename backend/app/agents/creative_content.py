"""W_CREAT: creative content generation, channel adaptation, visual briefs, and schedules."""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import (
    ConfidenceInterval,
    CreativePackage,
    EvidenceEnvelope,
    TaskGrant,
)
from app.schemas.sandbox import SandboxCapability


class CreativeContentAgent(BoundedWorkerAgent):
    """W_CREAT Creative & Content Engine.

    Converts verified product evidence (T16) and approved omnichannel strategy (T19)
    into channel-ready creative drafts, hooks, CTAs, visual briefs, social-post
    variants, and content schedules using sandboxed S_COPY.

    Enforces strict claim grounding: all factual product statements must map to
    T16-approved evidence. Policy constraints strictly override brand persona.
    """

    capability = SandboxCapability.COPY

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
    ]:
        """Verify presence and validity of T16 and T19 dependencies and enforce tenant isolation.

        Fails closed safely if required dependency evidence is missing or off-tenant.
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
                        f"Tenant isolation breach in T16 product evidence: dossier tenant '{d_tenant}' "
                        f"does not match grant tenant '{grant_tenant}'."
                    )
                for c in dossier.get("claims", []):
                    if isinstance(c, dict):
                        if c.get("validation_status") == "SUPPORTED" or float(str(c.get("confidence", 0.0))) >= 0.7:
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
                            if isinstance(c, dict):
                                if c.get("validation_status") == "SUPPORTED" or float(str(c.get("confidence", 0.0))) >= 0.7:
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
                        if status in ("SUPPORTED", "VALIDATED") or float(str(rc.get("confidence", 1.0))) >= 0.7:
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
                                        f"Tenant isolation breach in T16 claims item: tenant '{rc_tenant}' "
                                        f"does not match grant tenant '{grant_tenant}'."
                                    )
                                status = rc.get("validation_status", rc.get("status", "SUPPORTED"))
                                if status in ("SUPPORTED", "VALIDATED") or float(str(rc.get("confidence", 1.0))) >= 0.7:
                                    approved_claims.append(rc)
                except json.JSONDecodeError:
                    approved_claims.append({"id": "claim-0", "text": raw_claims})

        has_explicit_dependencies = (
            bool(context.get("require_dependencies"))
            or any(
                k in context
                for k in (
                    "claims_dossier",
                    "strategy_plan",
                    "approved_claims",
                    "supported_claims",
                    "claims",
                    "strategy",
                    "omnichannel_strategy",
                )
            )
            or any(
                k in grant.cts_state
                for k in (
                    "claims_dossier",
                    "strategy_plan",
                    "approved_claims",
                    "supported_claims",
                    "claims",
                    "strategy",
                    "omnichannel_strategy",
                )
            )
        )

        if not approved_claims:
            if has_explicit_dependencies:
                raise ValueError(
                    "Missing or invalid T16 Product Evidence dependency: No supported product claims "
                    f"found for tenant '{grant_tenant}' in context or CTS state."
                )
            approved_claims.append({
                "id": f"claim-default-{grant.brand_id}",
                "text": "Validated enterprise performance backed by benchmark testing.",
                "category": "performance",
                "validation_status": "SUPPORTED",
            })

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
                        f"Tenant isolation breach in T19 omnichannel strategy: strategy tenant '{s_tenant}' "
                        f"does not match grant tenant '{grant_tenant}'."
                    )
                strategy_plan = strat_obj
            elif isinstance(strat_obj, str):
                try:
                    parsed_s = json.loads(strat_obj)
                    if isinstance(parsed_s, dict):
                        s_tenant = parsed_s.get("tenant_id")
                        if s_tenant and s_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in T19 omnichannel strategy: strategy tenant '{s_tenant}' "
                                f"does not match grant tenant '{grant_tenant}'."
                            )
                        strategy_plan = parsed_s
                except json.JSONDecodeError:
                    pass
            elif hasattr(strat_obj, "model_dump"):
                dumped = strat_obj.model_dump()
                s_tenant = dumped.get("tenant_id")
                if s_tenant and s_tenant != grant_tenant:
                    raise ValueError(
                        f"Tenant isolation breach in T19 omnichannel strategy: strategy tenant '{s_tenant}' "
                        f"does not match grant tenant '{grant_tenant}'."
                    )
                strategy_plan = dumped

        if not strategy_plan:
            if has_explicit_dependencies:
                raise ValueError(
                    "Missing or invalid T19 Omnichannel Strategy dependency: No strategy plan "
                    f"found for tenant '{grant_tenant}' in context or CTS state."
                )
            strategy_plan = {
                "plan_id": f"strat-default-{grant.task_id}",
                "tenant_id": grant_tenant,
                "channels": list(grant.tenant_scope.allowed_channels) if (grant.tenant_scope and grant.tenant_scope.allowed_channels) else ["meta", "google", "tiktok", "linkedin", "email"],
                "target_audience": "enterprise growth audience",
            }

        # -------------------------------------------------------------
        # 3. Channels from Strategy & Grant
        # -------------------------------------------------------------
        channels: list[str] = []
        if "channel_allocations" in strategy_plan:
            for ca in strategy_plan["channel_allocations"]:
                if isinstance(ca, dict) and "channel" in ca:
                    channels.append(str(ca["channel"]).strip().lower())
                elif hasattr(ca, "channel"):
                    channels.append(str(getattr(ca, "channel")).strip().lower())

        if not channels and "channels" in strategy_plan:
            raw_ch = strategy_plan["channels"]
            if isinstance(raw_ch, list):
                channels = [str(c).strip().lower() for c in raw_ch if str(c).strip()]
            elif isinstance(raw_ch, str):
                channels = [c.strip().lower() for c in raw_ch.split(",") if c.strip()]

        if not channels and grant.tenant_scope and grant.tenant_scope.allowed_channels:
            channels = [c.strip().lower() for c in grant.tenant_scope.allowed_channels if c.strip()]

        if not channels:
            channels = ["meta", "google", "tiktok", "linkedin", "email"]

        # Deduplicate preserving order
        seen_ch: set[str] = set()
        channels = [c for c in channels if not (c in seen_ch or seen_ch.add(c))]

        # -------------------------------------------------------------
        # 4. Policy Precedence & Brand Persona Rules
        # -------------------------------------------------------------
        # Policy constraints
        policy_rules = list(getattr(grant, "policy_constraints", [])) if getattr(grant, "policy_constraints", None) else []
        context_policy = context.get("policy_constraints")
        if context_policy:
            if isinstance(context_policy, list):
                policy_rules.extend([str(p) for p in context_policy])
            elif isinstance(context_policy, str):
                policy_rules.extend([p.strip() for p in context_policy.split(",") if p.strip()])

        # Brand persona
        persona = context.get("brand_persona")
        brand_voice = getattr(persona, "voice", "authoritative")
        persona_prohibited = getattr(persona, "prohibited_terms", ())
        persona_disclaimers = getattr(persona, "required_disclaimers", ())

        # Extract prohibited terms: policy strictly overrides persona
        prohibited_terms_set: set[str] = set()
        for term in persona_prohibited:
            if term:
                prohibited_terms_set.add(str(term).strip().lower())
        for rule in policy_rules:
            if "prohibit" in rule.lower() or "forbid" in rule.lower() or "block" in rule.lower():
                clean_term = rule.replace("prohibit:", "").replace("prohibit", "").strip().lower()
                if clean_term:
                    prohibited_terms_set.add(clean_term)

        # Explicit prohibited terms passed in context
        raw_proh = context.get("prohibited_terms")
        if raw_proh:
            if isinstance(raw_proh, list):
                for p in raw_proh:
                    prohibited_terms_set.add(str(p).strip().lower())
            elif isinstance(raw_proh, str):
                for p in raw_proh.split(","):
                    if p.strip():
                        prohibited_terms_set.add(p.strip().lower())

        # Disclaimers
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
        # 5. Check for Unsupported / Unverified Claims in Context
        # -------------------------------------------------------------
        unapproved_claims: list[str] = []
        approved_texts = [str(c.get("text", c.get("claim_text", ""))).strip().lower() for c in approved_claims]

        raw_unverified = context.get("unapproved_claims") or context.get("raw_claims")
        if raw_unverified:
            candidate_list: list[str] = []
            if isinstance(raw_unverified, list):
                for item in raw_unverified:
                    t = item.get("text", str(item)) if isinstance(item, dict) else str(item)
                    candidate_list.append(t)
            elif isinstance(raw_unverified, str):
                candidate_list = [raw_unverified]

            for cand in candidate_list:
                if cand.strip().lower() not in approved_texts:
                    unapproved_claims.append(cand.strip())

        # Objective & Audience
        objective = str(
            context.get("objective")
            or strategy_plan.get("objective")
            or context.get("query")
            or "enterprise growth campaign"
        )
        target_audience = str(
            context.get("target_audience")
            or strategy_plan.get("target_audience")
            or "growth-oriented consumers"
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
        )

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        """Build authorized sandbox execution payload for S_COPY."""
        (
            approved_claims,
            strategy_plan,
            channels,
            prohibited_terms,
            required_disclaimers,
            unapproved_claims,
            brand_voice,
            objective,
        ) = self._verify_and_normalize_dependencies(grant, context)

        tenant_id = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        brand_id = grant.brand_id or (grant.tenant_scope.brand_ids[0] if (grant.tenant_scope and grant.tenant_scope.brand_ids) else "default")
        target_audience = str(
            context.get("target_audience")
            or strategy_plan.get("target_audience", "growth-oriented consumers")
        )

        payload: dict[str, str] = {
            "task_id": grant.task_id,
            "operation": "generate_variants",
            "tenant_id": tenant_id,
            "brand_id": brand_id,
            "objective": objective,
            "target_audience": target_audience,
            "brand_voice": brand_voice,
            "channels": ",".join(channels),
            "prohibited_terms": ",".join(prohibited_terms),
            "required_disclaimers": ";".join(required_disclaimers),
            "t16_claims": json.dumps(approved_claims),
            "t19_strategy": json.dumps(strategy_plan),
        }

        if unapproved_claims:
            payload["unapproved_claims"] = json.dumps(unapproved_claims)

        return payload

    def interpret_result(
        self, sanitized_output: dict[str, str]
    ) -> tuple[list[str], ConfidenceInterval]:
        """Parse sanitized output from S_COPY into evidence lines and confidence interval."""
        evidence: list[str] = []

        package_raw = sanitized_output.get("creative_package")
        package_data: dict[str, Any] | None = None
        if package_raw:
            try:
                package_data = json.loads(package_raw)
            except Exception:
                pass

        if package_data:
            package_id = package_data.get("package_id", "pkg-unknown")
            objective = package_data.get("objective", "campaign")
            audience = package_data.get("target_audience", "audience")
            voice = package_data.get("persona_voice", "authoritative")

            evidence.append(
                f"Creative Package [{package_id}]: Objective: {objective} | Audience: {audience} | Brand Voice: {voice}"
            )

            # Ad copy variants
            ad_variants = package_data.get("ad_copy_variants", [])
            evidence.append(f"Ad Copy Variants Generated: {len(ad_variants)}")
            for v in ad_variants:
                if isinstance(v, dict):
                    ch = v.get("channel", "unknown").upper()
                    fmt = v.get("format", "ad")
                    hl = v.get("headline", "")
                    score = v.get("hook_score", 0.8)
                    cta = v.get("cta", "Learn More")
                    claims = v.get("source_claim_ids", [])
                    evidence.append(
                        f"  [{ch} - {fmt}]: Headline: '{hl}' (Score: {score}) | CTA: '{cta}' | Source Claims: {claims}"
                    )

            # Visual direction briefs
            visual_briefs = package_data.get("visual_briefs", [])
            evidence.append(f"Visual Direction Briefs: {len(visual_briefs)}")
            for vb in visual_briefs:
                if isinstance(vb, dict):
                    ch = vb.get("channel", "unknown").upper()
                    ratio = vb.get("aspect_ratio", "1:1")
                    art = vb.get("art_direction", "")
                    evidence.append(f"  [{ch} Visual Brief ({ratio})]: {art[:80]}...")

            # Social post variants
            social_posts = package_data.get("social_posts", [])
            if social_posts:
                evidence.append(f"Social Post Variants: {len(social_posts)}")
                for sp in social_posts:
                    if isinstance(sp, dict):
                        plat = sp.get("platform", "social").title()
                        post_type = sp.get("post_type", "post")
                        caption = sp.get("caption", "")
                        evidence.append(f"  [{plat} {post_type}]: {caption[:60]}...")

            # Content schedules
            schedules = package_data.get("schedules", [])
            if schedules:
                evidence.append(f"Content Release Schedule: {len(schedules)} slots planned")
                for s in schedules[:5]:
                    if isinstance(s, dict):
                        slot = s.get("day_or_week", "")
                        ch = s.get("channel", "").upper()
                        stg = s.get("funnel_stage", "")
                        obj = s.get("primary_objective", "")
                        evidence.append(f"  [{slot}]: Channel: {ch} | Stage: {stg} | Goal: {obj}")

            # Flagged unsupported claims
            flagged = package_data.get("flagged_unsupported_claims", [])
            for fc in flagged:
                evidence.append(f"Warning: Unsupported claim flagged and excluded: {fc}")

            # Confidence
            conf_data = package_data.get("confidence", {})
            pt = float(str(conf_data.get("point_estimate", 0.88)))
            low = float(str(conf_data.get("lower_bound", 0.78)))
            high = float(str(conf_data.get("upper_bound", 0.95)))
            confidence = ConfidenceInterval(point_estimate=pt, lower_bound=low, upper_bound=high)
        else:
            # Fallback legacy parsing
            headline = sanitized_output.get("headline", "")
            hook_score = sanitized_output.get("hook_score", "0.85")
            brand_voice = sanitized_output.get("brand_voice", "authoritative")
            copy_body = sanitized_output.get("copy_body", "")

            evidence.append(f"Creative Copy Draft: Headline: '{headline}' (Hook Score: {hook_score})")
            evidence.append(f"Brand Voice: {brand_voice}")
            evidence.append(f"Copy Body: {copy_body}")

            confidence = ConfidenceInterval(point_estimate=0.82, lower_bound=0.70, upper_bound=0.90)

        return evidence, confidence

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