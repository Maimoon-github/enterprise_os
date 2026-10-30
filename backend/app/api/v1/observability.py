from fastapi import APIRouter

router = APIRouter()

@router.get("/traces")
async def get_traces():
    return {
        "exporter": "OpenTelemetry -> Langfuse OTLP",
        "langfuse_host": "http://localhost:3001",
        "openinference_conventions": "enabled",
        "total_spans_today": 1240,
    }

@router.get("/stats")
async def get_stats():
    return {
        "trajectory_gate_pass_rate": 0.98,
        "brand_voice_rubric_avg": 0.92,
        "token_velocity_per_min": 450,
    }
