"""YouTube publishing and engagement adapter."""
from __future__ import annotations


class YouTubeAdapter:
    name = "youtube"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def publish(self, payload: dict) -> dict:
        raise PermissionError("social writes require signed HITL dispatch")
