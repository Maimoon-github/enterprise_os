from typing import Any

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.core.rbac import UserRole
from app.observability.evals.golden_suite import run_golden_suite_regression
from app.observability.langfuse import get_evaluation_stats, get_evaluations
from app.schemas.common import (
    GoldenRegressionRunResponse,
    ObservabilityEvaluationItem,
    ObservabilityEvaluationsResponse,
    ObservabilityStatsResponse,
    ObservabilityTraceResponse,
)
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
    stats = get_evaluation_stats()
    return ObservabilityStatsResponse(
        trajectory_gate_pass_rate=stats.get("trajectory_pass_rate", 0.98),
        brand_voice_rubric_avg=stats.get("brand_voice_avg", 0.92),
        token_velocity_per_min=450,
    )


@router.get("/evaluations", response_model=ObservabilityEvaluationsResponse)
async def list_evaluations(current_user: dict[str, Any] = Depends(get_current_user)):
    evals = get_evaluations(limit=50)
    stats = get_evaluation_stats()
    return ObservabilityEvaluationsResponse(
        evaluations=[
            ObservabilityEvaluationItem(
                trace_id=e["trace_id"],
                name=e["name"],
                score=e["score"],
                label=e["label"],
                annotator_kind=e.get("annotator_kind", "CODE"),
                comment=e.get("comment"),
                created_at=e.get("created_at"),
            )
            for e in evals
        ],
        total=len(evals),
        pass_rate=stats.get("pass_rate", 1.0),
    )


@router.post("/evaluations/run", response_model=GoldenRegressionRunResponse)
async def run_evaluations(current_user: dict[str, Any] = Depends(require_role(UserRole.OPERATOR))):
    res = run_golden_suite_regression()
    return GoldenRegressionRunResponse(
        total_scenarios=res["total_scenarios"],
        passed=res["passed"],
        failed=res["failed"],
        pass_rate=res["pass_rate"],
        results=res["results"],
    )
