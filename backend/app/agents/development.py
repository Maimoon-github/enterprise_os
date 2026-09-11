"""W_DEV: CMS schemas, UI layouts, code diffs, and web-development work."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class DevelopmentAgent:
    worker_id = "W_DEV"
    capability = "S_CODE"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
