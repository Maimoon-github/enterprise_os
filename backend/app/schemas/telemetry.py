"""Normalized traffic, conversion, ad, social, and ROAS event contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, Union
import uuid

from pydantic import BaseModel, Field


class TelemetryEventType(StrEnum):
    """The normalized categories of omnichannel performance events."""

    TRAFFIC = "traffic"
    CONVERSION = "conversion"
    CHECKOUT = "checkout"
    TRANSACTION = "transaction"
    AD_SPEND = "ad_spend"
    SOCIAL_ENGAGEMENT = "social_engagement"
    ROAS = "roas"
    ERROR = "error"


class TelemetrySourceType(StrEnum):
    """The supported transport / connector listener types."""

    WEBHOOK = "webhook"
    PIXEL = "pixel"
    CONVERSION = "conversion"
    EVENT_STREAM = "event_stream"
    ERROR_LOG = "error_log"


class RecordKind(StrEnum):
    """Discriminated kinds of telemetry records."""

    EVENT = "event"
    METRIC_SNAPSHOT = "metric_snapshot"
    OPERATIONAL_ERROR = "operational_error"


class TrustClass(StrEnum):
    """Origin trust classification for admitted telemetry."""

    BROWSER_UNTRUSTED = "browser_untrusted"
    SERVER_VERIFIED = "server_verified"
    PROVIDER_VERIFIED = "provider_verified"


class AggregationSemantics(StrEnum):
    """Aggregation behavior for metric snapshots."""

    PERIOD_TOTAL = "period_total"
    LIFETIME_COUNTER = "lifetime_counter"
    RATIO = "ratio"
    GAUGE = "gauge"


class MonetaryAmount(BaseModel):
    """Exact decimal monetary value with declared minor units and scale."""

    amount: Decimal = Field(default=Decimal("0.00"))
    currency: str = "USD"
    minor_units: int | None = None
    scale: int = 2

    def model_post_init(self, __context: Any) -> None:
        if self.minor_units is None:
            multiplier = Decimal(10**self.scale)
            self.minor_units = int((self.amount * multiplier).to_integral_value())
        elif self.amount == Decimal("0.00") and self.minor_units != 0:
            divisor = Decimal(10**self.scale)
            self.amount = Decimal(self.minor_units) / divisor


class TelemetryQuality(BaseModel):
    """Completeness, freshness, and quality indicators."""

    completeness: str = "complete"  # complete, partial, suppressed, missing
    freshness_seconds: float | None = None
    sampling_rate: float = 1.0
    is_correction: bool = False
    clock_skew_seconds: float = 0.0
    missing_fields: list[str] = Field(default_factory=list)


class TelemetryPrivacy(BaseModel):
    """Privacy and policy metadata."""

    collection_purpose: str = "operational_telemetry"
    policy_reference: str | None = None
    consent_reference: str | None = None
    retention_class: str = "standard"


class TelemetryProvenance(BaseModel):
    """Lineage metadata linking admitted telemetry to sources and build versions."""

    source_request_id: str | None = None
    source_response_id: str | None = None
    collector_build: str = "v1.0"
    schema_version: str = "1.0"
    mapping_version: str = "1.0"
    policy_version: str = "1.0"
    evidence_hash: str | None = None


class TelemetryEventPayload(BaseModel):
    """Payload for discrete occurrence events."""

    occurrence_type: str
    logical_event_id: str | None = None
    transaction_status: str | None = None
    quantity: Decimal | int | None = None
    monetary_amount: MonetaryAmount | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class MetricSnapshotPayload(BaseModel):
    """Payload for time-windowed aggregated observations."""

    entity_id: str
    metric_name: str
    value: Decimal
    unit: str
    aggregation_semantics: AggregationSemantics = AggregationSemantics.GAUGE
    currency: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    boundary_convention: str = "closed_open"
    granularity: str = "1d"
    account_timezone: str = "UTC"
    source_api_version: str = "v1"
    attribution_settings: dict[str, Any] = Field(default_factory=dict)
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))
    report_run_id: str | None = None
    revision: int = 1


class OperationalErrorPayload(BaseModel):
    """Payload for surface and pipeline errors."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    service_reference: str
    surface_reference: str | None = None
    release_reference: str | None = None
    severity: str = "error"
    error_code: str
    sanitized_message: str
    trace_reference: str | None = None


class TelemetryEnvelope(BaseModel):
    """Versioned common envelope for all admitted Layer-8 signals."""

    schema_version: str = "1.0"
    record_kind: RecordKind
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    receipt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    brand_id: str
    source_id: str
    source_account_id: str
    source_event_id: str | None = None
    source_revision: str = "1"
    occurred_at: datetime | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dimensions: dict[str, str] = Field(default_factory=dict)
    references: dict[str, str] = Field(default_factory=dict)
    trust_class: TrustClass = TrustClass.SERVER_VERIFIED
    quality: TelemetryQuality = Field(default_factory=TelemetryQuality)
    privacy: TelemetryPrivacy = Field(default_factory=TelemetryPrivacy)
    provenance: TelemetryProvenance = Field(default_factory=TelemetryProvenance)


