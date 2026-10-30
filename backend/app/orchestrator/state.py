import operator
from datetime import datetime
from typing import Annotated, Literal, TypedDict
from pydantic import BaseModel, Field

PlatformType = Literal[
    "linkedin", "youtube", "instagram", "threads",
    "facebook", "x", "pinterest", "google_business_profile"
]

class PlatformAssetSpec(BaseModel):
    platform: PlatformType
    copy_text: str
    media_urls: list[str] = Field(default_factory=list)
    aspect_ratio: Literal["1:1", "4:5", "9:16", "16:9", "2:3"]
    scheduled_utc: datetime
    idempotency_key: str = Field(description="SHA-256 of campaign_id + platform + scheduled_utc")
    compliance_passed: bool = False

class CampaignBlueprint(BaseModel):
    campaign_id: str
    objective: str
    target_audience_segments: list[str] = Field(default_factory=list)
    positioning_statement: str
    platform_assets: list[PlatformAssetSpec] = Field(default_factory=list)

def merge_platform_results(existing: list[dict], new_items: list[dict]) -> list[dict]:
    by_key = {item["idempotency_key"]: item for item in existing}
    for item in new_items:
        by_key[item["idempotency_key"]] = item
    return list(by_key.values())

class MarketingOSState(TypedDict):
    thread_id: str
    campaign_id: str
    user_command: str
    task_description: str
    active_skills: list[str]
    research_dossier: dict
    campaign_blueprint: dict
    platform_publish_results: Annotated[list[dict], merge_platform_results]
    critique_history: Annotated[list[str], operator.add]
    revision_count: int
    approval_status: Literal["pending", "approved", "rejected"]
    analytics_anomalies: list[dict]
