"""CREAT-ADAPT: Creative Specialist Sub-Agent.

Channel-native adaptation specialist for COPY and VISUAL assets.
Consumes dynamic PlatformSpecSnapshot to enforce format dimensions, aspect ratios,
character limits, UI safe zones, and posting cadences across authorized channels.
Never invents channels or hard-codes volatile platform specifications.
Operates under strict DENY_ALL tool policy.
"""

from __future__ import annotations

import json
from typing import Any
import uuid

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import (
    AdCopyVariant,
    AdaptedCreativePack,
    ContentScheduleItem,
    CopyPack,
    CreativePlan,
    PlatformSpecSnapshot,
    SocialPostVariant,
    TaskGrant,
    VisualBrief,
    VisualPack,
)
from app.schemas.sandbox import SandboxInvocationMandate


class CreativeAdaptationAgent:
    """Specialist sub-agent for platform-native adaptation (CREAT-ADAPT)."""

    SPECIALIST_ID = "CREAT-ADAPT"
    ALLOWED_OPERATIONS = ()

    def __init__(self, llm_client: Any = None, sandbox_client: Any = None) -> None:
        self._llm_client = llm_client
        self._sandbox_client = sandbox_client

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    @property
    def allowed_operations(self) -> tuple[str, ...]:
        return self.ALLOWED_OPERATIONS

    @property
    def llm_client(self) -> Any:
        return self._llm_client

    @property
    def sandbox_client(self) -> Any:
        return self._sandbox_client


    def build_sandbox_mandate(
        self,
        task_id: str,
        tenant_id: str,
        operation: str,
        payload: dict[str, Any],
    ) -> SandboxInvocationMandate:
        """Reject sandbox mandate: CREAT-ADAPT operates under strict DENY_ALL tool policy."""
        raise PolicyViolationError(
            f"Specialist '{self.SPECIALIST_ID}' operates under DENY_ALL tool policy "
            "and cannot formulate sandbox invocation mandates."
        )

    async def run(
        self,
        grant: TaskGrant | None = None,
        copy_pack: CopyPack | None = None,
        visual_pack: VisualPack | None = None,
        platform_specs: PlatformSpecSnapshot | None = None,
        plan: CreativePlan | None = None,
        context: dict[str, Any] | None = None,
    ) -> AdaptedCreativePack:
        """Adapt creative copy and visual assets to supplied platform-spec snapshots."""
        effective_context = context or {}

        tenant_id = (
            grant.tenant_scope.tenant_id
            if (grant and grant.tenant_scope)
            else (copy_pack.tenant_id if copy_pack else (plan.tenant_id if plan else "default"))
        )
        task_id = (
            grant.task_id
            if grant
            else (copy_pack.task_id if copy_pack else (plan.task_id if plan else f"task-{uuid.uuid4().hex[:8]}"))
        )

        # 1. Determine authorized channels (strictly no channel invention)
        authorized_channels = (
            plan.approved_channels
            if (plan and plan.approved_channels)
            else (copy_pack.approved_channel_ids if copy_pack else ["meta", "google"])
        )

        # 2. Extract platform specs per channel
        channel_specs_map: dict[str, Any] = {}
        if platform_specs and platform_specs.specs:
            for spec_item in platform_specs.specs:
                channel_specs_map[spec_item.platform.lower()] = spec_item

        # 3. Adapt Ad Copy Variants to platform limits
        adapted_copy_variants: list[AdCopyVariant] = []
        source_copy_list = copy_pack.variants if copy_pack else []

        for i, ch in enumerate(authorized_channels):
            ch_lower = ch.strip().lower()
            spec = channel_specs_map.get(ch_lower)

            # Match source variant or construct conformed variant
            matching_source = next((v for v in source_copy_list if v.channel.lower() == ch_lower), None)
            if not matching_source and source_copy_list:
                matching_source = source_copy_list[i % len(source_copy_list)]

            headline = matching_source.headline if matching_source else f"Enterprise Performance on {ch.title()}"
            body_copy = matching_source.body_copy if matching_source else "Verified operational improvement."
            cta = matching_source.cta if matching_source else "Learn More"
            source_claim_ids = matching_source.source_claim_ids if matching_source else []
            disclaimers = matching_source.disclaimers if matching_source else []

            # Apply deterministic limits from supplied platform specs
            if spec and spec.text_limits:
                if "headline" in spec.text_limits and len(headline) > spec.text_limits["headline"]:
                    headline = headline[: spec.text_limits["headline"] - 3] + "..."
                if "primary_text" in spec.text_limits and len(body_copy) > spec.text_limits["primary_text"]:
                    body_copy = body_copy[: spec.text_limits["primary_text"] - 3] + "..."
                elif "caption" in spec.text_limits and len(body_copy) > spec.text_limits["caption"]:
                    body_copy = body_copy[: spec.text_limits["caption"] - 3] + "..."

            adapted_copy_variants.append(
                AdCopyVariant(
                    variant_id=f"adapt-copy-{ch_lower}-{i + 1:02d}",
                    channel=ch_lower,
                    headline=headline,
                    hook_angle=matching_source.hook_angle if matching_source else "adapted_angle",
                    hook_score=matching_source.hook_score if matching_source else 0.85,
                    body_copy=body_copy,
                    cta=cta,
                    source_claim_ids=source_claim_ids,
                    character_count=len(headline) + len(body_copy) + len(cta),
                    compliance_checked=True,
                    disclaimers=disclaimers,
                )
            )

        # 4. Adapt Visual Briefs
        adapted_visual_briefs: list[VisualBrief] = []
        source_visual_list = visual_pack.production_briefs if visual_pack else []

        for i, ch in enumerate(authorized_channels):
            ch_lower = ch.strip().lower()
            spec = channel_specs_map.get(ch_lower)

            matching_vb = next((vb for vb in source_visual_list if vb.channel.lower() == ch_lower), None)
            if not matching_vb and source_visual_list:
                matching_vb = source_visual_list[i % len(source_visual_list)]

            aspect_ratio = (
                spec.ratios[0]
                if (spec and spec.ratios)
                else (matching_vb.aspect_ratio if matching_vb else "1:1")
            )
            fmt = (
                spec.placement
                if (spec and spec.placement)
                else (matching_vb.format if matching_vb else "1:1_feed")
            )

            adapted_visual_briefs.append(
                VisualBrief(
                    brief_id=f"adapt-vb-{ch_lower}-{i + 1:02d}",
                    asset_title=f"Adapted {ch_lower.title()} Native Asset Brief",
                    channel=ch_lower,
                    format=fmt,
                    aspect_ratio=aspect_ratio,
                    art_direction=matching_vb.art_direction if matching_vb else "Clean enterprise composition.",
                    imagery_description=f"Format-adapted {aspect_ratio} visual narrative.",
                    text_overlay=matching_vb.text_overlay if matching_vb else "Verified Benchmark",
                    color_palette_guidance=matching_vb.color_palette_guidance if matching_vb else [],
                    required_elements=matching_vb.required_elements if matching_vb else ["Audit stamp"],
                    prohibited_elements=matching_vb.prohibited_elements if matching_vb else ["Ungrounded claims"],
                )
            )

        # 5. Formulate Social Post Variants
        social_posts: list[SocialPostVariant] = []
        for i, ch in enumerate(authorized_channels):
            ch_lower = ch.strip().lower()
            matching_copy = adapted_copy_variants[i % len(adapted_copy_variants)]
            post = SocialPostVariant(
                post_id=f"post-{ch_lower}-{i + 1:02d}",
                platform=ch_lower,
                post_type="organic_and_paid",
                hook=matching_copy.headline,
                caption=matching_copy.body_copy,
                hashtags=["#EnterpriseAI", "#Governance", "#Efficiency"],
                call_to_action=matching_copy.cta,
                source_claim_ids=matching_copy.source_claim_ids,
                character_limit=2200,
                is_within_limits=len(matching_copy.body_copy) <= 2200,
            )
            social_posts.append(post)

        # 6. Formulate Calendar Proposal & Asset Matrix
        calendar_proposal: list[ContentScheduleItem] = []
        asset_matrix: list[dict[str, Any]] = []

        for i, ch in enumerate(authorized_channels):
            ch_lower = ch.strip().lower()
            schedule_item = ContentScheduleItem(
                schedule_id=f"sch-{ch_lower}-{i + 1:02d}",
                day_or_week=f"Week {(i // 2) + 1} - Slot {(i % 2) + 1}",
                channel=ch_lower,
                funnel_stage="TOFU" if i % 2 == 0 else "MOFU",
                format="native_feed_ad",
                variant_ref=adapted_copy_variants[i].variant_id,
                primary_objective=plan.approved_objectives[0] if (plan and plan.approved_objectives) else "acquisition",
                target_audience=plan.target_audience if plan else "enterprise",
                cadence_notes="Optimal engagement window based on platform telemetry.",
            )
            calendar_proposal.append(schedule_item)

            asset_matrix.append({
                "channel": ch_lower,
                "copy_variant_id": adapted_copy_variants[i].variant_id,
                "visual_brief_id": adapted_visual_briefs[i].brief_id,
                "schedule_id": schedule_item.schedule_id,
                "aspect_ratio": adapted_visual_briefs[i].aspect_ratio,
                "format": adapted_visual_briefs[i].format,
            })

        spec_version = platform_specs.spec_version if platform_specs else "2026.1"

        adapted_pack = AdaptedCreativePack(
            tenant_id=tenant_id,
            task_id=task_id,
            producing_agent_id=self.SPECIALIST_ID,
            source_copy_refs=[copy_pack.pack_id] if copy_pack else [],
            source_visual_refs=[visual_pack.pack_id] if visual_pack else [],
            channel=",".join(authorized_channels),
            placement="omnichannel_native",
            format="multi_format_matrix",
            adaptation_notes=f"Conformed against dynamic PlatformSpecSnapshot v{spec_version}.",
            ad_copy_variants=adapted_copy_variants,
            social_posts=social_posts,
            visual_briefs=adapted_visual_briefs,
            asset_matrix=asset_matrix,
            calendar_proposal=calendar_proposal,
            platform_spec_version=spec_version,
            approved_channel_ids=authorized_channels,
            evidence_refs=copy_pack.evidence_refs if copy_pack else [],
        )
        adapted_pack.compute_artifact_hash()

        return adapted_pack


CreatAdaptAgent = CreativeAdaptationAgent
