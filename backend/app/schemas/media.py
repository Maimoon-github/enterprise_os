import uuid
from datetime import datetime

from pydantic import BaseModel


class MediaAssetResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    campaign_id: uuid.UUID | None
    minio_bucket: str
    minio_key: str
    content_hash: str
    mime_type: str
    aspect_ratio: str | None
    created_at: datetime
