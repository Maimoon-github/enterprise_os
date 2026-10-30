import hashlib
import json
from datetime import datetime
from typing import Any


def generate_schedule_idempotency_key(
    campaign_id: str | Any,
    platform: str,
    scheduled_utc: datetime | str | None,
) -> str:
    sched_str = (
        scheduled_utc.isoformat()
        if isinstance(scheduled_utc, datetime)
        else str(scheduled_utc or "")
    )
    raw = f"{str(campaign_id)}:{platform.strip().lower()}:{sched_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_idempotency_key(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
