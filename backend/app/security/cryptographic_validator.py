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


class ProviderHmacValidator:
    """Validates raw request byte signatures for specific third-party provider channels."""

    @staticmethod
    def _extract_candidate_secrets(secret: str | list[str]) -> list[str]:
        if isinstance(secret, list):
            return [s.strip() for s in secret if s and s.strip()]
        if "," in secret:
            return [s.strip() for s in secret.split(",") if s.strip()]
        return [secret.strip()] if secret.strip() else []

    @classmethod
    def verify_meta(
        cls,
        raw_bytes: bytes,
        signature_header: str | None,
        secret: str | list[str],
    ) -> bool:
        """Verify Meta / Instagram X-Hub-Signature-256 header over raw request bytes."""
        if not signature_header:
            return False
        import hashlib
        import hmac

        sig = signature_header.strip()
        if not sig.startswith("sha256="):
            return False
        expected_hex = sig[len("sha256=") :]

        for sec in cls._extract_candidate_secrets(secret):
            computed = hmac.new(
                sec.encode("utf-8"), raw_bytes, hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(computed, expected_hex):
                return True
        return False

    @classmethod
    def verify_tiktok(
        cls,
        raw_bytes: bytes,
        signature_header: str | None,
        timestamp_header: str | None,
        secret: str | list[str],
        *,
        tolerance_seconds: int = 300,
    ) -> bool:
        """Verify TikTok developer / business webhook signature over timestamp and raw request bytes."""
        if not signature_header:
            return False
        import hashlib
        import hmac
        import time

        # Timestamp freshness check
        if timestamp_header:
            try:
                ts = float(timestamp_header.strip())
                now = time.time()
                if abs(now - ts) > tolerance_seconds:
                    return False
            except ValueError:
                return False

        sig = signature_header.strip()
        if sig.startswith("sha256="):
            sig = sig[len("sha256=") :]

        for sec in cls._extract_candidate_secrets(secret):
            # TikTok signs timestamp + raw_bytes
            message = (timestamp_header.encode("utf-8") if timestamp_header else b"") + raw_bytes
            computed = hmac.new(
                sec.encode("utf-8"), message, hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(computed, sig):
                return True
            # Fallback if provider signs raw_bytes alone
            computed_raw = hmac.new(
                sec.encode("utf-8"), raw_bytes, hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(computed_raw, sig):
                return True
        return False

    @classmethod
    def verify_generic_hmac(
        cls,
        raw_bytes: bytes,
        signature_header: str | None,
        secret: str | list[str],
    ) -> bool:
        """Verify generic HMAC-SHA256 signature with constant-time comparison and key rotation."""
        if not signature_header:
            return False
        import hashlib
        import hmac

        sig = signature_header.strip()
        if sig.startswith("sha256="):
            sig = sig[len("sha256=") :]

        for sec in cls._extract_candidate_secrets(secret):
            computed = hmac.new(
                sec.encode("utf-8"), raw_bytes, hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(computed, sig):
                return True
        return False


def verify_raw_webhook_signature(
    channel: str,
    raw_bytes: bytes,
    headers: dict[str, str],
    secret: str | list[str] | None,
    *,
    tolerance_seconds: int = 300,
) -> bool:
    """Route provider raw bytes to appropriate cryptographic verifier."""
    if not secret:
        return True  # If no secret configured process-wide, allow unauthenticated
    ch_lower = channel.lower()
    lower_headers = {k.lower(): v for k, v in headers.items()}

    if ch_lower in ("meta", "instagram"):
        sig = lower_headers.get("x-hub-signature-256")
        return ProviderHmacValidator.verify_meta(raw_bytes, sig, secret)

    if ch_lower == "tiktok":
        sig = lower_headers.get("tiktok-signature") or lower_headers.get("x-signature")
        ts = lower_headers.get("tiktok-timestamp") or lower_headers.get("x-timestamp")
        return ProviderHmacValidator.verify_tiktok(
            raw_bytes, sig, ts, secret, tolerance_seconds=tolerance_seconds
        )

    sig = (
        lower_headers.get("x-hub-signature-256")
        or lower_headers.get("x-signature")
        or lower_headers.get("authorization")
    )
    return ProviderHmacValidator.verify_generic_hmac(raw_bytes, sig, secret)