from pydantic import BaseModel, Field

class SkillSummary(BaseModel):
    name: str
    description: str
    compatibility: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    tier: str = "progressive_disclosure"
    valid: bool = True
