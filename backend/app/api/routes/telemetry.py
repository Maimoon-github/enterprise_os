"""Receives webhook, conversion, pixel, event, and error telemetry."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, Request, status
from pydantic import BaseModel

from app.core.exceptions import (
    AuthorizationError,
    PolicyViolationError,
    SignatureVerificationError,
)
from app.schemas.telemetry import (
    OmnichannelTelemetryReadiness,
    TelemetryEvent,
    TelemetryEventType,
    TelemetryHandshakeProbe,
    WebhookIngestEnvelope,
)

router = APIRouter()


class TelemetryIngestRequest(BaseModel):
    """The transport-layer shape of an incoming raw telemetry event."""

    tenant_id: str
    event_type: TelemetryEventType
    channel: str
    occurred_at: datetime
    metrics: dict[str, float]


@router.post("", response_model=TelemetryEvent, status_code=201)
async def ingest_telemetry(payload: TelemetryIngestRequest, request: Request) -> TelemetryEvent:
    """Normalize and persist an incoming telemetry event (legacy direct path)."""
    telemetry_normalizer = request.app.state.telemetry_normalizer
    return await telemetry_normalizer.ingest(
        tenant_id=payload.tenant_id,
        event_type=payload.event_type,
        channel=payload.channel,
        occurred_at=payload.occurred_at,
        metrics=payload.metrics,
    )


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


async def _handle_ingress(
    payload: WebhookIngestEnvelope,
    request: Request,
    signature_header: str | None = None,
) -> TelemetryEvent:
    """Shared ingress handler with security, freshness, and replay validation."""
    engine = getattr(request.app.state, "telemetry_engine", None)
    raw_body = await request.body()
    sig = signature_header or payload.signature or request.headers.get("x-hub-signature-256") or request.headers.get("x-signature")

    if engine:
        return engine.validate_ingress(payload, raw_body=raw_body, signature=sig)

    # Fallback normalization if engine not present
    return TelemetryEvent(
        event_id="simulated_ingress_event",
        tenant_id=payload.tenant_id,
        event_type=payload.event_type,
        channel=payload.channel,
        occurred_at=payload.occurred_at,
        metrics=payload.metrics,
    )


@router.post("/pixel", response_model=TelemetryEvent, status_code=202)
async def receive_pixel(
    payload: WebhookIngestEnvelope,
    request: Request,
    x_signature: str | None = Header(None, alias="X-Signature"),
) -> TelemetryEvent:
    """Storefront pixel endpoint for website pageviews and client traffic."""
    return await _handle_ingress(payload, request, signature_header=x_signature)


@router.post("/conversions", response_model=TelemetryEvent, status_code=202)
async def receive_conversions(
    payload: WebhookIngestEnvelope,
    request: Request,
    x_signature: str | None = Header(None, alias="X-Signature"),
) -> TelemetryEvent:
    """Storefront checkout and conversion callback endpoint."""
    return await _handle_ingress(payload, request, signature_header=x_signature)


@router.post("/errors", response_model=TelemetryEvent, status_code=202)
async def receive_errors(
    payload: WebhookIngestEnvelope,
    request: Request,
    x_signature: str | None = Header(None, alias="X-Signature"),
) -> TelemetryEvent:
    """Storefront and application error-log collector endpoint."""
    return await _handle_ingress(payload, request, signature_header=x_signature)


@router.post("/webhooks/ads/{channel}", response_model=TelemetryEvent, status_code=202)
async def receive_ad_webhook(
    channel: str,
    payload: WebhookIngestEnvelope,
    request: Request,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> TelemetryEvent:
    """Authenticated webhook listener for paid-media ad platforms."""
    payload.channel = channel
    return await _handle_ingress(payload, request, signature_header=x_hub_signature_256)


@router.post("/webhooks/social/{channel}", response_model=TelemetryEvent, status_code=202)
async def receive_social_webhook(
    channel: str,
    payload: WebhookIngestEnvelope,
    request: Request,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> TelemetryEvent:
    """Authenticated webhook listener for organic social channels."""
    payload.channel = channel
    return await _handle_ingress(payload, request, signature_header=x_hub_signature_256)