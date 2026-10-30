from datetime import UTC, datetime

from app.core.idempotency import generate_schedule_idempotency_key
from app.orchestrator.state import (
    CampaignBlueprint,
    MarketingOSState,
    PlatformAssetSpec,
    merge_platform_results,
)


def test_merge_platform_results_deduplication():
    """Verify deterministic deduplication of parallel Send() outputs by idempotency_key."""
    existing = [
        {"idempotency_key": "key_linkedin_01", "platform": "linkedin", "status": "pending"},
        {"idempotency_key": "key_x_01", "platform": "x", "status": "pending"},
    ]
    new_items = [
        {"idempotency_key": "key_linkedin_01", "platform": "linkedin", "status": "published"},
        {"idempotency_key": "key_instagram_01", "platform": "instagram", "status": "published"},
    ]
    merged = merge_platform_results(existing, new_items)
    assert len(merged) == 3
    by_key = {item["idempotency_key"]: item for item in merged}
    assert by_key["key_linkedin_01"]["status"] == "published"
    assert by_key["key_x_01"]["status"] == "pending"
    assert by_key["key_instagram_01"]["status"] == "published"


def test_platform_asset_spec_and_blueprint_idempotency():
    """Verify Pydantic v2 blueprint & asset specs compute deterministic SHA-256 keys."""
    now = datetime(2026, 10, 31, 12, 0, 0, tzinfo=UTC)
    campaign_id = "camp_alpha_42"

    expected_key = generate_schedule_idempotency_key(campaign_id, "linkedin", now)

    asset = PlatformAssetSpec(
        platform="linkedin",
        copy_text="Enterprise Marketing OS Launch",
        aspect_ratio="1:1",
        scheduled_utc=now,
    )
    assert asset.idempotency_key == ""
    key = asset.compute_idempotency_key(campaign_id)
    assert key == expected_key
    assert asset.idempotency_key == expected_key

    # Test auto-population in CampaignBlueprint model validator
    blueprint = CampaignBlueprint(
        campaign_id=campaign_id,
        objective="Drive enterprise trial signups",
        positioning_statement="Zero hallucination deterministic agentic system",
        platform_assets=[
            PlatformAssetSpec(
                platform="x",
                copy_text="Short-form x post",
                aspect_ratio="16:9",
                scheduled_utc=now,
            )
        ],
    )
    x_key = generate_schedule_idempotency_key(campaign_id, "x", now)
    assert blueprint.platform_assets[0].idempotency_key == x_key


def test_marketing_os_state_structure():
    """Verify MarketingOSState TypedDict structure and field interoperability."""
    state: MarketingOSState = {
        "thread_id": "thread_test_01",
        "campaign_id": "camp_test_01",
        "user_command": "Execute Q4 launch",
        "task_description": "Run strategy and creative",
        "active_skills": ["brand_rag", "copy_generator"],
        "research_dossier": {"insights": "positive"},
        "campaign_blueprint": {"campaign_id": "camp_test_01"},
        "platform_publish_results": [],
        "critique_history": ["First review note"],
        "revision_count": 1,
        "approval_status": "pending",
        "human_approved": False,
        "analytics_anomalies": [],
    }
    assert state["thread_id"] == "thread_test_01"
    assert state["approval_status"] == "pending"
    assert len(state["critique_history"]) == 1
