"""Receives webhook, conversion, pixel, event, and error telemetry with raw-byte verification."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Request, status

from app.core.exceptions import (
    AuthorizationError,
    PolicyViolationError,
    RepositoryError,
    SignatureVerificationError,
)
from app.schemas.telemetry import (
    BatchTelemetryIngestRequest,
    BatchTelemetryIngestResponse,
    OmnichannelTelemetryReadiness,
    RecordKind,
    TelemetryHandshakeProbe,
    TelemetryReceipt,
    TrustClass,
    WebhookIngestEnvelope,
)
from app.security.cryptographic_validator import verify_raw_webhook_signature

router = APIRouter()


@router.get("/readiness", response_model=OmnichannelTelemetryReadiness)
async def get_readiness(tenant_id: str, request: Request) -> OmnichannelTelemetryReadiness:
    """Return latest omnichannel telemetry connection readiness for a tenant."""
    engine = getattr(request.app.state, "telemetry_engine", None)
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Omnichannel Telemetry Engine is not initialized.",
        )
    readiness = engine.get_readiness(tenant_id)
    if not readiness:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No telemetry readiness record found for tenant '{tenant_id}'.",
        )
    return readiness


@router.post("/probe", response_model=list[TelemetryHandshakeProbe])
async def run_probes(tenant_id: str, request: Request) -> list[TelemetryHandshakeProbe]:
    """Execute non-destructive synthetic probes across active listeners."""
    engine = getattr(request.app.state, "telemetry_engine", None)
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Omnichannel Telemetry Engine is not initialized.",
        )
    readiness = engine.get_readiness(tenant_id)
    if not readiness:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active surfaces registered for tenant '{tenant_id}'.",
        )
    return await engine.probe_all_listeners(readiness.active_surfaces)


async def _admit_envelope(
    envelope: WebhookIngestEnvelope,
    request: Request,
    trust_class: TrustClass,
    raw_body: bytes | None = None,
    signature: str | None = None,
) -> TelemetryReceipt:

    """Durably admit a validated envelope through DataGateway or TelemetryService."""
    logical_event_id = envelope.idempotency_key or hashlib.sha256(
        f"{envelope.tenant_id}:{envelope.channel}:{envelope.event_type}:{envelope.occurred_at.isoformat()}:{json.dumps(envelope.metrics, sort_keys=True)}".encode()
    ).hexdigest()

    # Release stamping: extract deployed release ID if available from CMS client
    release_ref = None
    cms_client = getattr(request.app.state, "cms_client", None)
    if cms_client and hasattr(cms_client, "get_current_release"):
        rel_info = cms_client.get_current_release(envelope.tenant_id)
        if rel_info:
            release_ref = rel_info.get("release_id")

    # Authoritative order enforcement: browser purchases remain browser_untrusted
    is_authoritative = (
        False
        if trust_class == TrustClass.BROWSER_UNTRUSTED
        else True
    )

    clean_payload = dict(envelope.payload)
    clean_payload["is_authoritative_order"] = is_authoritative

    record_dict: dict[str, Any] = {
        "tenant_id": envelope.tenant_id,
        "brand_id": envelope.tenant_id,
        "source_id": envelope.source_id or envelope.account_id or envelope.channel,
        "source_account_id": envelope.account_id or envelope.channel,
        "channel": envelope.channel,
        "logical_event_id": logical_event_id,
        "record_kind": RecordKind.EVENT.value,
        "trust_class": trust_class.value,
        "occurred_at": envelope.occurred_at.isoformat(),
        "payload": {
            "occurrence_type": envelope.event_type.value,
            "logical_event_id": logical_event_id,
            "metrics": envelope.metrics,
            "properties": clean_payload,
            "is_authoritative_order": is_authoritative,
        },
        "references": {"release_id": release_ref} if release_ref else {},
    }

    # Attempt admission via TelemetryNormalizer / TelemetryService / DataGateway
    service = getattr(request.app.state, "telemetry_normalizer", None)
    if not service:
        service = getattr(request.app.state, "telemetry_service", None)

    gateway = getattr(request.app.state, "data_gateway", None)
    repo = getattr(request.app.state, "telemetry_repository", None)

    try:
        if service and hasattr(service, "admit"):
            receipt = await service.admit(record_dict)
        elif gateway and hasattr(gateway, "admit"):
            from app.schemas.governance import RiskLevel, TenantScope
            from app.security.authorization_boundary import CallerIdentity

            caller = CallerIdentity(
                subject="telemetry_ingress",
                tenant_scope=TenantScope(tenant_id=envelope.tenant_id),
                risk_ceiling=RiskLevel.LOW,
                allowed_capabilities=frozenset({"telemetry.ingest", "mcp_data_write"}),
            )
            receipt = await gateway.admit(caller, tenant_id=envelope.tenant_id, record=record_dict)
        elif repo and hasattr(repo, "admit"):
            receipt = await repo.admit(record_dict)
        else:
            engine = getattr(request.app.state, "telemetry_engine", None)
            if engine and getattr(engine, "_telemetry_repository", None):
                receipt = await engine._telemetry_repository.admit(record_dict)
            elif engine:
                # Standalone engine listener validation
                engine.validate_ingress(envelope, raw_body=raw_body, signature=signature)
                receipt = TelemetryReceipt(

                    receipt_id=f"rcpt_{logical_event_id[:16]}",
                    tenant_id=envelope.tenant_id,
                    source_id=envelope.source_id or envelope.account_id or envelope.channel,
                    source_account_id=envelope.account_id or envelope.channel,
                    logical_event_id=logical_event_id,
                    content_hash=hashlib.sha256(json.dumps(envelope.metrics, sort_keys=True).encode()).hexdigest(),
                    status="accepted",
                    channel=envelope.channel,
                    minimized_payload={"metrics": envelope.metrics, "properties": clean_payload},
                )
            else:
                # Production telemetry must NEVER fabricate simulated success
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Telemetry persistence is not configured; simulated ingress forbidden.",
                )

        if hasattr(receipt, "channel"):
            receipt.channel = envelope.channel
        return receipt


    except (RepositoryError, PolicyViolationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Telemetry admission failure: {exc}",
        ) from exc


async def _process_ingress(
    request: Request,
    *,
    expected_channel: str | None = None,
    trust_class: TrustClass = TrustClass.SERVER_VERIFIED,
    require_signature: bool = True,
) -> TelemetryReceipt:
    """Verify raw request bytes before JSON/schema parsing, then admit envelope."""
    raw_bytes = await request.body()
    engine = getattr(request.app.state, "telemetry_engine", None)
    headers = dict(request.headers)

    # 1. Cryptographic raw-byte verification BEFORE parsing JSON
    secret = None
    if engine and hasattr(engine, "_webhook_signing_secret"):
        secret = engine._webhook_signing_secret

    if require_signature:
        channel_name = expected_channel or "generic"
        if secret:
            is_valid = verify_raw_webhook_signature(
                channel_name, raw_bytes, headers, secret
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or missing webhook signature over raw request bytes.",
                )

    # 2. Parse and validate JSON only after raw bytes are verified
    try:
        body_dict = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else {}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON in request payload.",
        ) from exc

    try:
        envelope = WebhookIngestEnvelope.model_validate(body_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Schema validation failed: {exc}",
        ) from exc

    # 3. Channel binding enforcement
    if expected_channel:
        if envelope.channel != expected_channel:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Channel mismatch: route is '{expected_channel}', payload claims '{envelope.channel}'.",
            )
        envelope.channel = expected_channel

    # 4. Surface authorization allowlist and readiness check
    sig = headers.get("x-hub-signature-256") or headers.get("x-signature") or headers.get("tiktok-signature")
    if sig and not envelope.signature:
        envelope.signature = sig

    if engine:
        surface_key = (envelope.tenant_id, envelope.channel)
        active_list = engine._active_surfaces.get(surface_key)
        if not active_list:
            known = [ch for (tid, ch) in engine._active_surfaces if tid == envelope.tenant_id]
            if known:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Channel '{envelope.channel}' is not an authorized active surface for tenant '{envelope.tenant_id}'.",
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant '{envelope.tenant_id}' has no registered active telemetry surfaces.",
            )

    return await _admit_envelope(
        envelope, request, trust_class=trust_class, raw_body=raw_bytes, signature=sig
    )



@router.post("/pixel", response_model=TelemetryReceipt, status_code=status.HTTP_202_ACCEPTED)
async def receive_pixel(request: Request) -> TelemetryReceipt:
    """Storefront pixel endpoint for unauthenticated website pageviews and client traffic."""
    return await _process_ingress(
        request,
        expected_channel="website",
        trust_class=TrustClass.BROWSER_UNTRUSTED,
        require_signature=False,
    )


@router.post("/conversions", response_model=TelemetryReceipt, status_code=status.HTTP_202_ACCEPTED)
async def receive_conversions(
    request: Request,
    x_signature: str | None = Header(None, alias="X-Signature"),
) -> TelemetryReceipt:
    """Storefront checkout and conversion callback endpoint."""
    # If signed, verified server intake; otherwise browser_untrusted
    trust = TrustClass.SERVER_VERIFIED if x_signature else TrustClass.BROWSER_UNTRUSTED
    return await _process_ingress(
        request,
        expected_channel="website",
        trust_class=trust,
        require_signature=bool(x_signature),
    )


@router.post("/errors", response_model=TelemetryReceipt, status_code=status.HTTP_202_ACCEPTED)
async def receive_errors(request: Request) -> TelemetryReceipt:
    """Storefront and application error-log collector endpoint."""
    return await _process_ingress(
        request,
        expected_channel="website",
        trust_class=TrustClass.BROWSER_UNTRUSTED,
        require_signature=False,
    )


@router.post(
    "/webhooks/ads/{channel}",
    response_model=TelemetryReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_ad_webhook(channel: str, request: Request) -> TelemetryReceipt:
    """Authenticated webhook listener for paid-media ad platforms."""
    return await _process_ingress(
        request,
        expected_channel=channel,
        trust_class=TrustClass.PROVIDER_VERIFIED,
        require_signature=True,
    )


@router.post(
    "/webhooks/social/{channel}",
    response_model=TelemetryReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_social_webhook(channel: str, request: Request) -> TelemetryReceipt:
    """Authenticated webhook listener for organic social channels."""
    return await _process_ingress(
        request,
        expected_channel=channel,
        trust_class=TrustClass.PROVIDER_VERIFIED,
        require_signature=True,
    )


@router.post(
    "/batch",
    response_model=BatchTelemetryIngestResponse,
    status_code=status.HTTP_200_OK,
)
async def receive_batch(
    payload: BatchTelemetryIngestRequest,
    request: Request,
) -> BatchTelemetryIngestResponse:
    """Batch ingestion endpoint supporting item-level partial failure handling."""
    engine = getattr(request.app.state, "telemetry_engine", None)
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Omnichannel Telemetry Engine is not initialized.",
        )
    return await engine.ingest_batch(payload.tenant_id, payload.events)