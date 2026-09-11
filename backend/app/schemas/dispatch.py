"""Signed post-HITL execution directives."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SignedDispatch(BaseModel):
    dispatch_id: str
    preview_id: str
    tenant_id: str
    signature: str
    payload: dict
    scopes: list[str] = Field(default_factory=list)
