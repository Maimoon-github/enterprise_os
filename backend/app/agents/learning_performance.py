"""W_LEARN: attribution, fatigue, decay, ROAS, and validated learning deltas."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class LearningPerformanceAgent:
    worker_id = "W_LEARN"
    capability = "S_ATTR"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
