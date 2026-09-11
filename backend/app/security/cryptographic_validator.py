"""Validates signed caller, approval, and execution authorization."""
from __future__ import annotations

import hmac
from hashlib import sha256


class CryptographicValidator:
    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    def sign(self, payload: bytes) -> str:
        return hmac.new(self._secret, payload, sha256).hexdigest()

    def verify(self, payload: bytes, signature: str) -> bool:
        return hmac.compare_digest(self.sign(payload), signature)
