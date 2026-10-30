import uuid

from app.schemas.common import BaseSchema, TimestampedSchema


class MediaAssetResponse(TimestampedSchema):
    brand_id: uuid.UUID
    campaign_id: uuid.UUID | None = None
    minio_bucket: str
    minio_key: str
    content_hash: str
    mime_type: str
    width: int | None = None
    height: int | None = None
    aspect_ratio: str | None = None
    prompt_lineage: str | None = None


class MediaPresignedUrlResponse(BaseSchema):
    url: str
    bucket: str
    key: str
    expires_in: int = 3600
