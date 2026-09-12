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
        if isinstance(retrieved_at, str):
            try:
                retrieved_at = datetime.fromisoformat(retrieved_at)
            except ValueError:
                return False
        if not isinstance(retrieved_at, datetime):
            return False
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=UTC)
        reference = now or datetime.now(UTC)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=UTC)
        return (reference - retrieved_at) <= self._max_age

    def filter_fresh(
        self, documents: list[dict[str, Any]], *, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Return only the documents that satisfy the freshness policy."""

        return [doc for doc in documents if self.is_fresh(doc, now=now)]