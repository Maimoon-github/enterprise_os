from typing import Any

from app.api.deps import get_current_user, require_role
from app.core.rbac import UserRole
from app.mcp.host import mcp_host
from app.schemas.mcp import MCPServerStatus, MCPSyncResponse
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("", response_model=list[MCPServerStatus])
async def list_mcp_servers(current_user: dict[str, Any] = Depends(get_current_user)):
    """Retrieve list and capabilities of registered FastMCP servers compliant with MCP 2026-07-28."""
    servers = mcp_host.list_servers()
    return [
        MCPServerStatus(
            name=s["name"],
            transport=s["transport"],
            endpoint=s["endpoint"],
            tools=s.get("tools", []),
            resources=s.get("resources", []),
            capabilities=s.get("capabilities", ["tools", "resources"]),
            connected=True,
        )
        for s in servers
    ]


@router.post("/{server_id}/sync", response_model=MCPSyncResponse)
async def sync_mcp_server(
    server_id: str,
    current_user: dict[str, Any] = Depends(require_role(UserRole.EDITOR)),
):
    """Trigger server/discover and update local tool/resource inventory."""
    res = await mcp_host.sync_server(server_id)
    return MCPSyncResponse(
        server_id=server_id,
        status="synced",
        tools_synced=res["tools_synced"],
        resources_synced=res["resources_synced"],
    )
