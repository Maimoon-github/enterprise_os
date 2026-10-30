from app.schemas.common import BaseSchema, PlatformType, TimestampedSchema
from pydantic import Field


class BrandBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    voice_guidelines: str | None = None
    target_segments: list[str] = Field(default_factory=list)
    default_platforms: list[PlatformType] = Field(default_factory=list)


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BaseSchema):
    name: str | None = Field(None, max_length=100)
    slug: str | None = Field(None, max_length=100)
    voice_guidelines: str | None = None
    target_segments: list[str] | None = None
    default_platforms: list[PlatformType] | None = None


class BrandResponse(BrandBase, TimestampedSchema):
    pass
