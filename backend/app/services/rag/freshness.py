"""Enforces evidence freshness requirements for retrieved knowledge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


class FreshnessPolicy:
    """Rejects retrieved documents older than a configured maximum age."""

    def __init__(self, max_age: timedelta = timedelta(days=90)) -> None:
        self._max_age = max_age

    def is_fresh(self, document: dict[str, Any], *, now: datetime | None = None) -> bool:
        """Return True if ``document['retrieved_at']`` is within the freshness window."""

        retrieved_at = document.get("retrieved_at")
        if not isinstance(retrieved_at, datetime):
            return False
        reference = now or datetime.now(UTC)
        return (reference - retrieved_at) <= self._max_age

    def filter_fresh(
        self, documents: list[dict[str, Any]], *, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Return only the documents that satisfy the freshness policy."""

        return [doc for doc in documents if self.is_fresh(doc, now=now)]