
from app.schemas.common import TimestampedSchema
from pydantic import BaseModel, Field


class BrandBase(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)
    voice_guidelines: str | None = None
    target_segments: list[str] = Field(default_factory=list)
    default_platforms: list[str] = Field(default_factory=list)

class BrandCreate(BrandBase):
    pass

class BrandResponse(BrandBase, TimestampedSchema):
    pass
