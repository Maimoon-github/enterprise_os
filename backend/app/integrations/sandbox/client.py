"""Single backend wrapper for invoking the existing agent_sandbox SDK.

This is the only module in the backend permitted to import ``agent_sandbox``.
Its internal implementation is intentionally treated as opaque: this wrapper
converts backend mandates into whatever call shape the SDK expects and
converts SDK responses back into ``SandboxResult`` without leaking SDK
types past this module boundary.
"""

from __future__ import annotations

from app.core.exceptions import ConfigurationError, SandboxInvocationError
from app.core.settings import SandboxSettings
from app.integrations.sandbox.micro_tools import dispatch_micro_tool
from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate, SandboxResult


class SandboxClient:
    """Invokes existing sandbox capabilities and returns sanitized results."""

    def __init__(self, settings: SandboxSettings | None = None) -> None:
        self._settings = settings
        self._sandbox = None

    def _get_sandbox(self):
        """Lazily import and construct the agent_sandbox client on first use."""

        if self._sandbox is not None:
            return self._sandbox
        if self._settings is None or not self._settings.endpoint:
            return None
        try:
            import agent_sandbox

            base_url = self._settings.endpoint
            headers = {}
            if self._settings.api_key:
                headers["Authorization"] = f"Bearer {self._settings.api_key}"
            self._sandbox = agent_sandbox.Sandbox(base_url=base_url, headers=headers)
        except (ImportError, Exception):
            # Fall back to specialist micro-tool sandbox execution
            self._sandbox = None
        return self._sandbox

    async def invoke(self, mandate: SandboxInvocationMandate) -> SandboxResult:
        """Execute ``mandate`` against the sandbox and sanitize the result.

        Enforces capability allowlisting: only valid SandboxCapability values
        may execute. Executes the corresponding specialist micro-tool and
        returns a sanitized SandboxResult.
        """

        if not isinstance(mandate.capability, SandboxCapability):
            raise SandboxInvocationError(
                f"Unauthorized or invalid sandbox capability: {mandate.capability}"
            )

        try:
            raw_result = dispatch_micro_tool(mandate.capability, mandate.payload)
        except Exception as exc:  # noqa: BLE001 - sandbox internals are opaque by design
            return SandboxResult(
                task_id=mandate.task_id,
                capability=mandate.capability,
                success=False,
                error=str(exc),
            )

        sanitized_output = {str(key): str(value) for key, value in dict(raw_result).items()}
        return SandboxResult(
            task_id=mandate.task_id,
            capability=mandate.capability,
            success=True,
            sanitized_output=sanitized_output,
        )