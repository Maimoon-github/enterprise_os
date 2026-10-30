from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    id: str
    name: str
    model: str
    role: str
    max_tokens: int = Field(default=4096)
    temperature: float = Field(default=0.7)
    allowed_tools: list[str] = Field(default_factory=list)
