"""Verifies required control-plane and execution audit lineage."""
from datetime import datetime, timezone

from app.persistence.repositories.provenance import ProvenanceRepository
from app.schemas.provenance import ProvRecord


def test_provenance_append_only() -> None:
    repo = ProvenanceRepository()
    now = datetime.now(timezone.utc)
    repo.append(ProvRecord(entity_id="e", activity_id="a", agent_id="W_DEV", started_at=now))
    assert len(repo.all()) == 1
