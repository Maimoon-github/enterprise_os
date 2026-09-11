"""Maps W_DEV-W_LEARN worker roles to S_CODE-S_ATTR sandbox capabilities."""

from __future__ import annotations

from app.schemas.governance import WorkerRole
from app.schemas.sandbox import SandboxCapability

WORKER_CAPABILITY_MAP: dict[WorkerRole, SandboxCapability] = {
    WorkerRole.DEVELOPMENT: SandboxCapability.CODE,
    WorkerRole.STRATEGY: SandboxCapability.ALLOC,
    WorkerRole.CREATIVE_CONTENT: SandboxCapability.COPY,
    WorkerRole.PRODUCT_EVIDENCE: SandboxCapability.VAL,
    WorkerRole.COMPETITOR_INTEL: SandboxCapability.SCRAPE,
    WorkerRole.CUSTOMER_VOICE: SandboxCapability.PARSE,
    WorkerRole.LEARNING_PERFORMANCE: SandboxCapability.ATTR,
}


def get_capability_for_role(role: WorkerRole) -> SandboxCapability:
    """Return the single sandbox capability authorized for ``role``.

    Raises ``KeyError`` if ``role`` has no mapped capability, which should
    never happen for one of the seven bounded worker roles.
    """

    return WORKER_CAPABILITY_MAP[role]