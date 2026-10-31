import pytest
from app.agents.validators.campaign_schema import CampaignValidationError, validate_campaign_blueprint
from app.agents.validators.platform_limits import (
    PLATFORM_CHAR_LIMITS,
    sanitize_gbp_summary,
    validate_platform_asset_compliance,
    validate_text_limit,
)
from app.core.config import settings
from app.integrations.llm.ollama_client import OllamaInvariantError, ollama_client
from app.integrations.social.facebook import FacebookAdapter
from app.integrations.social.google_business_profile import GoogleBusinessProfileAdapter
from app.integrations.social.instagram import InstagramAdapter
from app.integrations.social.linkedin import LinkedInAdapter
from app.integrations.social.pinterest import PinterestAdapter
from app.integrations.social.threads import ThreadsAdapter
from app.integrations.social.x_twitter import XTwitterAdapter
from app.integrations.social.youtube import YouTubeAdapter
from app.services.sandbox_service import SandboxSecurityViolation, SandboxService
from app.tasks.analytics_tasks import (
    calculate_engagement_velocity,
    detect_metric_anomalies,
    export_weekly_analytics_backup,
)
from app.tasks.beat_schedule import CELERY_BEAT_SCHEDULE
from pydantic import BaseModel


def test_ollama_client_invariant_issue_8095():
    """Verify Ollama Issue #8095 invariant: tools and format cannot be used simultaneously.

    Also verify structured outputs enforce temperature=0 and num_ctx=32768, and concurrency is bounded.
    """
    # 1. Dual tools and format must raise OllamaInvariantError
    tools = [{"type": "function", "function": {"name": "test_tool"}}]
    format_schema = {"type": "object"}

    with pytest.raises(OllamaInvariantError, match="Issue #8095 Invariant Violation"):
        ollama_client.validate_request_invariants(tools=tools, format=format_schema)

    # 2. Structured output turn enforces temperature=0 and num_ctx=32768
    options = ollama_client.validate_request_invariants(tools=None, format=format_schema)
    assert options["temperature"] == 0.0
    assert options["num_ctx"] == 32768

    # 3. Tool-calling turn allows tools when format is None
    tool_options = ollama_client.validate_request_invariants(tools=tools, format=None)
    assert "temperature" not in tool_options

    # 4. Concurrency bounds configured in settings
    assert settings.OLLAMA_MAX_LOADED_MODELS == 2
    assert settings.OLLAMA_NUM_PARALLEL == 2


def test_platform_limits_and_sanitization():
    """Verify platform limits, format restrictions, and GBP policy sanitization."""
    # 1. Character limits defined for all 8 platforms
    for p in ["linkedin", "youtube", "instagram", "threads", "facebook", "x", "pinterest", "google_business_profile"]:
        assert p in PLATFORM_CHAR_LIMITS
        assert validate_text_limit(p, "Short compliant copy") is True

    # 2. X post character ceiling (<=280)
    assert validate_text_limit("x", "a" * 280) is True
    assert validate_text_limit("x", "a" * 281) is False

    # 3. LinkedIn rejects organic carousels
    passed, errors = validate_platform_asset_compliance(
        platform="linkedin",
        copy_text="Valid text",
        media_urls=["https://example.org/1.jpg", "https://example.org/2.jpg"],
        is_carousel=True,
    )
    assert passed is False
    assert any("organic carousels are unsupported" in err.lower() for err in errors)

    # 4. GBP sanitization strips raw phone numbers and emails to prevent REJECTED state
    raw_text = "Call us at +1 (555) 234-5678 or reach out to support@enterprise.local for enterprise OS!"
    sanitized = sanitize_gbp_summary(raw_text)
    assert "+1 (555) 234-5678" not in sanitized
    assert "support@enterprise.local" not in sanitized
    assert "[Contact via Profile]" in sanitized
    assert "[Contact via Website]" in sanitized

    # 5. GBP rejects video posts
    passed_gbp, gbp_errors = validate_platform_asset_compliance(
        platform="google_business_profile",
        copy_text="Local post update",
        media_urls=["https://example.org/video.mp4"],
        media_type="video",
    )
    assert passed_gbp is False
    assert any("rejects video" in err.lower() for err in gbp_errors)


