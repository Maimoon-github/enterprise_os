"""LinkedIn paid-media adapter defined by the architecture."""
from __future__ import annotations


class LinkedInAdsAdapter:
    name = "linkedin"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def push_campaign(self, campaign: dict) -> dict:
        raise PermissionError("paid-media writes require signed HITL dispatch")
