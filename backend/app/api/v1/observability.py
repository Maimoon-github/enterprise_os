from typing import Any

from app.api.deps import get_current_user
from app.core.config import settings
from app.schemas.common import ObservabilityStatsResponse, ObservabilityTraceResponse
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/traces", response_model=ObservabilityTraceResponse)
async def get_traces(current_user: dict[str, Any] = Depends(get_current_user)):
    return ObservabilityTraceResponse(
        exporter="OpenTelemetry -> Langfuse OTLP",
        langfuse_host=settings.LANGFUSE_HOST,
        openinference_conventions="enabled",
        total_spans_today=1240,
    )


@router.get("/stats", response_model=ObservabilityStatsResponse)
async def get_stats(current_user: dict[str, Any] = Depends(get_current_user)):
    return ObservabilityStatsResponse(
        trajectory_gate_pass_rate=0.98,
        brand_voice_rubric_avg=0.92,
        token_velocity_per_min=450,
    )
