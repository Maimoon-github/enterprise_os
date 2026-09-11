"""Reads staged CMS data and applies approved content/schema changes."""
from __future__ import annotations


class CmsClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    def read(self, resource: str) -> dict:
        raise NotImplementedError("wire to vendor SDK via configuration")

    def apply(self, resource: str, payload: dict) -> dict:
        raise PermissionError("CMS writes require signed HITL dispatch")
