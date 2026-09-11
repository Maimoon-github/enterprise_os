"""W_PROD: product specifications, evidence, claims, and compliance dossiers."""
from __future__ import annotations

from app.integrations.sandbox.client import SandboxClient


class ProductEvidenceAgent:
    worker_id = "W_PROD"
    capability = "S_VAL"

    def __init__(self, sandbox: SandboxClient | None = None) -> None:
        self.sandbox = sandbox or SandboxClient()

    def execute(self, payload: dict) -> dict:
        return self.sandbox.invoke(self.capability, self.worker_id, payload)
