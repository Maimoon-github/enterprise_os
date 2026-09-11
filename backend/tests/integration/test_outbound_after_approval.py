"""Verifies external writes require signed HITL clearance."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.exceptions import (
    ApprovalRequiredError,
    ConfigurationError,
    SignatureVerificationError,
)
from app.integrations.ads.base import AdsAdapter
from app.mcp.outbound_gateway import OutboundGateway, TokenBucket, canonical_dispatch_bytes
from app.schemas.action_preview import ActionPreview, ActionPreviewKind
from app.schemas.dispatch import DispatchDirective
from app.schemas.governance import RiskLevel
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import HitlCoordinator


class FakeAdsAdapter(AdsAdapter):
    channel = "meta"

    def __init__(self) -> None:
        self.applied: list[dict[str, str]] = []

    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        self.applied.append(payload)
        return {"status_code": "200", "channel": self.channel}


def _preview() -> ActionPreview:
    return ActionPreview(
        preview_id="preview-1",
        task_id="task-1",
        kind=ActionPreviewKind.SPEND,
        summary="increase meta spend by $200",
        spend_amount=200.0,
        risk_level=RiskLevel.MEDIUM,
    )


def _dispatch(signature: str = "") -> DispatchDirective:
    return DispatchDirective(
        dispatch_id="dispatch-1",
        task_id="task-1",
        action_preview_id="preview-1",
        signature=signature,
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="meta",
        payload={"campaign_id": "123"},
    )


@pytest.mark.asyncio
async def test_dispatch_is_rejected_without_approval(ed25519_keypair) -> None:
    _, public_pem = ed25519_keypair
    gateway = OutboundGateway(
        HitlCoordinator(),
        CryptographicValidator(public_pem),
        ads_adapters={"meta": FakeAdsAdapter()},
    )

    with pytest.raises(ApprovalRequiredError):
        await gateway.execute(_dispatch())


@pytest.mark.asyncio
async def test_dispatch_is_rejected_with_invalid_signature(ed25519_keypair) -> None:
    _, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    hitl.submit_for_approval(_preview())
    hitl.decide("preview-1", approved=True, approver="[email protected]")
    gateway = OutboundGateway(
        hitl, CryptographicValidator(public_pem), ads_adapters={"meta": FakeAdsAdapter()}
    )

    with pytest.raises(SignatureVerificationError):
        await gateway.execute(_dispatch(signature="not-a-real-signature"))


@pytest.mark.asyncio
async def test_dispatch_succeeds_with_approval_and_valid_signature(ed25519_keypair) -> None:
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    hitl.submit_for_approval(_preview())
    hitl.decide("preview-1", approved=True, approver="[email protected]")

    dispatch = _dispatch()
    signature = sign_payload(canonical_dispatch_bytes(dispatch), private_key)
    dispatch = dispatch.model_copy(update={"signature": signature})

    fake_adapter = FakeAdsAdapter()
    gateway = OutboundGateway(
        hitl, CryptographicValidator(public_pem), ads_adapters={"meta": fake_adapter}
    )

    result = await gateway.execute(dispatch)

    assert result == {"status_code": "200", "channel": "meta"}
    assert fake_adapter.applied == [{"campaign_id": "123"}]


@pytest.mark.asyncio
async def test_dispatch_rejected_for_unregistered_channel(ed25519_keypair) -> None:
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    hitl.submit_for_approval(_preview())
    hitl.decide("preview-1", approved=True, approver="[email protected]")

    dispatch = _dispatch().model_copy(update={"channel": "unregistered"})
    signature = sign_payload(canonical_dispatch_bytes(dispatch), private_key)
    dispatch = dispatch.model_copy(update={"signature": signature})

    gateway = OutboundGateway(
        hitl, CryptographicValidator(public_pem), ads_adapters={"meta": FakeAdsAdapter()}
    )

    with pytest.raises(ConfigurationError):
        await gateway.execute(dispatch)


def test_token_bucket_enforces_capacity() -> None:
    bucket = TokenBucket(capacity=1, refill_per_second=0.0)

    assert bucket.allow() is True
    assert bucket.allow() is False