"""Unit tests for T28: Publish Approved Social Posts & Assets (Outbound Actuation MCP Boundary)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import (
    ApprovalRequiredError,
    ConfigurationError,
    PolicyViolationError,
    SignatureVerificationError,
)
from app.integrations.social.base import SocialMediaAdapter
from app.integrations.social.instagram import InstagramSocialAdapter
from app.integrations.social.tiktok import TikTokSocialAdapter
from app.integrations.social.x import XSocialAdapter
from app.integrations.social.youtube import YouTubeSocialAdapter
from app.mcp.outbound_gateway import OutboundGateway, canonical_dispatch_bytes
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewKind,
    HumanDecisionType,
    ReviewStatus,
    ReviewerRole,
    SignedApprovalClearance,
)
from app.schemas.dispatch import AudienceToken, DispatchDirective, SocialPostDeploymentResult
from app.schemas.governance import RiskLevel, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import HitlCoordinator, compute_preview_hash
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class InMemoryTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task '{task_id}' not found.")
        return self.states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state


def _make_clearance(
    preview_id: str,
    task_id: str,
    tenant_id: str,
    content_hash: str,
    public_pem: str,
    approved_scope: dict[str, Any] | None = None,
) -> SignedApprovalClearance:
    return SignedApprovalClearance(
        clearance_id=f"clr-{preview_id}",
        preview_id=preview_id,
        task_id=task_id,
        tenant_id=tenant_id,
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role="brand_lead",
        approved_scope=approved_scope or {},
        preview_content_hash=content_hash,
        signature="simulated_valid_clearance_signature",
        public_key_pem=public_pem,
        is_valid=True,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )


def _setup_pipeline(
    ed25519_keypair,
    *,
    tenant_id: str = "tenant_social_corp",
    task_id: str = "task_t28_social",
    preview_kind: ActionPreviewKind = ActionPreviewKind.COPY,
    copy_text: str = "Introducing our breakthrough product launch! #innovation",
    approved_scope: dict[str, Any] | None = None,
    instagram_adapter: InstagramSocialAdapter | None = None,
    x_adapter: XSocialAdapter | None = None,
    youtube_adapter: YouTubeSocialAdapter | None = None,
    tiktok_adapter: TikTokSocialAdapter | None = None,
):
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    crypto = CryptographicValidator(public_pem)
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)

    state_repo = InMemoryTaskStateRepository()
    from app.orchestration.task_state_machine import TaskStateMachine

    state_machine = TaskStateMachine()
    state_service = TaskStateService(state_repo, state_machine, prov_recorder)

    initial_state = CanonicalTaskState(
        task_id=task_id,
        directive_id="directive_t28_01",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_id=tenant_id,
        status=TaskStatus.APPROVED,
    )
    state_repo.states[task_id] = initial_state

    social_adapters: dict[str, SocialMediaAdapter] = {
        "instagram": instagram_adapter or InstagramSocialAdapter(None),
        "x": x_adapter or XSocialAdapter(None),
        "youtube": youtube_adapter or YouTubeSocialAdapter(None),
        "tiktok": tiktok_adapter or TikTokSocialAdapter(None),
    }

    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=crypto,
        social_adapters=social_adapters,
        provenance_recorder=prov_recorder,
        task_state_service=state_service,
    )

    preview = ActionPreview(
        preview_id="preview_t28_1",
        task_id=task_id,
        tenant_id=tenant_id,
        kind=preview_kind,
        summary="Publish official social launch post",
        spend_amount=0.0,
        risk_level=RiskLevel.LOW,
        details={
            "copy_text": copy_text,
            "media_asset_ids": ["asset_hero_img_01"],
            "claim_ids": ["claim_zero_emission_01"],
        },
    )
    hitl.submit_for_approval(preview)

    content_hash = compute_preview_hash(preview)
    computed_copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()

    default_scope = {
        "copy_hash": computed_copy_hash,
        "media_asset_ids": ["asset_hero_img_01"],
        "claim_ids": ["claim_zero_emission_01"],
    }
    if approved_scope:
        default_scope.update(approved_scope)

    clearance = _make_clearance(
        preview.preview_id,
        preview.task_id,
        tenant_id,
        content_hash,
        public_pem,
        approved_scope=default_scope,
    )

    decision = hitl.decide(
        preview.preview_id,
        approved=True,
        approver="[email protected]",
        approver_role=ReviewerRole.BRAND_LEAD,
        tenant_id=tenant_id,
    )
    decision.clearance = clearance

    return (
        gateway,
        hitl,
        crypto,
        state_service,
        state_repo,
        prov_recorder,
        prov_repo,
        private_key,
        public_pem,
        preview,
        clearance,
    )


def _sign_and_build_dispatch(
    private_key,
    preview_id: str,
    task_id: str,
    tenant_id: str,
    channel: str,
    payload: dict[str, Any],
    preview_content_hash: str | None = None,
    clearance_id: str | None = None,
    idempotency_key: str | None = None,
) -> DispatchDirective:
    now = datetime.now(UTC)
    dispatch = DispatchDirective(
        dispatch_id=f"disp_{channel}_01",
        task_id=task_id,
        tenant_id=tenant_id,
        action_preview_id=preview_id,
        channel=channel,
        action_type="publish",
        payload=payload,
        approved_by="[email protected]",
        approved_at=now,
        signature="",
        preview_content_hash=preview_content_hash,
        clearance_id=clearance_id,
        idempotency_key=idempotency_key or f"idem_{channel}_01",
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), private_key)
    return dispatch.model_copy(update={"signature": sig})


@pytest.mark.asyncio
async def test_t28_successful_instagram_post_dispatch(ed25519_keypair) -> None:
    """Publishes an approved Instagram post matching copy hash, media asset, and account ID."""
    copy_text = "Check out our newest sustainable line! #green"
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {
        "copy_hash": copy_hash,
        "media_asset_ids": ["img_ig_eco_01"],
        "ig_user_id": "ig_account_eco_official",
    }
    (
        gateway,
        _,
        _,
        _,
        state_repo,
        _,
        prov_repo,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
    )

    payload = {
        "caption": copy_text,
        "media_asset_ids": ["img_ig_eco_01"],
        "ig_user_id": "ig_account_eco_official",
        "image_url": "https://cdn.enterprise.test/assets/eco_01.jpg",
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "instagram",
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    readiness = await gateway.validate_readiness(dispatch)
    assert readiness.is_ready is True

    result = await gateway.execute(dispatch)
    assert result.get("status") == "published"
    assert "post_id" in result or "creation_id" in result

    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.COMPLETED
    assert "social_post" in task_state.cts_state
    social_cts = task_state.cts_state["social_post"]
    assert social_cts["channel"] == "instagram"
    assert social_cts["status"] == "published"
    assert social_cts["content_hash"] == clearance.preview_content_hash
    assert social_cts["media_asset_ids"] == ["img_ig_eco_01"]

    records = prov_repo._chains.get(preview.tenant_id, [])
    events = [e for e in records if e.activity == "outbound_instagram_deployment_executed"]
    assert len(events) == 1


@pytest.mark.asyncio
async def test_t28_successful_x_post_dispatch(ed25519_keypair) -> None:
    """Publishes an approved X (Twitter) tweet without scheduling matching copy hash and author ID."""
    copy_text = "Live now: Enterprise OS Release 2.0 with cryptographic HITL! https://enterprisestore.test"
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {
        "copy_hash": copy_hash,
        "author_id": "x_author_enterprise_123",
    }
    (
        gateway,
        _,
        _,
        _,
        state_repo,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
    )

    payload = {
        "text": copy_text,
        "author_id": "x_author_enterprise_123",
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "x",
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    readiness = await gateway.validate_readiness(dispatch)
    assert readiness.is_ready is True

    result = await gateway.execute(dispatch)
    assert result.get("status") == "published"
    assert "post_id" in result

    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.COMPLETED
    assert task_state.cts_state["social_post"]["channel"] == "x"


@pytest.mark.asyncio
async def test_t28_successful_youtube_video_dispatch(ed25519_keypair) -> None:
    """Publishes an approved YouTube video with title, description, and channel ID."""
    copy_text = "Detailed architecture walkthrough of the Outbound Actuation MCP Boundary."
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {
        "copy_hash": copy_hash,
        "channel_id": "yt_chan_enterprise_global",
        "media_asset_ids": ["video_asset_t28_mcp"],
    }
    (
        gateway,
        _,
        _,
        _,
        state_repo,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
    )

    payload = {
        "title": "Enterprise OS Architecture Overview",
        "description": copy_text,
        "channel_id": "yt_chan_enterprise_global",
        "media_asset_ids": ["video_asset_t28_mcp"],
        "video_url": "https://cdn.enterprise.test/videos/arch_overview.mp4",
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "youtube",
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    readiness = await gateway.validate_readiness(dispatch)
    assert readiness.is_ready is True

    result = await gateway.execute(dispatch)
    assert result.get("status") == "published"
    assert "video_id" in result

    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.COMPLETED
    assert task_state.cts_state["social_post"]["channel"] == "youtube"


@pytest.mark.asyncio
async def test_t28_tiktok_rejected_without_explicit_authorization(ed25519_keypair) -> None:
    """Rejects TikTok social dispatch if TikTok is not explicitly listed in clearance scope."""
    copy_text = "Watch this clip on TikTok!"
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {
        "copy_hash": copy_hash,
        # Notice authorized_channels does NOT contain tiktok
        "authorized_channels": ["instagram", "x"],
    }
    (
        gateway,
        _,
        _,
        _,
        _,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
    )

    payload = {"text": copy_text}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "tiktok",
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError) as exc:
        await gateway.validate_readiness(dispatch)
    assert "outside canonical T28 scope" in str(exc.value)


@pytest.mark.asyncio
async def test_t28_tiktok_succeeds_when_explicitly_authorized(ed25519_keypair) -> None:
    """Allows TikTok social dispatch when explicitly authorized in governing clearance."""
    copy_text = "Approved TikTok short video launch!"
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {
        "copy_hash": copy_hash,
        "authorized_channels": ["tiktok"],
    }
    (
        gateway,
        _,
        _,
        _,
        state_repo,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
    )

    payload = {"text": copy_text, "video_url": "https://cdn.enterprise.test/tiktok/short.mp4"}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "tiktok",
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    readiness = await gateway.validate_readiness(dispatch)
    assert readiness.is_ready is True

    result = await gateway.execute(dispatch)
    assert result.get("status") == "published"
    assert "post_id" in result or "publish_id" in result


@pytest.mark.asyncio
async def test_t28_unsupported_channel_rejected(ed25519_keypair) -> None:
    """Rejects actuation directives targeting unsupported/unregistered social channels."""
    copy_text = "Post to unapproved network"
    (
        gateway,
        _,
        _,
        _,
        _,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
    )

    payload = {"text": copy_text}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "threads",  # Unsupported
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError) as exc:
        await gateway.validate_readiness(dispatch)
    assert "Unsupported social channel" in str(exc.value)


@pytest.mark.asyncio
async def test_t28_altered_copy_blocked(ed25519_keypair) -> None:
    """Blocks actuation when dispatch copy text differs from approved copy hash."""
    approved_text = "Approved text that passed brand review."
    approved_hash = hashlib.sha256(approved_text.encode("utf-8")).hexdigest()
    approved_scope = {"copy_hash": approved_hash}

    (
        gateway,
        _,
        _,
        _,
        _,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=approved_text,
        approved_scope=approved_scope,
    )

    # Rogue copy mutation
    tampered_payload = {"text": "Tampered text with unauthorized claims and disclaimers removed."}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "x",
        tampered_payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError) as exc:
        await gateway.validate_readiness(dispatch)
    assert "Copy hash mismatch" in str(exc.value)


@pytest.mark.asyncio
async def test_t28_altered_media_asset_blocked(ed25519_keypair) -> None:
    """Blocks actuation when dispatch references unapproved media asset IDs."""
    copy_text = "Approved promo copy."
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {
        "copy_hash": copy_hash,
        "media_asset_ids": ["img_approved_01", "img_approved_02"],
    }

    (
        gateway,
        _,
        _,
        _,
        _,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
    )

    unapproved_payload = {
        "text": copy_text,
        "media_asset_ids": ["img_approved_01", "unapproved_meme_asset_99"],
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "instagram",
        unapproved_payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError) as exc:
        await gateway.validate_readiness(dispatch)
    assert "Media asset 'unapproved_meme_asset_99' not in approved clearance" in str(exc.value)


@pytest.mark.asyncio
async def test_t28_unapproved_claims_blocked(ed25519_keypair) -> None:
    """Blocks actuation when dispatch introduces claim IDs not approved in clearance."""
    copy_text = "Eco-friendly verified claim."
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {
        "copy_hash": copy_hash,
        "claim_ids": ["claim_eco_01"],
    }

    (
        gateway,
        _,
        _,
        _,
        _,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
    )

    unapproved_payload = {
        "text": copy_text,
        "claim_ids": ["claim_eco_01", "claim_unverified_miracle_cure"],
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "x",
        unapproved_payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError) as exc:
        await gateway.validate_readiness(dispatch)
    assert "Claim 'claim_unverified_miracle_cure' not in approved clearance" in str(exc.value)


@pytest.mark.asyncio
async def test_t28_cross_tenant_account_mismatch_blocked(ed25519_keypair) -> None:
    """Blocks actuation when dispatch attempts to publish to an account ID outside approved scope."""
    copy_text = "Official announcement."
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {
        "copy_hash": copy_hash,
        "ig_user_id": "ig_account_legit_corp",
    }

    (
        gateway,
        _,
        _,
        _,
        _,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
    )

    attacker_payload = {
        "caption": copy_text,
        "ig_user_id": "ig_account_compromised_target",
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "instagram",
        attacker_payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError) as exc:
        await gateway.validate_readiness(dispatch)
    assert "Social account ID mismatch" in str(exc.value)


@pytest.mark.asyncio
async def test_t28_unsupported_scheduling_fails_closed_no_premature_publish(ed25519_keypair) -> None:
    """Ensures scheduling requested on X (unsupported native scheduling) fails closed."""
    copy_text = "Scheduled Tweet for future release."
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    future_time = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    approved_scope = {
        "copy_hash": copy_hash,
        "scheduled_at": future_time,
    }

    x_adapter_mock = AsyncMock(spec=XSocialAdapter)
    x_adapter_mock.publish = AsyncMock()

    (
        gateway,
        _,
        _,
        _,
        _,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
        x_adapter=x_adapter_mock,
    )

    payload = {
        "text": copy_text,
        "scheduled_at": future_time,
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "x",
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    # Must fail closed in readiness validation
    with pytest.raises(PolicyViolationError) as exc:
        await gateway.validate_readiness(dispatch)
    assert "does not support native scheduled posts" in str(exc.value)
    # Ensure the adapter was never called (no premature publication)
    x_adapter_mock.publish.assert_not_called()


@pytest.mark.asyncio
async def test_t28_supported_scheduling_preserved(ed25519_keypair) -> None:
    """Preserves approved schedule for adapters supporting native scheduling (YouTube / Instagram)."""
    copy_text = "Scheduled YouTube premiere video description."
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    future_time = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    approved_scope = {
        "copy_hash": copy_hash,
        "scheduled_at": future_time,
    }

    (
        gateway,
        _,
        _,
        _,
        state_repo,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
    )

    payload = {
        "title": "Future Premiere",
        "description": copy_text,
        "scheduled_at": future_time,
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "youtube",
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    readiness = await gateway.validate_readiness(dispatch)
    assert readiness.is_ready is True

    result = await gateway.execute(dispatch)
    assert result.get("status") == "scheduled"
    assert result.get("scheduled_at") == future_time

    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.COMPLETED
    assert task_state.cts_state["social_post"]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_t28_duplicate_dispatch_idempotent_no_duplicate_post(ed25519_keypair) -> None:
    """Replaying an identical dispatch returns the cached execution result and prevents duplicate actuation."""
    copy_text = "Idempotent social release."
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {"copy_hash": copy_hash}

    ig_adapter = InstagramSocialAdapter(None)
    (
        gateway,
        _,
        _,
        _,
        _,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
        instagram_adapter=ig_adapter,
    )

    payload = {"caption": copy_text}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "instagram",
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
        idempotency_key="unique_idem_key_ig_001",
    )

    res1 = await gateway.execute(dispatch)
    res2 = await gateway.execute(dispatch)

    assert res1 == res2
    assert res1.get("status") == "published"


@pytest.mark.asyncio
async def test_t28_provider_failure_marks_cts_failed_and_secret_redaction(ed25519_keypair) -> None:
    """Simulated provider failure marks CTS as FAILED and sanitizes sensitive credentials in provenance."""
    copy_text = "Failing social post."
    copy_hash = hashlib.sha256(copy_text.encode("utf-8")).hexdigest()
    approved_scope = {"copy_hash": copy_hash}

    failing_adapter = AsyncMock(spec=InstagramSocialAdapter)
    failing_adapter.publish = AsyncMock(side_effect=RuntimeError("Instagram Graph API rate limit exceeded (code 429)"))

    (
        gateway,
        _,
        _,
        _,
        state_repo,
        _,
        prov_repo,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(
        ed25519_keypair,
        copy_text=copy_text,
        approved_scope=approved_scope,
        instagram_adapter=failing_adapter,
    )

    payload = {
        "caption": copy_text,
        "access_token": "EAABsecret_token_12345",
        "app_secret": "sensitive_app_secret_999",
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        "instagram",
        payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(RuntimeError) as exc:
        await gateway.execute(dispatch)
    assert "rate limit exceeded" in str(exc.value)

    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.FAILED

    records = prov_repo._chains.get(preview.tenant_id, [])
    events = [e for e in records if e.activity == "outbound_instagram_deployment_failed"]
    assert len(events) == 1
    event_meta_str = json.dumps(events[0].metadata)
    assert "EAABsecret_token_12345" not in event_meta_str
    assert "sensitive_app_secret_999" not in event_meta_str
    assert "[REDACTED]" in event_meta_str
