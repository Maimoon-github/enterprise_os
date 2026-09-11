"""X publishing and engagement adapter."""
from __future__ import annotations


class XAdapter:
    name = "x"

    def __init__(self, credentials: dict) -> None:
        self._credentials = credentials

    def publish(self, payload: dict) -> dict:
        raise PermissionError("social writes require signed HITL dispatch")
