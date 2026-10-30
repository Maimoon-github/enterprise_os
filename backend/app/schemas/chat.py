import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default=None, description="Optional chat session title")
    project_id: str | None = Field(default=None, description="Optional project or folder tag")
    brand_id: uuid.UUID | None = Field(default=None, description="Scoped brand workspace ID")


class ChatSessionUpdate(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None
    project_id: str | None = None


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, description="User instruction or orchestrator command")
    skills_override: list[str] | None = Field(default=None, description="Optional skills allowlist override")
    campaign_id: uuid.UUID | None = Field(default=None, description="Linked campaign ID")
    brand_id: uuid.UUID | None = Field(default=None, description="Brand workspace context")
    stream: bool = Field(default=True, description="Whether to stream response via SSE")


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    run_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    title: str
    is_pinned: bool = False
    is_archived: bool = False
    project_id: str | None = None
    brand_id: uuid.UUID | None = None
    messages_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatSessionDetailResponse(ChatSessionResponse):
    messages: list[ChatMessageResponse] = Field(default_factory=list)
