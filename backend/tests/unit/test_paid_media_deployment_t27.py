"""Unit tests for T27: Publish Approved Paid Campaigns & Bid Targets (Outbound Actuation MCP Boundary)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.exceptions import (
    ApprovalRequiredError,
    ConfigurationError,
    PolicyViolationError,
    SignatureVerificationError,
)
from app.integrations.ads.base import AdsAdapter
from app.integrations.ads.google import GoogleAdsAdapter
from app.integrations.ads.linkedin import LinkedInAdsAdapter
from app.integrations.ads.meta import MetaAdsAdapter
from app.integrations.ads.tiktok import TikTokAdsAdapter
from app.mcp.outbound_gateway import OutboundGateway, canonical_dispatch_bytes
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewKind,
    HumanDecisionType,
    ReviewStatus,
    ReviewerRole,
    SignedApprovalClearance,
)
from app.schemas.dispatch import AudienceToken, DispatchDirective, PaidCampaignDeploymentResult
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
        approver_role="finance",
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
    tenant_id: str = "tenant_ad_corp",
    task_id: str = "task_t27_ad",
    preview_kind: ActionPreviewKind = ActionPreviewKind.SPEND,
    approved_scope: dict[str, Any] | None = None,
    meta_adapter: MetaAdsAdapter | None = None,
    google_adapter: GoogleAdsAdapter | None = None,
    tiktok_adapter: TikTokAdsAdapter | None = None,
    linkedin_adapter: LinkedInAdsAdapter | None = None,
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
        directive_id="directive_t27_01",
        worker_role=WorkerRole.STRATEGY,
        tenant_id=tenant_id,
        status=TaskStatus.APPROVED,
    )
    state_repo.states[task_id] = initial_state

    ads_adapters: dict[str, AdsAdapter] = {
        "meta": meta_adapter or MetaAdsAdapter(None),
        "google": google_adapter or GoogleAdsAdapter(None),
        "tiktok": tiktok_adapter or TikTokAdsAdapter(None),
        "linkedin": linkedin_adapter or LinkedInAdsAdapter(None),
    }

    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=crypto,
        ads_adapters=ads_adapters,
        provenance_recorder=prov_recorder,
        task_state_service=state_service,
    )

    preview = ActionPreview(
        preview_id="preview_t27_1",
        task_id=task_id,
        tenant_id=tenant_id,
        kind=preview_kind,
        summary="Launch Q4 performance marketing campaign",
        spend_amount=1000.0,
        risk_level=RiskLevel.LOW,
        details={"campaign_name": "Q4_Conversion_Boost"},
    )
    hitl.submit_for_approval(preview)

    content_hash = compute_preview_hash(preview)
    clearance = _make_clearance(
        preview.preview_id,
        preview.task_id,
        tenant_id,
        content_hash,
        public_pem,
        approved_scope=approved_scope or {"spend_amount": 1000.0, "max_bid": 5.0},
    )

    decision = hitl.decide(
        preview.preview_id,
        approved=True,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE,
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
async def test_t27_successful_meta_campaign_dispatch(ed25519_keypair) -> None:
    """Publishes an approved Meta campaign within budget, bid, and creative scopes."""
    approved_scope = {
        "spend_amount": 500.0,
        "max_bid": 2.50,
        "creative_refs": ["creative_meta_hero_v1"],
        "account_id": "act_meta_12345",
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
    ) = _setup_pipeline(ed25519_keypair, approved_scope=approved_scope)

    payload = {
        "campaign_id": "cmp_meta_987",
        "account_id": "act_meta_12345",
        "budget": 500.0,
        "bid_amount": 2.50,
        "creative_refs": ["creative_meta_hero_v1"],
        "status": "ACTIVE",
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="meta",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    result = await gateway.execute(dispatch)

    assert result["status_code"] == "200"
    assert result["channel"] == "meta"
    assert result["campaign_id"] == "cmp_meta_987"
    assert result["status"] == "published"
    assert result["applied_budget"] == 500.0
    assert result["applied_bid"] == 2.50

    # CTS State verification
    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.COMPLETED
    assert "paid_campaign" in task_state.cts_state
    paid_info = task_state.cts_state["paid_campaign"]
    assert paid_info["channel"] == "meta"
    assert paid_info["applied_budget"] == 500.0
    assert paid_info["creative_refs"] == ["creative_meta_hero_v1"]

    # Provenance chain verification
    chain = await prov_repo.chain(preview.tenant_id)
    assert any(r.activity == "outbound_meta_deployment_executed" for r in chain)


@pytest.mark.asyncio
async def test_t27_successful_google_campaign_dispatch(ed25519_keypair) -> None:
    """Publishes an approved Google Ads campaign within approved customer and target CPA scopes."""
    approved_scope = {
        "spend_amount": 1000.0,
        "target_cpa": 15.0,
        "customer_id": "cust_google_888",
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
    ) = _setup_pipeline(ed25519_keypair, approved_scope=approved_scope)

    payload = {
        "campaign_id": "cmp_goog_555",
        "customer_id": "cust_google_888",
        "daily_budget": 800.0,
        "bid_amount": 14.50,
        "status": "ACTIVE",
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="google",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    result = await gateway.execute(dispatch)

    assert result["status_code"] == "200"
    assert result["channel"] == "google"
    assert result["customer_id"] == "cust_google_888"

    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.COMPLETED
    assert task_state.cts_state["paid_campaign"]["channel"] == "google"


@pytest.mark.asyncio
async def test_t27_successful_tiktok_campaign_dispatch(ed25519_keypair) -> None:
    """Publishes an approved TikTok Ads campaign."""
    approved_scope = {
        "budget": 300.0,
        "advertiser_id": "adv_tt_333",
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
    ) = _setup_pipeline(ed25519_keypair, approved_scope=approved_scope)

    payload = {
        "campaign_id": "cmp_tt_111",
        "advertiser_id": "adv_tt_333",
        "budget": 300.0,
        "status": "ACTIVE",
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="tiktok",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    result = await gateway.execute(dispatch)

    assert result["status_code"] == "200"
    assert result["channel"] == "tiktok"
    assert result["advertiser_id"] == "adv_tt_333"

    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_t27_linkedin_rejected_without_explicit_authorization(ed25519_keypair) -> None:
    """Ensures LinkedIn is rejected by default for canonical T27 without explicit HITL scope."""
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
    ) = _setup_pipeline(ed25519_keypair)

    payload = {"campaign_id": "cmp_li_999", "budget": 200.0}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="linkedin",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError, match="Platform 'linkedin' is not permitted for canonical T27"):
        await gateway.execute(dispatch)


@pytest.mark.asyncio
async def test_t27_linkedin_succeeds_when_explicitly_authorized(ed25519_keypair) -> None:
    """Ensures LinkedIn succeeds when explicitly authorized in governing approval clearance."""
    approved_scope = {
        "spend_amount": 500.0,
        "authorized_platforms": ["linkedin"],
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
    ) = _setup_pipeline(ed25519_keypair, approved_scope=approved_scope)

    payload = {"campaign_id": "cmp_li_999", "account_id": "act_li_444", "budget": 450.0}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="linkedin",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    result = await gateway.execute(dispatch)

    assert result["status_code"] == "200"
    assert result["channel"] == "linkedin"
    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_t27_unsupported_platform_rejected(ed25519_keypair) -> None:
    """Ensures unsupported paid-media platforms (e.g., Snapchat, Pinterest) are blocked."""
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
    ) = _setup_pipeline(ed25519_keypair)

    payload = {"campaign_id": "cmp_snap_123", "budget": 100.0}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="snapchat",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError, match="Unsupported or unapproved paid-media platform 'snapchat'"):
        await gateway.execute(dispatch)


@pytest.mark.asyncio
async def test_t27_spend_escalation_blocked(ed25519_keypair) -> None:
    """Blocks any dispatch attempting to spend beyond the HITL-approved limit."""
    approved_scope = {"spend_amount": 250.0}
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
    ) = _setup_pipeline(ed25519_keypair, approved_scope=approved_scope)

    # Escalating to $500
    payload = {"campaign_id": "cmp_meta_esc", "budget": 500.0}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="meta",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError, match="exceeds HITL-approved scope"):
        await gateway.execute(dispatch)


@pytest.mark.asyncio
async def test_t27_bid_escalation_blocked(ed25519_keypair) -> None:
    """Blocks any dispatch attempting a bid target beyond the HITL-approved limit."""
    approved_scope = {"max_bid": 1.50, "spend_amount": 1000.0}
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
    ) = _setup_pipeline(ed25519_keypair, approved_scope=approved_scope)

    # Escalating bid target to $3.00
    payload = {"campaign_id": "cmp_meta_bid", "budget": 500.0, "bid_amount": 3.00}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="meta",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError, match="exceeds HITL-approved bid target"):
        await gateway.execute(dispatch)


@pytest.mark.asyncio
async def test_t27_altered_creative_or_claim_blocked(ed25519_keypair) -> None:
    """Blocks dispatch if creative references or claim IDs were altered from approved set."""
    approved_scope = {
        "creative_refs": ["approved_asset_01"],
        "claim_ids": ["legal_claim_42"],
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
    ) = _setup_pipeline(ed25519_keypair, approved_scope=approved_scope)

    # Attempting unapproved creative
    payload_creative_mutated = {
        "campaign_id": "cmp_meta_01",
        "creative_refs": ["approved_asset_01", "unapproved_sneaky_asset"],
    }
    dispatch_c = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="meta",
        payload=payload_creative_mutated,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )
    with pytest.raises(PolicyViolationError, match="Payload contains unapproved creative references"):
        await gateway.execute(dispatch_c)

    # Attempting unapproved claim
    payload_claim_mutated = {
        "campaign_id": "cmp_meta_01",
        "creative_refs": ["approved_asset_01"],
        "claim_ids": ["unverified_claim_999"],
    }
    dispatch_cl = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="meta",
        payload=payload_claim_mutated,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )
    with pytest.raises(PolicyViolationError, match="Payload contains unapproved claim references"):
        await gateway.execute(dispatch_cl)


@pytest.mark.asyncio
async def test_t27_cross_tenant_account_mismatch_blocked(ed25519_keypair) -> None:
    """Blocks cross-tenant account mismatches between approved scope and payload."""
    approved_scope = {"account_id": "act_tenant_alpha"}
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
    ) = _setup_pipeline(ed25519_keypair, approved_scope=approved_scope)

    payload = {"campaign_id": "cmp_meta_01", "account_id": "act_tenant_bravo"}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="meta",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(PolicyViolationError, match="Account mismatch on 'account_id'"):
        await gateway.execute(dispatch)


@pytest.mark.asyncio
async def test_t27_invalid_signature_or_unapproved_blocked(ed25519_keypair) -> None:
    """Fails closed on missing HITL approval or forged cryptographic signature."""
    (
        gateway,
        hitl,
        _,
        _,
        _,
        _,
        _,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(ed25519_keypair)

    payload = {"campaign_id": "cmp_meta_01"}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="meta",
        payload=payload,
    )

    # 1. Invalid signature
    forged_dispatch = dispatch.model_copy(update={"signature": "bad_sig_abc"})
    with pytest.raises(SignatureVerificationError):
        await gateway.execute(forged_dispatch)

    # 2. Unapproved preview
    unapproved_preview = ActionPreview(
        preview_id="preview_unapproved_99",
        task_id="task_99",
        kind=ActionPreviewKind.SPEND,
        summary="Unapproved spend",
        risk_level=RiskLevel.HIGH,
    )
    hitl.submit_for_approval(unapproved_preview)
    unapproved_dispatch = dispatch.model_copy(update={"action_preview_id": unapproved_preview.preview_id})
    sig_unapp = sign_payload(canonical_dispatch_bytes(unapproved_dispatch), private_key)
    unapproved_dispatch = unapproved_dispatch.model_copy(update={"signature": sig_unapp})

    with pytest.raises(ApprovalRequiredError):
        await gateway.execute(unapproved_dispatch)


@pytest.mark.asyncio
async def test_t27_duplicate_dispatch_idempotent_no_duplicate_spend(ed25519_keypair) -> None:
    """Verifies that replaying an identical dispatch returns cached execution without duplicate spend."""
    approved_scope = {"spend_amount": 500.0}

    class CountingMetaAdapter(MetaAdsAdapter):
        def __init__(self) -> None:
            super().__init__(None)
            self.call_count = 0

        async def apply_action(self, payload: dict[str, Any]) -> dict[str, Any]:
            self.call_count += 1
            return await super().apply_action(payload)

    counting_adapter = CountingMetaAdapter()
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
        approved_scope=approved_scope,
        meta_adapter=counting_adapter,
    )

    payload = {"campaign_id": "cmp_meta_repeat", "budget": 500.0}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="meta",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
        idempotency_key="unique_dispatch_key_777",
    )

    # First execution
    res1 = await gateway.execute(dispatch)
    assert counting_adapter.call_count == 1
    assert res1["status_code"] == "200"

    # Second execution with exact same key and signature
    res2 = await gateway.execute(dispatch)
    # The adapter was NOT called again; zero duplicate spend!
    assert counting_adapter.call_count == 1
    assert res2 == res1


@pytest.mark.asyncio
async def test_t27_provider_failure_marks_cts_failed(ed25519_keypair) -> None:
    """Verifies that provider-level failure transitions CTS to FAILED and audits failure."""
    class FailingTikTokAdapter(TikTokAdsAdapter):
        def __init__(self) -> None:
            super().__init__(None)

        async def apply_action(self, payload: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("TikTok API connection reset: 503 Service Unavailable")

    failing_adapter = FailingTikTokAdapter()
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
        tiktok_adapter=failing_adapter,
    )

    payload = {"campaign_id": "cmp_tt_fail", "budget": 100.0}
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="tiktok",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    with pytest.raises(RuntimeError, match="503 Service Unavailable"):
        await gateway.execute(dispatch)

    task_state = await state_repo.require(preview.task_id)
    assert task_state.status == TaskStatus.FAILED

    chain = await prov_repo.chain(preview.tenant_id)
    assert any(r.activity == "outbound_tiktok_deployment_failed" for r in chain)


@pytest.mark.asyncio
async def test_t27_secret_redaction_in_provenance_and_logs(ed25519_keypair) -> None:
    """Verifies that secrets (access_token, api_key, private_key) are scrubbed from provenance records."""
    (
        gateway,
        _,
        _,
        _,
        _,
        _,
        prov_repo,
        private_key,
        _,
        preview,
        clearance,
    ) = _setup_pipeline(ed25519_keypair)

    payload = {
        "campaign_id": "cmp_meta_secret",
        "budget": 200.0,
        "access_token": "EAAX_super_secret_meta_user_token_99999",
        "api_key": "api_secret_key_12345",
    }
    dispatch = _sign_and_build_dispatch(
        private_key,
        preview.preview_id,
        preview.task_id,
        preview.tenant_id,
        channel="meta",
        payload=payload,
        preview_content_hash=clearance.preview_content_hash,
        clearance_id=clearance.clearance_id,
    )

    await gateway.execute(dispatch)

    chain = await prov_repo.chain(preview.tenant_id)
    for record in chain:
        record_json = json.dumps(record.metadata, default=str)
        assert "EAAX_super_secret_meta_user_token_99999" not in record_json
        assert "api_secret_key_12345" not in record_json
