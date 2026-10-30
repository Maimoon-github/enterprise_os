from app.schemas.common import BaseSchema
from pydantic import Field


class SkillSummary(BaseSchema):
    name: str
    path: str | None = None
    description: str = ""
    compatibility: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    tier: str = "Tier 1/2/3"
    status: str = "validated"
    valid: bool = True
    lines_count: int = 0
    token_estimate: int = 0
    tier3_resources: list[str] = Field(default_factory=list)


class SkillDetailResponse(SkillSummary):
    content: str = ""
    tier2_body: str = ""


class SkillValidateRequest(BaseSchema):
    name: str
    content: str
    path: str | None = None


class SkillValidateResponse(BaseSchema):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    token_estimate: int = 0
    lines_count: int = 0

