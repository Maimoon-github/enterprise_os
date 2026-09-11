"""Appends W3C PROV audit records."""
from __future__ import annotations

from app.schemas.provenance import ProvRecord


class ProvenanceRepository:
    def __init__(self) -> None:
        self._records: list[ProvRecord] = []

    def append(self, record: ProvRecord) -> None:
        self._records.append(record)

    def all(self) -> list[ProvRecord]:
        return list(self._records)
