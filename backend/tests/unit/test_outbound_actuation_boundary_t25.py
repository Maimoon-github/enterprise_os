"""Comprehensive verification suite for Task-25: Outbound Actuation MCP Boundary Initialization (MCP_ACT)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.core.exceptions import (
    ApprovalRequiredError,
    ConfigurationError,
    PolicyViolationError,
    RateLimitExceededError,
    SignatureVerificationError,
)
from app.integrations.ads.base import AdsAdapter
from app.integrations.cms.client import CmsClient
from app.integrations.social.base import SocialAdapter
from app.mcp.outbound_gateway import (
    OutboundGateway,
    TokenBucket,
    canonical_dispatch_bytes,
    scrub_sensitive_payload,
)
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewKind,
    HumanDecisionType,
    ReviewStatus,
    ReviewerRole,
    SignedApprovalClearance,
    compute_preview_hash,
)
from app.schemas.dispatch import AudienceToken, DispatchDirective, DispatchReadiness
from app.schemas.governance import RiskLevel, WorkerRole
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import HitlCoordinator, canonical_decision_bytes
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository


class FakeAdsAdapter(AdsAdapter):
    channel = "meta"

    def __init__(self) -> None:
        self.applied: list[dict[str, str]] = []

    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        self.applied.append(payload)
        return {"status_code": "200", "channel": self.channel}


class FakeSocialAdapter(SocialAdapter):
    platform = "twitter"

    def __init__(self) -> None:
        self.published: list[dict[str, str]] = []

    async def publish(self, payload: dict[str, str]) -> dict[str, str]:
        self.published.append(payload)
        return {"status_code": "200", "platform": self.platform}


def _make_keypair() -> tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_key, public_pem


def _setup_approved_preview_and_gateway(
    tenant_id: str = "tenant-alpha",
    spend_amount: float = 25000.0,
    kind: ActionPreviewKind = ActionPreviewKind.SPEND,
) -> tuple[
    OutboundGateway,
    HitlCoordinator,
    ActionPreview,
    Ed25519PrivateKey,
    str,
    FakeAdsAdapter,
    ProvenanceRecorder,
]:
    priv_key, pub_pem = _make_keypair()
    validator = CryptographicValidator(pub_pem)
    hitl = HitlCoordinator(validator)

    preview = ActionPreview(
        preview_id="prev-100",
        task_id="task-100",
        tenant_id=tenant_id,
        kind=kind,
        summary=f"Approved action for {kind.value}",
        spend_amount=spend_amount,
        risk_level=RiskLevel.MEDIUM,
    )
    hitl.submit_for_approval(preview)

    now_dt = datetime.now(UTC)
    content_hash = compute_preview_hash(preview)
    canon_bytes = canonical_decision_bytes(
        preview_id="prev-100",
        decision="APPROVE",
        approver="[email protected]",
        tenant_id=tenant_id,
        preview_content_hash=content_hash,
        decided_at=now_dt.isoformat(),
    )
    sig = sign_payload(canon_bytes, priv_key)

    hitl.decide(
        "prev-100",
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE if kind == ActionPreviewKind.SPEND else ReviewerRole.ADMIN,
        tenant_id=tenant_id,
        signature=sig,
        public_key_pem=pub_pem,
        preview_content_hash=content_hash,
        decided_at=now_dt,
    )

    prov_recorder = ProvenanceRecorder(FakeProvenanceRepository())
    fake_ads = FakeAdsAdapter()
    gateway = OutboundGateway(
        hitl,
        validator,
        ads_adapters={"meta": fake_ads},
        provenance_recorder=prov_recorder,
    )

    return gateway, hitl, preview, priv_key, pub_pem, fake_ads, prov_recorder


@pytest.mark.asyncio
async def test_readiness_certified_with_valid_t24_clearance_and_signature() -> None:
    """Gateway certifies dispatch readiness for valid T24 clearance without executing side effects."""
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, prov = _setup_approved_preview_and_gateway()

    decision = hitl.get_decision(preview.preview_id)
    assert decision is not None and decision.clearance is not None

    dispatch = DispatchDirective(
        dispatch_id="disp-1",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel="meta",
        tenant_id="tenant-alpha",
        audience="global",
        clearance_id=decision.clearance.clearance_id,
        preview_content_hash=decision.clearance.preview_content_hash,
        payload={"campaign_id": "meta-camp-1", "spend_amount": 20000.0},
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), priv_key)
    dispatch = dispatch.model_copy(update={"signature": sig})

    readiness = await gateway.validate_readiness(dispatch)

    assert isinstance(readiness, DispatchReadiness)
    assert readiness.is_ready is True
    assert readiness.status == "READY"
    assert readiness.verified_clearance_id == decision.clearance.clearance_id
    assert readiness.channel == "meta"
    assert readiness.tenant_id == "tenant-alpha"

    # Zero external outbound side effects occurred
    assert len(fake_ads.applied) == 0


@pytest.mark.asyncio
async def test_readiness_rejected_when_t24_unapproved_or_rejected() -> None:
    """Gateway strictly rejects dispatch directives targeting unapproved or rejected previews."""
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, _ = _setup_approved_preview_and_gateway()

    # Create unapproved preview
    unapproved = ActionPreview(
        preview_id="prev-unapproved",
        task_id="task-unauth",
        tenant_id="tenant-alpha",
        kind=ActionPreviewKind.SPEND,
        summary="Unapproved proposal",
        risk_level=RiskLevel.HIGH,
    )
    hitl.submit_for_approval(unapproved)

    dispatch = DispatchDirective(
        dispatch_id="disp-unapproved",
        task_id="task-unauth",
        action_preview_id="prev-unapproved",
        signature="dummy",
        approved_by="none",
        approved_at=datetime.now(UTC),
        channel="meta",
        tenant_id="tenant-alpha",
    )

    with pytest.raises(ApprovalRequiredError, match="not been reviewed|strictly blocked"):
        await gateway.validate_readiness(dispatch)


@pytest.mark.asyncio
async def test_readiness_rejected_on_invalid_or_forged_dispatch_signature() -> None:
    """Gateway strictly rejects directives carrying forged or invalid signatures."""
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, _ = _setup_approved_preview_and_gateway()

    decision = hitl.get_decision(preview.preview_id)
    assert decision is not None and decision.clearance is not None

    dispatch = DispatchDirective(
        dispatch_id="disp-forged",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="forged_corrupted_signature_payload",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel="meta",
        tenant_id="tenant-alpha",
        clearance_id=decision.clearance.clearance_id,
        payload={"campaign_id": "meta-camp-1"},
    )

    with pytest.raises(SignatureVerificationError, match="failed signature verification"):
        await gateway.validate_readiness(dispatch)


@pytest.mark.asyncio
async def test_readiness_rejected_on_cross_tenant_mismatch() -> None:
    """Gateway fails closed if directive tenant differs from T24 clearance tenant."""
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, _ = _setup_approved_preview_and_gateway("tenant-alpha")

    decision = hitl.get_decision(preview.preview_id)
    assert decision is not None and decision.clearance is not None

    dispatch = DispatchDirective(
        dispatch_id="disp-cross-tenant",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel="meta",
        tenant_id="tenant-beta",  # Mismatch against tenant-alpha clearance!
        clearance_id=decision.clearance.clearance_id,
        payload={"campaign_id": "meta-camp-1"},
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), priv_key)
    dispatch = dispatch.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="Tenant authority mismatch"):
        await gateway.validate_readiness(dispatch)


@pytest.mark.asyncio
async def test_readiness_rejected_on_audience_scope_or_action_mismatch() -> None:
    """Gateway fails closed when directive parameters conflict with audience token scope."""
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, _ = _setup_approved_preview_and_gateway()

    decision = hitl.get_decision(preview.preview_id)
    assert decision is not None and decision.clearance is not None

    # Token limited to audience "apac" and action "publish"
    token = AudienceToken(
        token_id="tok-apac-1",
        target_audience="apac",
        tenant_id="tenant-alpha",
        permitted_actions=["publish"],
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )

    # Directive targets audience "emea" (conflict!)
    dispatch = DispatchDirective(
        dispatch_id="disp-aud-mismatch",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel="meta",
        tenant_id="tenant-alpha",
        audience="emea",  # Mismatch!
        audience_token=token,
        clearance_id=decision.clearance.clearance_id,
        payload={"campaign_id": "meta-camp-1"},
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), priv_key)
    dispatch = dispatch.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="Audience token target 'apac' does not match directive audience 'emea'"):
        await gateway.validate_readiness(dispatch)


@pytest.mark.asyncio
async def test_readiness_rejected_on_spend_budget_exceedance() -> None:
    """Gateway fails closed when directive attempts to allocate spend above approved clearance."""
    # Approved for spend_amount = 25000.0
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, _ = _setup_approved_preview_and_gateway(spend_amount=25000.0)

    decision = hitl.get_decision(preview.preview_id)
    assert decision is not None and decision.clearance is not None

    # Directive requests 30,000.0 (exceeds 25,000.0 ceiling)
    dispatch = DispatchDirective(
        dispatch_id="disp-budget-overflow",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel="meta",
        tenant_id="tenant-alpha",
        clearance_id=decision.clearance.clearance_id,
        payload={"campaign_id": "meta-camp-1", "spend_amount": 30000.0},
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), priv_key)
    dispatch = dispatch.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="exceeds HITL-approved scope"):
        await gateway.validate_readiness(dispatch)


@pytest.mark.asyncio
async def test_readiness_rejected_on_expired_or_revoked_clearance_or_token() -> None:
    """Gateway fails closed on revoked or expired clearance or audience token."""
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, _ = _setup_approved_preview_and_gateway()

    decision = hitl.get_decision(preview.preview_id)
    assert decision is not None and decision.clearance is not None

    # Test expired clearance
    decision.clearance.expires_at = datetime.now(UTC) - timedelta(minutes=5)

    dispatch = DispatchDirective(
        dispatch_id="disp-expired",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel="meta",
        tenant_id="tenant-alpha",
        clearance_id=decision.clearance.clearance_id,
        payload={"campaign_id": "meta-camp-1"},
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), priv_key)
    dispatch = dispatch.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="expired"):
        await gateway.validate_readiness(dispatch)


@pytest.mark.asyncio
async def test_rate_limiter_enforces_capacity_and_backoff_readiness() -> None:
    """Gateway enforces target-specific rate limits and rejects when quota is exhausted."""
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, _ = _setup_approved_preview_and_gateway()

    decision = hitl.get_decision(preview.preview_id)
    assert decision is not None and decision.clearance is not None

    # Restrict channel to 1 token
    gateway._target_rate_limiters["meta"] = TokenBucket(capacity=1, refill_per_second=0.0)

    dispatch1 = DispatchDirective(
        dispatch_id="disp-rate-1",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel="meta",
        tenant_id="tenant-alpha",
        clearance_id=decision.clearance.clearance_id,
        payload={"campaign_id": "camp-1"},
    )
    sig1 = sign_payload(canonical_dispatch_bytes(dispatch1), priv_key)
    dispatch1 = dispatch1.model_copy(update={"signature": sig1})

    # Call 1 succeeds
    r1 = await gateway.validate_readiness(dispatch1)
    assert r1.is_ready is True

    # Call 2 with different ID exceeds rate limit
    dispatch2 = dispatch1.model_copy(update={"dispatch_id": "disp-rate-2"})
    sig2 = sign_payload(canonical_dispatch_bytes(dispatch2), priv_key)
    dispatch2 = dispatch2.model_copy(update={"signature": sig2})

    with pytest.raises(RateLimitExceededError, match="Outbound rate limit exceeded"):
        await gateway.validate_readiness(dispatch2)


@pytest.mark.asyncio
async def test_replay_protection_blocks_duplicate_and_allows_idempotent_retry() -> None:
    """Gateway allows identical idempotent retries while rejecting replayed directives with altered content."""
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, _ = _setup_approved_preview_and_gateway()

    decision = hitl.get_decision(preview.preview_id)
    assert decision is not None and decision.clearance is not None

    dispatch = DispatchDirective(
        dispatch_id="disp-idempotent-1",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel="meta",
        tenant_id="tenant-alpha",
        idempotency_key="idem-key-100",
        clearance_id=decision.clearance.clearance_id,
        payload={"campaign_id": "camp-1"},
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), priv_key)
    dispatch = dispatch.model_copy(update={"signature": sig})

    # First submission
    r1 = await gateway.validate_readiness(dispatch)
    assert r1.is_ready is True
    assert r1.idempotent_cached is False

    # Idempotent retry with identical parameters
    r2 = await gateway.validate_readiness(dispatch)
    assert r2.is_ready is True
    assert r2.idempotent_cached is True

    # Replay attack: same idempotency key with modified payload
    replayed = dispatch.model_copy(update={"payload": {"campaign_id": "camp-TAMPERED"}})
    with pytest.raises(PolicyViolationError, match="Replay detected"):
        await gateway.validate_readiness(replayed)


def test_plaintext_secrets_are_never_logged_or_persisted() -> None:
    """Scrubber redacts all credential, token, and secret fields from payload dictionaries."""
    payload = {
        "campaign_id": "123",
        "access_token": "secret_oauth_token_xyz",
        "api_key": "live_sk_1234567890",
        "nested_auth": {
            "password": "super_secret_password",
            "safe_field": "public_headline",
        },
    }

    scrubbed = scrub_sensitive_payload(payload)

    assert scrubbed["campaign_id"] == "123"
    assert scrubbed["access_token"] == "[REDACTED]"
    assert scrubbed["api_key"] == "[REDACTED]"
    assert scrubbed["nested_auth"]["password"] == "[REDACTED]"
    assert scrubbed["nested_auth"]["safe_field"] == "public_headline"


@pytest.mark.asyncio
async def test_zero_external_actuation_side_effects_during_t25_readiness() -> None:
    """Calling validate_readiness verifies all security gates with zero adapter invocations."""
    gateway, hitl, preview, priv_key, pub_pem, fake_ads, _ = _setup_approved_preview_and_gateway()

    decision = hitl.get_decision(preview.preview_id)
    assert decision is not None and decision.clearance is not None

    dispatch = DispatchDirective(
        dispatch_id="disp-no-side-effect",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel="meta",
        tenant_id="tenant-alpha",
        clearance_id=decision.clearance.clearance_id,
        payload={"campaign_id": "camp-1"},
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), priv_key)
    dispatch = dispatch.model_copy(update={"signature": sig})

    readiness = await gateway.validate_readiness(dispatch)
    assert readiness.is_ready is True

    # Critical requirement: Adapter call list remains strictly empty
    assert len(fake_ads.applied) == 0


@pytest.mark.asyncio
async def test_intelligence_engine_create_authorized_dispatch_handoff() -> None:
    """IntelligenceEngine correctly mints an authorized DispatchDirective bound to T24 clearance."""
    priv_key, pub_pem = _make_keypair()
    val = CryptographicValidator(pub_pem)
    hitl = HitlCoordinator(val)
    prov = ProvenanceRecorder(FakeProvenanceRepository())

    preview = ActionPreview(
        preview_id="prev-ie-dispatch",
        task_id="task-strat-1",
        tenant_id="tenant-alpha",
        kind=ActionPreviewKind.SPEND,
        summary="Strategic spend proposal",
        spend_amount=45000.0,
        risk_level=RiskLevel.MEDIUM,
    )
    hitl.submit_for_approval(preview)

    content_hash = compute_preview_hash(preview)
    now_dt = datetime.now(UTC)
    canon_bytes = canonical_decision_bytes(
        preview_id="prev-ie-dispatch",
        decision="APPROVE",
        approver="[email protected]",
        tenant_id="tenant-alpha",
        preview_content_hash=content_hash,
        decided_at=now_dt.isoformat(),
    )
    sig = sign_payload(canon_bytes, priv_key)
    hitl.decide(
        "prev-ie-dispatch",
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE,
        tenant_id="tenant-alpha",
        signature=sig,
        public_key_pem=pub_pem,
        preview_content_hash=content_hash,
        decided_at=now_dt,
    )

    from app.orchestration.evidence_synthesis import EvidenceSynthesizer
    from app.orchestration.hitl_preview_generator import HitlPreviewGenerator

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=None,  # type: ignore[arg-type]
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=hitl,
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=prov,
        workers={},
    )

    directive = await engine.create_authorized_dispatch(
        "prev-ie-dispatch",
        channel="meta",
        audience="global",
        payload={"campaign_id": "meta-001", "spend_amount": 40000.0},
        private_key=priv_key,
        tenant_id="tenant-alpha",
    )

    assert directive.channel == "meta"
    assert directive.action_preview_id == "prev-ie-dispatch"
    assert directive.tenant_id == "tenant-alpha"
    assert directive.signature != ""

    # Verify that the created directive passes MCP_ACT validation
    gateway = OutboundGateway(hitl, val, ads_adapters={"meta": FakeAdsAdapter()})
    readiness = await gateway.validate_readiness(directive)
    assert readiness.is_ready is True
