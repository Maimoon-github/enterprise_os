import operator
from datetime import datetime
from typing import Annotated, Any, Literal, TypedDict

from app.core.idempotency import generate_schedule_idempotency_key
from pydantic import BaseModel, Field, model_validator

PlatformType = Literal[
    "linkedin",
    "youtube",
    "instagram",
    "threads",
    "facebook",
    "x",
    "pinterest",
    "google_business_profile",
]

AspectRatioType = Literal["1:1", "4:5", "9:16", "16:9", "2:3"]


class PlatformAssetSpec(BaseModel):
    platform: PlatformType
    copy_text: str
    media_urls: list[str] = Field(default_factory=list)
    aspect_ratio: AspectRatioType = "1:1"
    scheduled_utc: datetime
    idempotency_key: str = Field(
        default="",
        description="SHA-256 of campaign_id + platform + scheduled_utc",
    )
    compliance_passed: bool = False

    def compute_idempotency_key(self, campaign_id: str) -> str:
        """Derive deterministic SHA-256 key if not explicitly set."""
        if not self.idempotency_key:
            self.idempotency_key = generate_schedule_idempotency_key(
                campaign_id=campaign_id,
                platform=self.platform,
                scheduled_utc=self.scheduled_utc,
            )
        return self.idempotency_key


class CampaignBlueprint(BaseModel):
    campaign_id: str
    objective: str
    target_audience_segments: list[str] = Field(default_factory=list)
    positioning_statement: str
    platform_assets: list[PlatformAssetSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_asset_idempotency_keys(self) -> "CampaignBlueprint":
        """Ensure all nested platform assets carry a deterministic SHA-256 idempotency key."""
        for asset in self.platform_assets:
            if not asset.idempotency_key:
                asset.compute_idempotency_key(self.campaign_id)
        return self


def merge_platform_results(
    existing: list[dict[str, Any]] | None,
    new_items: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Deterministic reducer deduplicating parallel Send() outputs by idempotency_key."""
    by_key: dict[str, dict[str, Any]] = {}
    for item in existing or []:
        key = item.get("idempotency_key")
        if key:
            by_key[key] = item
    for item in new_items or []:
        key = item.get("idempotency_key")
        if key:
            by_key[key] = item
    return list(by_key.values())


class MarketingOSState(TypedDict, total=False):
    thread_id: str
    campaign_id: str
    user_command: str
    task_description: str
    active_skills: list[str]
    research_dossier: dict[str, Any]
    campaign_blueprint: dict[str, Any]
    platform_publish_results: Annotated[list[dict[str, Any]], merge_platform_results]
    critique_history: Annotated[list[str], operator.add]
    revision_count: int
    approval_status: Literal["pending", "approved", "rejected"]
    human_approved: bool
    analytics_anomalies: list[dict[str, Any]]
    optimization_proposal: dict[str, Any]
    require_strategy_approval: bool
    strategy_approved: bool
    require_optimization_approval: bool
    optimization_approved: bool
    # Subgraph intermediate state channels
    react_iterations: int
    research_observations: list[str]
    current_thought: str
    campaign_plan: dict[str, Any]
    draft_assets: list[dict[str, Any]]
    compliance_passed: bool
    critique_feedback: list[str]
    rewoo_plan: list[dict[str, Any]]
    rewoo_raw_metrics: dict[str, Any]
