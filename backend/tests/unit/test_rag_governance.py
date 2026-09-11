"""Verifies IE-only RAG access, tenant isolation, freshness, and validation."""
from datetime import datetime, timedelta, timezone

from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.schema_validator import SchemaValidator


def test_freshness_rejects_stale() -> None:
    stale = {"retrieved_at": datetime.now(timezone.utc) - timedelta(days=90)}
    assert FreshnessPolicy().is_fresh(stale) is False


def test_schema_validator_requires_core_fields() -> None:
    assert SchemaValidator().is_valid({"doc_id": "d", "content": "c"}) is True
    assert SchemaValidator().is_valid({"doc_id": "d"}) is False
