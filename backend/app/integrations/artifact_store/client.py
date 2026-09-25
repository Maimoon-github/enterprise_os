"""Provider-neutral content-addressed artifact payload store.

Stores binary or string payloads keyed strictly by SHA-256 content address.
Enforces immutable write-once semantics: payloads are never overwritten.
"""

from __future__ import annotations

import hashlib
from typing import Any


def compute_sha256(content: bytes | str) -> str:
    """Return hex-encoded SHA-256 digest of content."""
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


class ArtifactStoreClient:
    """In-memory & pluggable provider-neutral artifact payload storage."""

    def __init__(self, root_prefix: str = "artifacts") -> None:
        self._root_prefix = root_prefix
        self._store: dict[str, bytes] = {}

    def _format_uri(self, content_hash: str) -> str:
        return f"{self._root_prefix}/{content_hash[:2]}/{content_hash[2:4]}/{content_hash}"

    async def put_if_absent(
        self,
        content: bytes | str,
        *,
        expected_hash: str | None = None,
        expected_length: int | None = None,
    ) -> tuple[str, int, str]:
        """Store content addressed by SHA-256 if not already present.

        Validates expected_hash and expected_length if supplied.
        Returns (content_hash, length, uri). Never overwrites existing payloads.
        """
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
        length = len(raw_bytes)
        content_hash = compute_sha256(raw_bytes)

        if expected_hash is not None and expected_hash.lower() != content_hash.lower():
            raise ValueError(
                f"Artifact content hash mismatch: expected '{expected_hash}', computed '{content_hash}'"
            )

        if expected_length is not None and expected_length != length:
            raise ValueError(
                f"Artifact length mismatch: expected {expected_length} bytes, got {length} bytes"
            )

        uri = self._format_uri(content_hash)
        # Write-once immutable semantics: do not overwrite existing content
        if content_hash not in self._store:
            self._store[content_hash] = raw_bytes

        return content_hash, length, uri

    async def get(self, content_hash: str) -> bytes:
        """Retrieve payload bytes by SHA-256 hash, raising KeyError if absent."""
        if content_hash not in self._store:
            raise KeyError(f"Artifact with content hash '{content_hash}' not found in store.")
        return self._store[content_hash]

    async def head(self, content_hash: str) -> dict[str, Any] | None:
        """Inspect artifact payload metadata without reading the full body."""
        if content_hash not in self._store:
            return None
        payload = self._store[content_hash]
        return {
            "content_hash": content_hash,
            "length": len(payload),
            "uri": self._format_uri(content_hash),
            "exists": True,
        }

    async def verify_integrity(self, content_hash: str) -> bool:
        """Recompute hash of stored bytes and verify match."""
        if content_hash not in self._store:
            return False
        return compute_sha256(self._store[content_hash]) == content_hash

    async def health(self) -> dict[str, Any]:
        """Return store operational capability without leaking payloads or tenant identities."""
        return {
            "status": "healthy",
            "type": "content_addressed_store",
            "object_count": len(self._store),
            "hash_algorithm": "SHA-256",
        }
