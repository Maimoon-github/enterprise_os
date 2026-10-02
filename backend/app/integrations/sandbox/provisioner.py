"""Sandbox Provisioner backend entrypoint.

This module provides the thin client interface used by the Enterprise OS backend.
All container runtime creation, bubblewrap/bwrap, systemd-run, seccomp compilation,
and process spawning are completely excluded from the backend process and delegated
to the standalone Sandbox Provisioner service over an authenticated Unix Domain Socket.
"""

from __future__ import annotations

from pathlib import Path

from app.integrations.sandbox.provisioner_client import SandboxProvisionerClient
from app.integrations.sandbox.provisioner_daemon import (
    CAPABILITY_SKILL_MAP,
    PINNED_DIGEST,
    PINNED_IMAGE,
    PINNED_PROFILE_VERSION,
    PINNED_RUNTIME_VERSION,
)

# Alias for backwards compatibility across backend callers
SandboxProvisioner = SandboxProvisionerClient

_DEFAULT_PROVISIONER: SandboxProvisionerClient | None = None


def get_sandbox_provisioner(
    socket_path: str | Path | None = None,
    auth_token: str | None = None,
) -> SandboxProvisionerClient:
    """Return the authoritative SandboxProvisionerClient instance."""
    global _DEFAULT_PROVISIONER
    if _DEFAULT_PROVISIONER is None or socket_path is not None or auth_token is not None:
        _DEFAULT_PROVISIONER = SandboxProvisionerClient(socket_path=socket_path, auth_token=auth_token)
    return _DEFAULT_PROVISIONER


__all__ = [
    "CAPABILITY_SKILL_MAP",
    "PINNED_DIGEST",
    "PINNED_IMAGE",
    "PINNED_PROFILE_VERSION",
    "PINNED_RUNTIME_VERSION",
    "SandboxProvisioner",
    "SandboxProvisionerClient",
    "get_sandbox_provisioner",
]
