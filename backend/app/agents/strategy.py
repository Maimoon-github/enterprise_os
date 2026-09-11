"""W_STRAT: omnichannel roadmaps, funnels, media mix, and budgets."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class StrategyAgent:
    worker_id = "W_STRAT"
    capability = "S_ALLOC"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