def test_sandbox_security_and_hmac_capability_tokens():
    """Verify ephemeral worker isolation: read-only rootfs, tmpfs, cap-drop, and HMAC capability tokens."""
    # 1. Build hardened Podman/gVisor command
    from pathlib import Path

    cmd = SandboxService.build_podman_command(
        job_dir=Path("/tmp"),
        script_name="task.py",
        network="none",
        use_runsc=True,
    )
    assert "--read-only" in cmd
    assert "--tmpfs" in cmd
    assert "/tmp:rw,noexec,nosuid,size=256m" in cmd
    assert "--cap-drop=ALL" in cmd
    assert "--security-opt=no-new-privileges" in cmd
    assert "--runtime=runsc" in cmd

    # 2. HMAC capability token signing & verification
    token = SandboxService.sign_capability_token(
        worker_id="researcher_01",
        allowed_tools=["searxng_search", "rag_read_brand_docs"],
        ttl_seconds=180,
    )
    assert SandboxService.verify_capability_token(token, "searxng_search") is True
    assert SandboxService.verify_capability_token(token, "rag_read_brand_docs") is True
    assert SandboxService.verify_capability_token(token, "unauthorized_tool") is False

    # 3. Worker environment must reject social OAuth credentials
    safe_env = {"JOB_PARAM": "test"}
    sanitized = SandboxService.sanitize_worker_env(safe_env)
    assert sanitized["JOB_PARAM"] == "test"

    insecure_env = {"LINKEDIN_OAUTH_ACCESS_TOKEN": "secret_abc"}
    with pytest.raises(SandboxSecurityViolation, match="Security policy violation"):
        SandboxService.sanitize_worker_env(insecure_env)


@pytest.mark.asyncio
async def test_all_8_social_adapters_7_stage_contract():
    """Verify all 8 platform adapters implement 7-stage contract, guards, and read-after-write verification."""
    adapters = [
        (LinkedInAdapter(), {"copy_text": "LinkedIn executive post", "aspect_ratio": "1:1"}),
        (YouTubeAdapter(), {"title": "Architecture Overview", "copy_text": "Video description", "aspect_ratio": "16:9"}),
        (InstagramAdapter(), {"copy_text": "Visual brand post", "media_urls": ["https://example.org/photo.jpg"], "aspect_ratio": "1:1"}),
        (ThreadsAdapter(), {"copy_text": "B2B threads hook", "aspect_ratio": "1:1"}),
        (FacebookAdapter(), {"copy_text": "Facebook page update", "aspect_ratio": "16:9"}),
        (XTwitterAdapter(), {"copy_text": "X post under 280 chars", "aspect_ratio": "16:9"}),
        (PinterestAdapter(), {"title": "Architecture Pin", "copy_text": "Visual Pin description", "aspect_ratio": "2:3"}),
        (GoogleBusinessProfileAdapter(), {"copy_text": "Local update Call +1 555-019-2834 or visit email test@test.com", "aspect_ratio": "1:1"}),
    ]

    for adapter, payload in adapters:
        res = await adapter.publish(payload, {"access_token": "mock_token", "tier": "trial"})
        assert res["platform"] == adapter.platform_name
        assert "post_id" in res
        assert res["verified"] is True
        assert res["status"] in ("VERIFIED_PUBLISHED", "SANDBOX_ONLY")
        assert "url" in res


@pytest.mark.asyncio
async def test_pinterest_trial_sandbox_detection():
    """Verify Pinterest Trial tier flags entity visibility as SANDBOX_ONLY."""
    adapter = PinterestAdapter()
    payload = {"title": "Pin Title", "copy_text": "Pin desc"}

    # Trial tier credentials
    trial_res = await adapter.publish(payload, {"access_token": "mock_token", "tier": "trial"})
    assert trial_res["status"] == "SANDBOX_ONLY"
    assert trial_res["is_sandbox"] is True

    # Standard tier credentials
    std_res = await adapter.publish(payload, {"access_token": "mock_token", "tier": "standard", "is_sandbox": False})
    assert std_res["status"] == "VERIFIED_PUBLISHED"
    assert std_res["is_sandbox"] is False


@pytest.mark.asyncio
async def test_instagram_jpeg_only_enforcement():
    """Verify Instagram adapter rejects non-JPEG image formats during pre-flight."""
    adapter = InstagramAdapter()
    png_payload = {
        "copy_text": "Valid IG caption",
        "media_urls": ["https://example.org/image.png"],  # PNG disallowed
        "media_type": "image",
    }
    pre_flight = await adapter.pre_flight_check(png_payload, {"access_token": "mock_token"})
    assert pre_flight["eligible"] is False
    assert "jpeg format only" in pre_flight["reason"].lower()


