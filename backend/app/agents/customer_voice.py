"""W_VOICE: tickets, reviews, sentiment, and objection analysis."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class CustomerVoiceAgent:
    worker_id = "W_VOICE"
    capability = "S_PARSE"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
