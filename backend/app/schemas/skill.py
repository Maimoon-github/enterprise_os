from app.schemas.common import BaseSchema
from pydantic import Field


class SkillSummary(BaseSchema):
    name: str
    path: str | None = None
    description: str = ""
    compatibility: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    tier: str = "progressive_disclosure"
    valid: bool = True


class SkillValidateRequest(BaseSchema):
    name: str
    content: str


class SkillValidateResponse(BaseSchema):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    token_estimate: int = 0
