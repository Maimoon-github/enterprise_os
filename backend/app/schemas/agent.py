from app.schemas.common import BaseSchema
from pydantic import Field


class AgentConfig(BaseSchema):
    id: str
    name: str
    model: str
    role: str
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.7)
    allowed_tools: list[str] = Field(default_factory=list)


class AgentSummary(BaseSchema):
    id: str
    name: str
    model: str
    role: str
    active_workers: int = 1
    status: str = "online"


class AgentConfigUpdate(BaseSchema):
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    allowed_tools: list[str] | None = None
