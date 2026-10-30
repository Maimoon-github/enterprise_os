from typing import Any

from app.api.deps import get_current_user, require_role
from app.core.rbac import UserRole
from app.schemas.mcp import MCPServerStatus, MCPSyncResponse
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("", response_model=list[MCPServerStatus])
async def list_mcp_servers(current_user: dict[str, Any] = Depends(get_current_user)):
    return [
        MCPServerStatus(
            name="brand_rag_server",
            transport="Streamable HTTP",
            endpoint="http://localhost:8081",
            tools=["search_brand_docs", "query_tone_rubric"],
            resources=["brand://guidelines", "brand://personas"],
            capabilities=["resources", "tools"],
            connected=True,
        ),
        MCPServerStatus(
            name="social_gateway_server",
            transport="Streamable HTTP",
            endpoint="http://localhost:8082",
            tools=["publish_post", "check_rate_limits"],
            resources=["social://profiles"],
            capabilities=["tools", "notifications"],
            connected=True,
        ),
        MCPServerStatus(
            name="media_studio_server",
            transport="Streamable HTTP",
            endpoint="http://localhost:8083",
            tools=["generate_visual", "extract_keyframes", "transcode_video"],
            resources=["media://templates"],
            capabilities=["tools", "tasks"],
            connected=True,
        ),
        MCPServerStatus(
            name="analytics_server",
            transport="Streamable HTTP",
            endpoint="http://localhost:8084",
            tools=["compute_kpis", "detect_anomalies"],
            resources=["analytics://history"],
            capabilities=["tools", "resources"],
            connected=True,
        ),
    ]


@router.post("/{server_id}/sync", response_model=MCPSyncResponse)
async def sync_mcp_server(
    server_id: str,
    current_user: dict[str, Any] = Depends(require_role(UserRole.EDITOR)),
):
    return MCPSyncResponse(
        server_id=server_id,
        status="synced",
        tools_synced=4,
        resources_synced=2,
    )
