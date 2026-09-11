"""Validates signed caller, approval, and execution authorization.

Uses Ed25519 signatures: small, fast, and deterministic, which keeps
signature verification simple and dependency-light while remaining a
production-appropriate choice for signing approval and dispatch payloads.
"""

from __future__ import annotations

import base64

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.core.exceptions import SignatureVerificationError


class CryptographicValidator:
    """Verifies Ed25519 signatures over canonical payload bytes."""

    def __init__(self, public_key_pem: str | None) -> None:
        self._public_key: Ed25519PublicKey | None = None
        if public_key_pem:
            from cryptography.hazmat.primitives.serialization import load_pem_public_key

            loaded = load_pem_public_key(public_key_pem.encode("utf-8"))
            if not isinstance(loaded, Ed25519PublicKey):
                raise SignatureVerificationError("Configured signing key is not Ed25519.")
            self._public_key = loaded

    def verify(self, payload: bytes, signature_b64: str) -> bool:
        """Return True if ``signature_b64`` is a valid signature over ``payload``."""

        if self._public_key is None:
            raise SignatureVerificationError(
                "No signing public key is configured; cannot verify signatures."
            )
        try:
            signature = base64.b64decode(signature_b64)
            self._public_key.verify(signature, payload)
            return True
        except (InvalidSignature, ValueError):
            return False


def sign_payload(payload: bytes, private_key: Ed25519PrivateKey) -> str:
    """Return a base64-encoded Ed25519 signature over ``payload``.

    Used by trusted approval/dispatch issuers (e.g. the HITL approval flow),
    never by workers or unauthenticated callers.
    """

    signature = private_key.sign(payload)
    return base64.b64encode(signature).decode("ascii")