from fastapi import APIRouter

router = APIRouter()

@router.get("")
async def list_schedules():
    return [
        {
            "id": "sched_01",
            "name": "Daily Cross-Platform Metrics Ingestion",
            "cron": "0 */6 * * *",
            "queue": "analytics_queue",
            "status": "active",
        },
        {
            "id": "sched_02",
            "name": "Midnight Brand Voice Audit",
            "cron": "0 0 * * *",
            "queue": "orchestrator_queue",
            "status": "active",
        },
    ]
