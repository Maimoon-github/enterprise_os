"""Validates retrieved and ingested knowledge structures."""
from __future__ import annotations

_REQUIRED = {"doc_id", "content"}


class SchemaValidator:
    def is_valid(self, hit: dict) -> bool:
        return _REQUIRED.issubset(hit.keys())
