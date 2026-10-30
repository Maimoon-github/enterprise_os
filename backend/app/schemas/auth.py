import uuid
from datetime import datetime

from app.schemas.common import BaseSchema, TimestampedSchema
from pydantic import Field


class LoginRequest(BaseSchema):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class RefreshTokenRequest(BaseSchema):
    refresh_token: str


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    role: str


class UserCreate(BaseSchema):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    full_name: str | None = None
    role: str = "viewer"


class UserUpdate(BaseSchema):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserProfile(TimestampedSchema):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    role: str
    is_active: bool = True
    created_at: datetime

