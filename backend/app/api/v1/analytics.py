import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.rbac import UserRole
from app.db.models.analytics_event import AnalyticsEvent
from app.db.repositories.base_repo import BaseRepository
from app.db.repositories.platform_connection_repo import PlatformConnectionRepository
from app.schemas.analytics import (
    AnalyticsEventCreate,
    AnalyticsEventResponse,
    AnomalyAlert,
    CrossPlatformKPIs,
)
from app.schemas.settings import AnalyticsChannelState
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

SUPPORTED_PLATFORMS = [
    "linkedin",
    "x",
    "youtube",
    "instagram",
    "threads",
    "facebook",
    "pinterest",
    "google_business_profile",
]


@router.get("/kpis", response_model=CrossPlatformKPIs)
async def get_kpis(
    brand_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Calculate aggregated cross-platform KPIs dynamically from actual database records.

    Returns zero-state when no events have been ingested (no demo/mock data).
    """
    query = select(AnalyticsEvent)
    if brand_id:
        query = query.where(AnalyticsEvent.brand_id == brand_id)
    res = await db.execute(query)
    events = list(res.scalars().all())

    if not events:
        return CrossPlatformKPIs(
            impressions_total=0,
            clicks_total=0,
            ctr_average=0.0,
            conversions_total=0,
            platforms_active=0,
        )

    impressions = 0
    clicks = 0
    conversions = 0
    active_platforms: set[str] = set()

    for ev in events:
        active_platforms.add(ev.platform)
        if ev.metric_type == "impressions":
            impressions += int(ev.metric_value)
        elif ev.metric_type == "clicks":
            clicks += int(ev.metric_value)
        elif ev.metric_type in ("conversions", "leads", "sales"):
            conversions += int(ev.metric_value)

    ctr = (clicks / impressions) if impressions > 0 else 0.0

    return CrossPlatformKPIs(
        impressions_total=impressions,
        clicks_total=clicks,
        ctr_average=round(ctr, 4),
        conversions_total=conversions,
        platforms_active=len(active_platforms),
    )


@router.get("/anomalies", response_model=list[AnomalyAlert])
async def get_anomalies(
    brand_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Retrieve statistical anomalies from recorded analytics events.

    Returns empty list when baseline sample size is insufficient or no variance exists.
    """
    query = select(AnalyticsEvent)
    if brand_id:
        query = query.where(AnalyticsEvent.brand_id == brand_id)
    res = await db.execute(query)
    events = list(res.scalars().all())

    # Only report anomalies if substantial real data exists (e.g. z-score calculation)
    # Never return fabricated anomaly fixtures
    if len(events) < 10:
        return []

    # Calculate actual z-score anomalies if present
    import numpy as np

    values = [e.metric_value for e in events]
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0:
        return []

    alerts: list[AnomalyAlert] = []
    for e in events:
        z = (e.metric_value - mean) / std
        if abs(z) >= 2.5:
            alerts.append(
                AnomalyAlert(
                    platform=e.platform,
                    metric=e.metric_type,
                    z_score=round(float(z), 2),
                    observed_value=float(e.metric_value),
                    baseline_mean=round(mean, 2),
                    recommendation=f"Statistical outlier detected on {e.platform} ({e.metric_type}): investigate performance spike or drop.",
                )
            )
    return alerts[:5]


@router.get("/channels", response_model=list[AnalyticsChannelState])
async def get_analytics_channels(
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Provide visibility into connection status and real analytics event counts across all 8 platforms."""
    conn_repo = PlatformConnectionRepository(db)
    conns = {c.platform: c for c in await conn_repo.list_connections()}

    # Group counts from AnalyticsEvent
    count_query = select(
        AnalyticsEvent.platform,
        func.count(AnalyticsEvent.id).label("cnt"),
    ).group_by(AnalyticsEvent.platform)
    counts_res = await db.execute(count_query)
    platform_counts = {row[0]: row[1] for row in counts_res.all()}

    channel_states: list[AnalyticsChannelState] = []
    for platform in SUPPORTED_PLATFORMS:
        conn = conns.get(platform)
        is_conn = bool(conn and conn.is_connected)
        ev_count = platform_counts.get(platform, 0)
        channel_states.append(
            AnalyticsChannelState(
                platform=platform,
                is_connected=is_conn,
                events_count=ev_count,
                impressions=0,
                clicks=0,
                last_synced_at=conn.last_synced_at if conn else None,
            )
        )
    return channel_states


@router.get("/events", response_model=list[AnalyticsEventResponse])
async def list_analytics_events(
    brand_id: uuid.UUID | None = None,
    platform: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    query = select(AnalyticsEvent)
    if brand_id:
        query = query.where(AnalyticsEvent.brand_id == brand_id)
    if platform:
        query = query.where(AnalyticsEvent.platform == platform)
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/events", response_model=AnalyticsEventResponse, status_code=status.HTTP_201_CREATED)
async def record_analytics_event(
    payload: AnalyticsEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(require_role(UserRole.OPERATOR)),
):
    repo = BaseRepository(AnalyticsEvent, db)
    event = await repo.create(
        brand_id=payload.brand_id,
        platform=payload.platform,
        external_post_id=payload.external_post_id,
        metric_type=payload.metric_type,
        metric_value=payload.metric_value,
        recorded_at=payload.recorded_at,
    )
    return event
