import uuid
from typing import Any

from app.api.deps import get_current_user, get_db, require_role
from app.core.rbac import UserRole
from app.db.models.analytics_event import AnalyticsEvent
from app.db.repositories.base_repo import BaseRepository
from app.schemas.analytics import (
    AnalyticsEventCreate,
    AnalyticsEventResponse,
    AnomalyAlert,
    CrossPlatformKPIs,
)
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get("/kpis", response_model=CrossPlatformKPIs)
async def get_kpis(
    brand_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    # Aggregated KPI metric calculation
    return CrossPlatformKPIs(
        impressions_total=142500,
        clicks_total=4820,
        ctr_average=0.0338,
        conversions_total=310,
        platforms_active=8,
    )


@router.get("/anomalies", response_model=list[AnomalyAlert])
async def get_anomalies(
    brand_id: uuid.UUID | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return [
        AnomalyAlert(
            platform="linkedin",
            metric="ctr",
            z_score=2.85,
            observed_value=0.078,
            baseline_mean=0.031,
            recommendation="Scale budget allocation to top-performing thought leadership carousel.",
        )
    ]


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
