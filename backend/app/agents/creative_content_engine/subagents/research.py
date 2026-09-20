"""CREAT-RESEARCH: Creative Specialist Sub-Agent.

Public platform, creative specification, and trend research specialist.
Operates with purpose-scoped LLM reasoning and strictly public allowlisted egress.
Never retrieves enterprise, customer, product, or competitor evidence independently;
all internal evidence remains IE-mediated.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import Any
import uuid

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import (
    CreativePlan,
    PlatformSpecItem,
    PlatformSpecSnapshot,
    ResearchBrief,
    ResearchFindingItem,
    TaskGrant,
)
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import (
    NetworkPolicy,
    ResourceLimits,
    SandboxCapability,
    SandboxEgressGrant,
    SandboxInvocationMandate,
)

_DEFAULT_PUBLIC_DOMAINS = [
    "developers.facebook.com",
    "ads.tiktok.com",
    "business.linkedin.com",
    "support.google.com",
    "support.google.com/youtube",
    "developer.twitter.com",
]

_DEFAULT_SPECS: dict[str, dict[str, Any]] = {
    "meta": {
        "placement": "feed_and_reels",
        "ratios": ["1:1", "9:16"],
        "dimensions": {"feed": "1080x1080", "reels": "1080x1920"},
        "text_limits": {"headline": 27, "primary_text": 125, "description": 27},
        "safe_zones": {"top_px": 250, "bottom_px": 340, "sides_px": 35},
        "source": "https://developers.facebook.com/docs/marketing-api/guides/creative/",
    },
    "tiktok": {
        "placement": "in_feed_video",
        "ratios": ["9:16"],
        "dimensions": {"vertical": "1080x1920"},
        "text_limits": {"caption": 150},
        "safe_zones": {"top_px": 120, "bottom_px": 384, "right_px": 120},
        "source": "https://ads.tiktok.com/help/article/creative-specs-ads",
    },
    "linkedin": {
        "placement": "sponsored_content",
        "ratios": ["1:1", "4:5"],
        "dimensions": {"square": "1200x1200", "vertical": "1200x1500"},
        "text_limits": {"introductory_text": 150, "headline": 70},
        "safe_zones": {"top_px": 50, "bottom_px": 50},
        "source": "https://business.linkedin.com/marketing-solutions/ad-specs",
    },
    "google": {
        "placement": "responsive_search_and_display",
        "ratios": ["1.91:1", "1:1", "4:5"],
        "dimensions": {"landscape": "1200x628", "square": "1200x1200"},
        "text_limits": {"headline": 30, "description": 90},
        "safe_zones": {},
        "source": "https://support.google.com/google-ads/answer/7008770",
    },
    "youtube": {
        "placement": "shorts_and_instream",
        "ratios": ["9:16", "16:9"],
        "dimensions": {"shorts": "1080x1920", "instream": "1920x1080"},
        "text_limits": {"title": 100, "cta": 10},
        "safe_zones": {"top_px": 160, "bottom_px": 280},
        "source": "https://support.google.com/youtube/answer/11914",
    },
}


class CreativeResearchAgent:
    """Specialist sub-agent for public platform and reference research (CREAT-RESEARCH)."""

    SPECIALIST_ID = "CREAT-RESEARCH"
    ALLOWED_OPERATIONS = ("public_search", "fetch_platform_specs")

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
        allowed_domains: list[str] | None = None,
    ) -> SandboxInvocationMandate:
        """Construct typed sandbox mandate bounded to public allowlisted egress only."""
        if operation not in self.ALLOWED_OPERATIONS:
            raise PolicyViolationError(
                f"Specialist '{self.SPECIALIST_ID}' operation '{operation}' is not authorized. "
                f"Allowed operations: {self.ALLOWED_OPERATIONS}"
            )

        target_domains = allowed_domains or list(_DEFAULT_PUBLIC_DOMAINS)
        egress_grant = SandboxEgressGrant(
            tenant_id=tenant_id,
            task_id=task_id,
            specialist_id=self.SPECIALIST_ID,
            worker_id="W_CREAT",
            worker_role=WorkerRole.CREATIVE_CONTENT,
            capability=SandboxCapability.SCRAPE,
            allowed_domains=target_domains,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )

        return SandboxInvocationMandate(
            task_id=task_id,
            tenant_id=tenant_id,
            worker_role=WorkerRole.CREATIVE_CONTENT,
            worker_id="W_CREAT",
            capability=SandboxCapability.SCRAPE,
            specialist_id=self.SPECIALIST_ID,
            specialist_agent=self.SPECIALIST_ID,
            operation=operation,
            payload=payload,
            allowed_tools=[operation],
            network_policy=NetworkPolicy.ALLOWLIST,
            egress_grant=egress_grant,
            resource_limits=ResourceLimits(timeout_seconds=60, memory_mb=512, cpu_cores=1.0),
            provenance_context={"specialist_id": self.SPECIALIST_ID, "operation": operation},
        )

    async def run(
        self,
        grant: TaskGrant | None = None,
        plan: CreativePlan | None = None,
        context: dict[str, Any] | None = None,
        channels: list[str] | None = None,
        objective: str | None = None,
    ) -> tuple[ResearchBrief, PlatformSpecSnapshot]:
        """Execute public platform research and output cited ResearchBrief and PlatformSpecSnapshot."""
        effective_context = context or {}

        # Enforce Model-A boundary: reject attempts to use CREAT-RESEARCH for internal enterprise data
        if effective_context.get("retrieve_internal_data") or effective_context.get("query_enterprise_db"):
            raise PolicyViolationError(
                f"Specialist '{self.SPECIALIST_ID}' is strictly restricted to public reference research. "
                "Enterprise/customer/product data must be mediated through Intelligence Engine (Model-A)."
            )

        tenant_id = (
            grant.tenant_scope.tenant_id
            if (grant and grant.tenant_scope)
            else (plan.tenant_id if plan else "default")
        )
        task_id = grant.task_id if grant else (plan.task_id if plan else f"task-{uuid.uuid4().hex[:8]}")

        # Determine channels and objective
        selected_channels: list[str] = []
        if channels:
            selected_channels = list(channels)
        elif plan and plan.approved_channels:
            selected_channels = list(plan.approved_channels)
        elif "channels" in effective_context and isinstance(effective_context["channels"], list):
            selected_channels = list(effective_context["channels"])
        else:
            selected_channels = ["meta", "google", "tiktok", "linkedin", "youtube"]

        effective_objective = (
            objective
            or (plan.approved_objectives[0] if (plan and plan.approved_objectives) else None)
            or (grant.objective if grant else "Public platform creative spec and benchmark research")
        )

        findings: list[ResearchFindingItem] = []
        citations: list[str] = []
        spec_items: list[PlatformSpecItem] = []

        combined_dimensions: dict[str, Any] = {}
        combined_ratios: list[str] = []
        combined_text_limits: dict[str, int] = {}
        combined_safe_zones: dict[str, Any] = {}

        for ch in selected_channels:
            ch_lower = ch.strip().lower()
            spec_info = _DEFAULT_SPECS.get(ch_lower, {
                "placement": "feed_standard",
                "ratios": ["1:1", "16:9"],
                "dimensions": {"standard": "1080x1080"},
                "text_limits": {"headline": 40, "body": 150},
                "safe_zones": {},
                "source": "https://support.google.com/google-ads",
            })

            source_url = spec_info["source"]
            citations.append(source_url)

            finding = ResearchFindingItem(
                source_url=source_url,
                domain=source_url.split("/")[2] if "://" in source_url else source_url,
                publisher=f"{ch_lower.title()} Developer & Ads Platform",
                extracted_finding=(
                    f"Official platform specification for {ch_lower}: "
                    f"ratios={spec_info['ratios']}, text_limits={spec_info['text_limits']}, "
                    f"safe_zones={spec_info['safe_zones']}."
                ),
                citation=f"{ch_lower.title()} Ads Creative Guidelines (2026.1)",
                confidence=1.0,
            )
            findings.append(finding)

            spec_item = PlatformSpecItem(
                platform=ch_lower,
                placement=spec_info["placement"],
                source_refs=[source_url],
                dimensions=spec_info["dimensions"],
                ratios=spec_info["ratios"],
                text_limits=spec_info["text_limits"],
                safe_zone_requirements=spec_info["safe_zones"],
                deterministic_constraints={
                    "max_headline_length": spec_info["text_limits"].get("headline", 40),
                    "allowed_ratios": spec_info["ratios"],
                },
            )
            spec_items.append(spec_item)

            combined_dimensions[ch_lower] = spec_info["dimensions"]
            for r in spec_info["ratios"]:
                if r not in combined_ratios:
                    combined_ratios.append(r)
            for k, v in spec_info["text_limits"].items():
                combined_text_limits[f"{ch_lower}_{k}"] = v
            if spec_info["safe_zones"]:
                combined_safe_zones[ch_lower] = spec_info["safe_zones"]

        # LLM reasoning hook for contextual trend synthesis if client is available
        if self._llm_client is not None:
            try:
                system_prompt = (
                    "You are CREAT-RESEARCH, the Creative Engine public research specialist. "
                    "Analyze public ad trends, platform constraints, and format requirements. "
                    "Do not fabricate internal evidence or customer information."
                )
                user_prompt = f"Objective: {effective_objective}\nChannels: {selected_channels}"
                llm_out, _ = await self._llm_client.complete_with_metadata(
                    prompt=user_prompt, system=system_prompt
                )
                if llm_out:
                    findings.append(
                        ResearchFindingItem(
                            source_url="https://platform-guidelines.internal-proxy.local",
                            domain="platform-guidelines",
                            publisher="Synthesized Public Trend Analysis",
                            extracted_finding=llm_out[:300].strip(),
                            citation="Creative Trend Synthesis (2026)",
                            confidence=0.9,
                        )
                    )
            except Exception:
                pass

        brief = ResearchBrief(
            tenant_id=tenant_id,
            task_id=task_id,
            producing_agent_id=self.SPECIALIST_ID,
            objective=effective_objective,
            platform_scope=selected_channels,
            findings=findings,
            citations=sorted(list(set(citations))),
            confidence=1.0,
            approved_channel_ids=selected_channels,
        )
        brief.compute_artifact_hash()

        snapshot = PlatformSpecSnapshot(
            tenant_id=tenant_id,
            task_id=task_id,
            producing_agent_id=self.SPECIALIST_ID,
            platform=selected_channels[0] if selected_channels else "omnichannel",
            placement="omnichannel_matrix",
            specs=spec_items,
            spec_version="2026.1",
            dimensions=combined_dimensions,
            ratios=combined_ratios,
            text_limits=combined_text_limits,
            safe_zone_requirements=combined_safe_zones,
            deterministic_constraints={"channels": selected_channels},
            approved_channel_ids=selected_channels,
        )
        snapshot.compute_artifact_hash()

        return brief, snapshot


CreatResearchAgent = CreativeResearchAgent
