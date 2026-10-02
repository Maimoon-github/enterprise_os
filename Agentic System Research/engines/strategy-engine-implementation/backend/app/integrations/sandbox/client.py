"""Reference SandboxClient extension for the unavailable existing host wrapper.

Do not replace the host's other capabilities. Merge invoke_s_alloc and connect
AgentSandboxControllerPort to the existing agent_sandbox SDK/controller. There
is deliberately no local Python, shell, subprocess or Docker fallback here.
"""
import asyncio
from typing import Protocol

from app.schemas.strategy import (ExecutionAttestation, SandboxMandate,
                                  SandboxResult, digest)


class AgentSandboxControllerPort(Protocol):
    async def execute_s_alloc(self, mandate: SandboxMandate) -> bytes:
        """Execute the fixed entrypoint via agent_sandbox in a fresh micro-VM.

        Enforce the policy before starting; bind execution_id to mandate hash;
        use a durable idempotency registry. Return <= max_output_bytes including
        sanitized output and a controller-signed attestation AFTER teardown.
        Cancellation must destroy the VM and audit controller-side exit traces.
        """
        ...

    def verify_attestation(self, attestation: ExecutionAttestation) -> bool:
        """Verify against pinned controller public keys, never a worker key."""
        ...


class SandboxClient:
    def __init__(self, controller: AgentSandboxControllerPort, *, image_digest: str):
        if len(image_digest) != 71 or not image_digest.startswith('sha256:'):
            raise ValueError('pin the deployed solver image SHA-256 digest')
        int(image_digest[7:], 16)
        self._controller = controller
        self._image_digest = image_digest

    async def invoke_s_alloc(self, mandate: SandboxMandate) -> SandboxResult:
        mandate = SandboxMandate.model_validate(mandate)
        async with asyncio.timeout(mandate.policy.timeout_seconds):
            raw = await self._controller.execute_s_alloc(mandate)
        if type(raw) is not bytes or len(raw) > mandate.policy.max_output_bytes:
            raise ValueError('sandbox result type/size violation')
        result = SandboxResult.model_validate_json(raw)
        a, o = result.attestation, result.output
        if not self._controller.verify_attestation(a):
            raise PermissionError('invalid controller attestation signature')
        if (a.execution_id != mandate.execution_id or o.execution_id != mandate.execution_id
                or a.mandate_hash != digest(mandate) or o.mandate_hash != digest(mandate)
                or a.policy_hash != digest(mandate.policy) or a.output_hash != digest(o)
                or a.image_digest != self._image_digest):
            raise ValueError('sandbox attestation binding mismatch')
        return result
