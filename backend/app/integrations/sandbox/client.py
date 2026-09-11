"""Single backend wrapper for invoking the existing agent_sandbox SDK.

This is the only module in the backend permitted to import ``agent_sandbox``.
Its internal implementation is intentionally treated as opaque: this wrapper
converts backend mandates into whatever call shape the SDK expects and
converts SDK responses back into ``SandboxResult`` without leaking SDK
types past this module boundary.
"""

from __future__ import annotations

from app.core.exceptions import ConfigurationError
from app.core.settings import SandboxSettings
from app.schemas.sandbox import SandboxInvocationMandate, SandboxResult


class SandboxClient:
    """Invokes existing sandbox capabilities and returns sanitized results."""

    def __init__(self, settings: SandboxSettings) -> None:
        self._settings = settings
        self._sandbox = None

    def _get_sandbox(self):
        """Lazily import and construct the agent_sandbox client on first use."""

        if self._sandbox is not None:
            return self._sandbox
        try:
            import agent_sandbox
        except ImportError as exc:
            raise ConfigurationError(
                "The 'agent_sandbox' SDK is not installed. Install the optional "
                "'sandbox' extra (pip install '.[sandbox]') and configure SANDBOX_* "
                "settings to enable worker execution."
            ) from exc

        self._sandbox = agent_sandbox.Sandbox(
            endpoint=self._settings.endpoint,
            api_key=self._settings.api_key,
        )
        return self._sandbox

    async def invoke(self, mandate: SandboxInvocationMandate) -> SandboxResult:
        """Execute ``mandate`` against the existing sandbox and sanitize the result."""

        sandbox = self._get_sandbox()
        try:
            raw_result = await sandbox.invoke(
                capability=mandate.capability.value,
                payload=mandate.payload,
                timeout=mandate.timeout_seconds,
            )
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