from pydantic import BaseModel, Field


class MCPServerStatus(BaseModel):
    name: str
    transport: str
    endpoint: str
    tools: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    connected: bool = True
