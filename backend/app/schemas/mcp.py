from app.schemas.common import BaseSchema
from pydantic import Field


class MCPServerStatus(BaseSchema):
    name: str
    transport: str
    endpoint: str
    tools: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    connected: bool = True


class MCPSyncResponse(BaseSchema):
    server_id: str
    status: str = "synced"
    tools_synced: int = 0
    resources_synced: int = 0
