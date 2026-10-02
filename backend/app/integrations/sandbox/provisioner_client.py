"""Thin Unix Domain Socket Client for Sandbox Provisioner Service.

Backend, Intelligence Engine, Workers, and Specialists interact exclusively
through this thin client. This module contains:
- ZERO subprocess-based container or sandbox creation
- ZERO bwrap or systemd-run execution authority
- ZERO Docker / containerd socket access
- ZERO host process-spawning authority

All execution requests are serialized as typed SandboxInvocationMandates and sent
across an authenticated Unix Domain Socket to the standalone Sandbox Provisioner service.
"""

from __future__ import annotations

import contextlib
import json
import logging
import socket
import struct
from pathlib import Path
from typing import Any

from app.core.exceptions import (
    PolicyViolationError,
    SandboxExecutionError,
    SandboxInvocationError,
    SandboxIsolationError,
    SandboxValidationError,
)
from app.core.settings import SandboxSettings
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxInvocationMandate,
    SandboxResult,
)

logger = logging.getLogger(__name__)

_VALID_CAPABILITIES = {
    SandboxCapability.ALLOC: "s-alloc",
    SandboxCapability.VAL: "s-val",
    SandboxCapability.COPY: "s-copy",
    SandboxCapability.CODE: "s-code",
    SandboxCapability.COMP: "s-comp",
    SandboxCapability.PARSE: "s-parse",
    SandboxCapability.ATTR: "s-attr",
}


class SandboxProvisionerClient:
    """Thin UDS client communicating with the standalone Sandbox Provisioner daemon."""

    def __init__(
        self,
        socket_path: str | Path | None = None,
        auth_token: str | None = None,
        settings: SandboxSettings | None = None,
    ) -> None:
        cfg = settings or SandboxSettings()
        self.socket_path = Path(socket_path or cfg.provisioner_socket_path)
        self.auth_token = auth_token or cfg.provisioner_auth_token

    @property
    def has_physical_isolation_runtime(self) -> bool:
        """Check whether the standalone provisioner socket is active."""
        if not self.socket_path.exists():
            return False
        # Probe socket connectivity
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.settimeout(0.5)
            sock.connect(str(self.socket_path))
            return True
        except Exception:
            return False
        finally:
            with contextlib.suppress(Exception):
                sock.close()

    def validate_mandate(self, mandate: SandboxInvocationMandate) -> str:
        """Client-side pre-validation of mandate before socket dispatch."""
        if mandate.capability not in _VALID_CAPABILITIES:
            cap_val = getattr(mandate.capability, "value", str(mandate.capability))
            raise SandboxValidationError(f"Unauthorized or unregistered sandbox capability: {cap_val}")

        for k, v in mandate.payload.items():
            if isinstance(v, str) and ("../" in v or "..\\" in v):
                raise SandboxValidationError(f"Path traversal detected in input payload parameter '{k}'")

        if mandate.network_policy != NetworkPolicy.DISABLED and mandate.egress_grant is None:
            raise PolicyViolationError(
                f"Network policy '{mandate.network_policy.value}' requested without approved SandboxEgressGrant."
            )

        return _VALID_CAPABILITIES[mandate.capability]

    def execute(self, mandate: SandboxInvocationMandate) -> SandboxResult:
        """Dispatch typed mandate over UDS to the standalone provisioner service."""
        # 1. Pre-validation
        self.validate_mandate(mandate)

        # 2. Check socket availability
        if not self.socket_path.exists():
            raise SandboxIsolationError(
                f"Sandbox Provisioner UDS socket '{self.socket_path}' not found. "
                "The standalone provisioner service must be running."
            )

        # 3. Connect to standalone provisioner UDS
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(float(mandate.timeout_seconds + 30))
        try:
            sock.connect(str(self.socket_path))
        except Exception as exc:
            raise SandboxIsolationError(
                f"Failed to connect to Sandbox Provisioner service at '{self.socket_path}': {exc}"
            ) from exc

        try:
            # 4. Serialize request
            req_data = {
                "auth_token": self.auth_token,
                "mandate": mandate.model_dump(mode="json"),
            }
            req_bytes = json.dumps(req_data, ensure_ascii=False).encode("utf-8")

            # Send length-prefixed framing (4-byte big-endian)
            sock.sendall(struct.pack(">I", len(req_bytes)) + req_bytes)

            # 5. Read length-prefixed response
            len_bytes = self._recv_exact(sock, 4)
            if not len_bytes:
                raise SandboxExecutionError("Provisioner service closed connection before sending response length.")

            resp_len = struct.unpack(">I", len_bytes)[0]
            resp_bytes = self._recv_exact(sock, resp_len)
            if not resp_bytes:
                raise SandboxExecutionError("Provisioner service closed connection before sending complete payload.")

            resp_json = json.loads(resp_bytes.decode("utf-8"))

            # 6. Error dispatch
            if not resp_json.get("success", False):
                err_msg = resp_json.get("error", "Unknown provisioner error")
                err_type = resp_json.get("error_type", "")
                if err_type == "PolicyViolationError":
                    raise PolicyViolationError(err_msg)
                if err_type == "SandboxValidationError":
                    raise SandboxValidationError(err_msg)
                if err_type == "SandboxIsolationError":
                    raise SandboxIsolationError(err_msg)
                if err_type == "SandboxExecutionError":
                    raise SandboxExecutionError(err_msg)
                raise SandboxInvocationError(f"Provisioner service error ({err_type}): {err_msg}")

            # 7. Deserialize strongly typed result
            return SandboxResult.model_validate(resp_json["result"])

        except (
            PolicyViolationError,
            SandboxValidationError,
            SandboxIsolationError,
            SandboxExecutionError,
            SandboxInvocationError,
        ):
            raise
        except Exception as exc:
            raise SandboxExecutionError(f"Provisioner communication failed: {exc}") from exc
        finally:
            with contextlib.suppress(Exception):
                sock.close()

    def _recv_exact(self, sock: socket.socket, num_bytes: int) -> bytes | None:
        buf = bytearray()
        while len(buf) < num_bytes:
            chunk = sock.recv(num_bytes - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)
