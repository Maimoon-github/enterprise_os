"""Validates retrieved and ingested knowledge structures."""

from __future__ import annotations

from typing import Any

_REQUIRED_DOCUMENT_KEYS = frozenset({"doc_id", "tenant_id", "text", "source", "retrieved_at"})


class SchemaValidator:
    """Validates that RAG documents conform to the expected shape."""

    def is_valid_document(self, document: dict[str, Any]) -> bool:
        """Return True if ``document`` contains all required, non-empty fields."""

        if not _REQUIRED_DOCUMENT_KEYS.issubset(document.keys()):
            return False
        return all(document[key] not in (None, "") for key in _REQUIRED_DOCUMENT_KEYS)

    def filter_valid(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return only the documents in ``documents`` that pass validation."""

        return [doc for doc in documents if self.is_valid_document(doc)]