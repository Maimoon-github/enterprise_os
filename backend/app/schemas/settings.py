from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlatformConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    is_connected: bool
    account_name: str | None = None
    masked_client_id: str | None = None
    last_synced_at: datetime | None = None


class PlatformConnectionUpdate(BaseModel):
    client_id: str | None = Field(default=None, description="Platform client/app ID")
    client_secret: str | None = Field(default=None, description="Platform client secret (stored encrypted)")
    access_token: str | None = Field(default=None, description="Platform access/bearer token (stored encrypted)")
    account_name: str | None = Field(default=None, description="Display name for account")


class PlatformConnectionTestResult(BaseModel):
    platform: str
    is_valid: bool
    latency_ms: int
    message: str


class AnalyticsChannelState(BaseModel):
    platform: str
    is_connected: bool
    events_count: int
    impressions: int
    clicks: int
    last_synced_at: datetime | None = None


class UserPreferencesResponse(BaseModel):
    theme: str = "bloodstone"
    notifications_enabled: bool = True
    auto_stream_chat: bool = True
    default_brand_id: str | None = None


class UserPreferencesUpdate(BaseModel):
    theme: str | None = None
    notifications_enabled: bool | None = None
    auto_stream_chat: bool | None = None
    default_brand_id: str | None = None
