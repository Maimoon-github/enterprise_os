"""Enforces evidence freshness requirements."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


class FreshnessPolicy:
    def __init__(self, max_age: timedelta = timedelta(days=30)) -> None:
        self.max_age = max_age

    def is_fresh(self, hit: dict, now: datetime | None = None) -> bool:
        ts = hit.get("retrieved_at")
        if ts is None:
            return True
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        now = now or datetime.now(timezone.utc)
        return (now - ts) <= self.max_age
