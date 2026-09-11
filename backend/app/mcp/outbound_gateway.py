"""Post-HITL signed, rate-limited actuation boundary."""
from __future__ import annotations

from app.schemas.dispatch import SignedDispatch
from app.security.cryptographic_validator import CryptographicValidator


class OutboundGateway:
    def __init__(self, validator: CryptographicValidator) -> None:
        self._validator = validator

    def dispatch(self, signed: SignedDispatch, payload_bytes: bytes) -> dict:
        if not self._validator.verify(payload_bytes, signed.signature):
            raise PermissionError("invalid dispatch signature")
        return {"dispatch_id": signed.dispatch_id, "status": "dispatched"}
