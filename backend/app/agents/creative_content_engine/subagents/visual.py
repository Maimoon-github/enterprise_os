"""CREAT-VISUAL: Creative Specialist Sub-Agent.

Art direction, storyboard, shot list, and production brief specialist.
Generates structured visual direction and generative asset briefs bounded to
approved channels. Does NOT execute un-governed image or video generation models directly.
Operates under strict DENY_ALL tool policy.
"""

from __future__ import annotations

import json
from typing import Any
import uuid

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import (
    ConceptPack,
    CreativePlan,
    PlatformSpecSnapshot,
    TaskGrant,
    VisualBrief,
    VisualPack,
)
from app.schemas.sandbox import SandboxInvocationMandate


class CreativeVisualAgent:
    """Specialist sub-agent for visual concepting, storyboarding, and briefs (CREAT-VISUAL)."""

    SPECIALIST_ID = "CREAT-VISUAL"
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
        """Reject sandbox mandate: CREAT-VISUAL operates under strict DENY_ALL tool policy."""
        raise PolicyViolationError(
            f"Specialist '{self.SPECIALIST_ID}' operates under DENY_ALL tool policy "
            "and cannot formulate sandbox invocation mandates."
        )

    async def run(
        self,
        grant: TaskGrant | None = None,
        concept_pack: ConceptPack | None = None,
        plan: CreativePlan | None = None,
        platform_specs: PlatformSpecSnapshot | None = None,
        context: dict[str, Any] | None = None,
    ) -> VisualPack:
        """Produce art direction, storyboards, shot lists, and channel visual briefs."""
        effective_context = context or {}

        tenant_id = (
            grant.tenant_scope.tenant_id
            if (grant and grant.tenant_scope)
            else (concept_pack.tenant_id if concept_pack else (plan.tenant_id if plan else "default"))
        )
        task_id = (
            grant.task_id
            if grant
            else (concept_pack.task_id if concept_pack else (plan.task_id if plan else f"task-{uuid.uuid4().hex[:8]}"))
        )

        channels = (
            concept_pack.approved_channel_ids
            if (concept_pack and concept_pack.approved_channel_ids)
            else (plan.approved_channels if plan else ["meta", "google", "tiktok", "linkedin", "youtube"])
        )
        concept_ref = concept_pack.concepts[0].concept_id if (concept_pack and concept_pack.concepts) else "cpt-1"
        evidence_refs = concept_pack.evidence_refs if concept_pack else (plan.evidence_manifest if plan else [])

        # Art Direction & Composition Architecture
        visual_territory = "High-clarity enterprise minimalism with dynamic data telemetry overlays"
        composition = (
            "Asymmetric grid composition with 60% negative space, 30% telemetry visualization, "
            "and 10% high-contrast brand focus anchor complying with UI safe zones."
        )

        storyboard = [
            {
                "scene": 1,
                "timing": "0.0s - 2.0s",
                "visual": "Close-up of operational dashboard displaying high friction metrics in muted red tone.",
                "text_overlay": "Operational Friction Slowing Growth?",
                "audio_cue": "Subtle low hum transitioning to rising chime.",
            },
            {
                "scene": 2,
                "timing": "2.0s - 5.0s",
                "visual": "Smooth zoom out revealing governed automation pipeline orchestrating data cleanly.",
                "text_overlay": "Verified Enterprise Performance.",
                "audio_cue": "Clean, crisp synthesized sweep.",
            },
            {
                "scene": 3,
                "timing": "5.0s - 8.0s",
                "visual": "Dynamic telemetry counters illustrating +42% efficiency jump with audit stamp.",
                "text_overlay": "42% Verified Efficiency Benchmark.",
                "audio_cue": "Data confirmation pulse.",
            },
            {
                "scene": 4,
                "timing": "8.0s - 10.0s",
                "visual": "Clean brand lockup, authoritative typography, and prominent CTA button.",
                "text_overlay": "Explore Verified Benchmarks.",
                "audio_cue": "Decisive melodic resolution.",
            },
        ]

        shot_list = [
            "Shot 1: Macro angle on dashboard telemetry and latency metrics (low key lighting).",
            "Shot 2: Wide isometric render of governed multi-stage enterprise architecture.",
            "Shot 3: Dynamic motion graphics showing audited data flow with zero loss.",
            "Shot 4: High-contrast hero typography card with compliance certification badge.",
        ]

        # Formulate Visual Briefs for each approved channel
        production_briefs: list[VisualBrief] = []
        for i, ch in enumerate(channels):
            ch_lower = ch.strip().lower()
            if ch_lower in ("tiktok", "reels", "shorts"):
                aspect_ratio = "9:16"
                fmt = "9:16_vertical_video"
            elif ch_lower == "linkedin":
                aspect_ratio = "4:5"
                fmt = "4:5_vertical_image"
            elif ch_lower == "youtube":
                aspect_ratio = "16:9"
                fmt = "16:9_landscape_video"
            else:
                aspect_ratio = "1:1"
                fmt = "1:1_feed"

            brief = VisualBrief(
                brief_id=f"vb-{ch_lower}-{i + 1:02d}",
                asset_title=f"{ch_lower.title()} Native Direction Brief",
                channel=ch_lower,
                format=fmt,
                aspect_ratio=aspect_ratio,
                art_direction=visual_territory,
                imagery_description=(
                    f"Platform-optimized {aspect_ratio} visual narrative demonstrating empirical benchmark proof. "
                    "Clean gradient background with authoritative enterprise color tokens."
                ),
                text_overlay="Verified Performance Benchmark",
                color_palette_guidance=["#0F172A (Deep Navy)", "#0284C7 (Electric Sky)", "#F8FAFC (Clean White)"],
                required_elements=["Audit badge", "Telemetry metric chart", "Official CTA button"],
                prohibited_elements=["Low-resolution stock graphics", "Exaggerated ungrounded claims", "Cluttered overlays"],
            )
            production_briefs.append(brief)

        # LLM reasoning hook if available
        if self._llm_client is not None:
            try:
                system_prompt = (
                    "You are CREAT-VISUAL, the Creative Engine specialist for art direction, "
                    "storyboarding, shot lists, and production briefs. "
                    "Provide authoritative, non-commodity visual direction without generating raw assets."
                )
                user_prompt = f"Concept: {concept_ref}\nChannels: {json.dumps(channels)}"
                llm_out, _ = await self._llm_client.complete_with_metadata(
                    prompt=user_prompt, system=system_prompt
                )
                if llm_out:
                    visual_territory = f"{visual_territory} — {llm_out[:120].strip()}"
            except Exception:
                pass

        visual_pack = VisualPack(
            tenant_id=tenant_id,
            task_id=task_id,
            producing_agent_id=self.SPECIALIST_ID,
            visual_variant_id=f"vis-{uuid.uuid4().hex[:8]}",
            concept_ref=concept_ref,
            visual_territory=visual_territory,
            composition=composition,
            storyboard=storyboard,
            shot_list=shot_list,
            production_briefs=production_briefs,
            product_brand_refs=effective_context.get("brand_refs", ["brand-standard-01"]),
            approved_channel_ids=channels,
            evidence_refs=evidence_refs,
        )
        visual_pack.compute_artifact_hash()

        return visual_pack


CreatVisualAgent = CreativeVisualAgent