class TelemetryEventRecord(TelemetryEnvelope):
    """Discriminated event record."""

    record_kind: Literal[RecordKind.EVENT] = RecordKind.EVENT
    payload: TelemetryEventPayload


class MetricSnapshotRecord(TelemetryEnvelope):
    """Discriminated metric snapshot record."""

    record_kind: Literal[RecordKind.METRIC_SNAPSHOT] = RecordKind.METRIC_SNAPSHOT
    payload: MetricSnapshotPayload


class OperationalErrorRecord(TelemetryEnvelope):
    """Discriminated operational error record."""

    record_kind: Literal[RecordKind.OPERATIONAL_ERROR] = RecordKind.OPERATIONAL_ERROR
    payload: OperationalErrorPayload


TelemetryRecord = Annotated[
    Union[TelemetryEventRecord, MetricSnapshotRecord, OperationalErrorRecord],
    Field(discriminator="record_kind"),
]


class TelemetryReceipt(BaseModel):
    """Immutable proof of durable admission."""

    receipt_id: str
    tenant_id: str
    source_id: str
    source_account_id: str
    logical_event_id: str
    source_revision: str = "1"
    content_hash: str
    status: str = "accepted"  # accepted, duplicate, quarantined
    channel: str | None = None
    minimized_payload: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "1.0"
    policy_version: str = "1.0"
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TelemetryWorkItem(BaseModel):
    """Durable unit of intake processing with lease fencing."""

    work_item_id: str
    receipt_id: str
    tenant_id: str
    status: str = "pending"  # pending, leased, retry, quarantined, done
    attempt_count: int = 0
    max_attempts: int = 5
    next_retry_at: datetime | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    lease_generation: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TelemetryCollectionRun(BaseModel):
    """Durable checkpoint and revision tracking for polling and collection jobs."""

    run_id: str
    tenant_id: str
    source_id: str
    query_fingerprint: str
    target_window_start: datetime
    target_window_end: datetime
    total_pages: int = 0
    completed_pages: int = 0
    coverage_ratio: float = 0.0
    generation: int = 1
    status: str = "running"  # running, completed, failed, partial
    published_revision: int | None = None
    document: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TelemetrySourceManifest(BaseModel):
    """Non-secret configuration manifest for an authorized telemetry source."""

    source_id: str
    tenant_id: str
    brand_id: str
    external_account_id: str
    channel: str
    source_type: str
    enabled: bool = True
    allowed_operations: list[str] = Field(default_factory=lambda: ["report_read", "admit"])
    api_version: str = "v1"
    secret_reference: str | None = None
    polling_cadence_seconds: int = 3600
    freshness_threshold_seconds: int = 7200
    rate_limit_per_minute: int = 60
    config: dict[str, Any] = Field(default_factory=dict)


class TelemetrySurface(BaseModel):
    """An active omnichannel telemetry listening surface attached to a deployed channel."""

    channel: str
    source_type: TelemetrySourceType
    endpoint: str
    tenant_id: str
    account_id: str | None = None
    event_classes: list[TelemetryEventType] = Field(default_factory=list)
    is_active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class TelemetryHandshakeProbe(BaseModel):
    """Result of a non-destructive handshake/synthetic connection validation probe."""

    channel: str
    source_type: TelemetrySourceType
    success: bool
    latency_ms: float = 0.0
    status: str = "ok"
    details: dict[str, Any] = Field(default_factory=dict)
    probed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OmnichannelTelemetryReadiness(BaseModel):
    """Authoritative readiness ledger documenting connected telemetry listeners."""

    readiness_id: str
    tenant_id: str
    is_ready: bool
    dependencies: dict[str, str] = Field(default_factory=dict)
    active_surfaces: list[TelemetrySurface] = Field(default_factory=list)
    probes: list[TelemetryHandshakeProbe] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    connected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WebhookIngestEnvelope(BaseModel):
    """Inbound transport-level telemetry event envelope."""

    tenant_id: str
    channel: str
    event_type: TelemetryEventType
    occurred_at: datetime
    account_id: str | None = None
    source_id: str | None = None
    correlation_id: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: str | None = None
    idempotency_key: str | None = None


class TelemetryEvent(BaseModel):
    """A single normalized telemetry event ready for persistence and learning."""

    event_id: str
    tenant_id: str
    event_type: TelemetryEventType
    channel: str
    occurred_at: datetime
    metrics: dict[str, float] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_id: str | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    dimensions: dict[str, str] = Field(default_factory=dict)


class BatchItemResult(BaseModel):
    """Result of an individual item within a batch ingestion request."""

    index: int
    success: bool
    event_id: str | None = None
    idempotency_key: str | None = None
    error: str | None = None


class BatchTelemetryIngestRequest(BaseModel):
    """Batch ingestion request containing multiple telemetry event envelopes."""

    tenant_id: str
    events: list[WebhookIngestEnvelope] = Field(default_factory=list)


class BatchTelemetryIngestResponse(BaseModel):
    """Response ledger for a batch ingestion request supporting partial failures."""

    tenant_id: str
    total_received: int
    total_succeeded: int
    total_failed: int
    results: list[BatchItemResult] = Field(default_factory=list)