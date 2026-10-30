from app.api.v1 import (
    agents,
    analytics,
    approvals,
    auth,
    brands,
    campaigns,
    mcp_servers,
    media,
    observability,
    runs,
    schedules,
    settings,
    skills,
    users,
)
from fastapi import APIRouter

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
api_v1_router.include_router(brands.router, prefix="/brands", tags=["Brands"])
api_v1_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
api_v1_router.include_router(runs.router, prefix="/runs", tags=["Runs"])
api_v1_router.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])
api_v1_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
api_v1_router.include_router(skills.router, prefix="/skills", tags=["Skills"])
api_v1_router.include_router(mcp_servers.router, prefix="/mcp-servers", tags=["MCP Servers"])
api_v1_router.include_router(media.router, prefix="/media", tags=["Media"])
api_v1_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_v1_router.include_router(schedules.router, prefix="/schedules", tags=["Schedules"])
api_v1_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_v1_router.include_router(observability.router, prefix="/observability", tags=["Observability"])
