"""TikTok social publishing and engagement adapter."""
from __future__ import annotations


class TikTokSocialAdapter:
    name = "tiktok-social"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def publish(self, payload: dict) -> dict:
        raise PermissionError("social writes require signed HITL dispatch")
