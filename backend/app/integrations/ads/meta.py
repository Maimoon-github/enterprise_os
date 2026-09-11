"""Meta campaign, targeting, bid, and telemetry adapter."""
from __future__ import annotations


class MetaAdsAdapter:
    name = "meta"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def push_campaign(self, campaign: dict) -> dict:
        raise PermissionError("paid-media writes require signed HITL dispatch")