@pytest.mark.asyncio
async def test_youtube_unaudited_private_guard():
    """Verify YouTube adapter forces privacyStatus to private for un-audited projects."""
    adapter = YouTubeAdapter()
    payload = {"title": "Audit Test", "copy_text": "Testing private guard"}

    # Unaudited
    unaudited_res = await adapter.execute_publish(payload, {"access_token": "mock_token", "is_audited": False})
    assert unaudited_res["privacy_status"] == "private"

    # Audited
    audited_res = await adapter.execute_publish(payload, {"access_token": "mock_token", "is_audited": True})
    assert audited_res["privacy_status"] == "public"


def test_engagement_velocity_and_closed_loop_eval():
    """Verify Engagement Velocity calculation and N >= 5 anomaly threshold."""
    # EV = [ (Likes + 2 * Comments + 3 * Shares/Saves) / max(Impressions, 100) ] * (24 / delta_t_hours)
    ev = calculate_engagement_velocity(likes=100, comments=20, shares_saves=10, impressions=1000, delta_t_hours=24.0)
    # (100 + 40 + 30) / 1000 * 1 = 170 / 1000 = 0.1700
    assert ev == 0.17

    # Under minimum sample size N=4 (<5), anomaly detection yields empty list
    small_series = [10.0, 12.0, 11.0, 100.0]
    small_platforms = ["linkedin", "youtube", "x", "instagram"]
    assert detect_metric_anomalies(small_series, small_platforms, min_sample_size=5) == []

    # With N=8 (>=5), breakout and underperformance are detected (|Z| > 1.5)
    metric_series = [420.0, 1450.0, 310.0, 95.0, 240.0, 180.0, 45.0, 110.0]
    platforms = [
        "linkedin", "youtube", "instagram", "threads",
        "facebook", "x", "pinterest", "google_business_profile"
    ]
    anomalies = detect_metric_anomalies(metric_series, platforms, min_sample_size=5)
    assert len(anomalies) > 0
    types = {a["anomaly_type"] for a in anomalies}
    assert "breakout" in types

    # Weekly backup is registered in Celery Beat schedule for Sunday 02:00 UTC
    assert "weekly-analytics-backup-sunday" in CELERY_BEAT_SCHEDULE
    task_def = CELERY_BEAT_SCHEDULE["weekly-analytics-backup-sunday"]
    assert task_def["task"] == "app.tasks.analytics_tasks.export_weekly_analytics_backup"


@pytest.mark.asyncio
async def test_analytics_overview_and_optimization_proposals():
    """Verify AnalyticsOverviewResponse schema and OptimizationProposal derivation."""
    from app.schemas.analytics import AnalyticsOverviewResponse, AnomalyAlert, CrossPlatformKPIs, OptimizationProposal

    kpis = CrossPlatformKPIs(
        impressions_total=10000,
        clicks_total=350,
        ctr_average=0.035,
        conversions_total=45,
        platforms_active=8,
    )
    outliers = [
        AnomalyAlert(
            platform="youtube",
            metric="engagement_velocity",
            z_score=2.15,
            observed_value=1450.0,
            baseline_mean=356.0,
            recommendation="Breakout performance on youtube: scale budget +35%",
        ),
        AnomalyAlert(
            platform="pinterest",
            metric="engagement_velocity",
            z_score=-1.85,
            observed_value=45.0,
            baseline_mean=356.0,
            recommendation="Underperformance on pinterest: route copy to creative revision loop",
        ),
    ]
    proposals = [
        OptimizationProposal(
            proposal_id="opt_test_01",
            cohort_size=8,
            anomalies_count=2,
            actions=["Scale budget on youtube", "Revise creative on pinterest"],
            proposed_changes={"scale_platforms": ["youtube"], "revise_platforms": ["pinterest"]},
        )
    ]
    overview = AnalyticsOverviewResponse(kpis=kpis, outliers=outliers, proposals=proposals)
    assert overview.kpis.platforms_active == 8
    assert len(overview.outliers) == 2
    assert len(overview.proposals) == 1
    assert overview.proposals[0].proposed_changes["scale_platforms"] == ["youtube"]


@pytest.mark.asyncio
async def test_facebook_video_and_x_chunked_upload_support():
    """Verify Facebook video routing and X Twitter chunked upload method."""
    fb = FacebookAdapter()
    video_payload = {"copy_text": "Video update", "media_urls": ["https://example.org/video.mp4"], "media_type": "video"}
    res = await fb.publish(video_payload, {"access_token": "mock_token"})
    assert res["status"] in ("VERIFIED_PUBLISHED", "PUBLISHED_UNVERIFIED")

    xt = XTwitterAdapter()
    assert hasattr(xt, "upload_media_chunked")
