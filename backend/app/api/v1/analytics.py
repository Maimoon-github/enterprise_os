from fastapi import APIRouter

router = APIRouter()

@router.get("/kpis")
async def get_kpis():
    return {
        "impressions_total": 142500,
        "clicks_total": 4820,
        "ctr_average": 0.0338,
        "conversions_total": 310,
        "platforms_active": 8,
    }

@router.get("/anomalies")
async def get_anomalies():
    return []
