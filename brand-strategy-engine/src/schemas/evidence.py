"""Evidence reference schema and provenance contracts."""

from datetime import datetime, timezone
from typing import Any, Literal, Optional, Tuple
from pydantic import BaseModel, Field, HttpUrl


class EvidenceReference(BaseModel):
    """Deterministic reference to an empirical finding."""

    evidence_id: str = Field(
        ...,
        description="Unique deterministic ID of observed evidence, e.g. 'ev_001' or 'ev_vnc_screen_004'",
    )
    source_url: str = Field(
        ...,
        description="URL where evidence was captured (e.g., https://example.com)",
    )
    source_type: Literal["dom_selector", "vnc_screenshot", "rag_chunk", "serp_result"] = Field(
        ...,
        description="Origin mechanism of evidence collection",
    )
    dataset_reference: str = Field(
        ...,
        description="CSS selector path, pixel bounding box, or RAG chunk ID",
    )
    observation_notes: str = Field(
        ...,
        description="Raw visual, structural, or semantic notes recorded at capture",
    )
    screenshot_uri: Optional[str] = Field(
        default=None,
        description="Filesystem path to stored screenshot image blob",
    )
    bounding_box: Optional[Tuple[int, int, int, int]] = Field(
        default=None,
        description="Visual bounding box [x1, y1, x2, y2] coordinates",
    )
    sha256_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hex digest of the captured screenshot blob",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC capture timestamp",
    )


# Standard alias
EvidenceItem = EvidenceReference


class ChunkProvenance(BaseModel):
    """Immutable cryptographic provenance header contract for indexed document chunks."""

    chunk_id: str = Field(..., description="Deterministic chunk ID, e.g. 'chk_8a12f9b4'")
    document_id: str = Field(..., description="Unique document ID, e.g. 'doc_pitch_deck_2026'")
    source_filename: str = Field(..., description="Source filename, e.g. 'Q3_Brand_Pitch_Deck.pdf'")
    sha256_hash: str = Field(..., min_length=64, max_length=64, description="64-char SHA-256 hex digest")
    page_number: int = Field(default=1, description="Page or sheet/row locator")
    section_heading: str = Field(default="General", description="Section heading context")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp")
    byte_range: list[int] = Field(..., min_length=2, max_length=2, description="[start_byte, end_byte] range")
    content: str = Field(..., description="Extracted textual content")

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_evidence_reference(self, source_url: str = "") -> EvidenceReference:
        """Maps retrieved chunk to an authoritative EvidenceReference."""
        return EvidenceReference(
            evidence_id=self.chunk_id,
            source_url=source_url or f"file:///{self.source_filename}#page={self.page_number}",
            source_type="rag_chunk",
            dataset_reference=self.chunk_id,
            observation_notes=f"[{self.section_heading}] {self.content[:150]} (Source: {self.source_filename}, SHA-256: {self.sha256_hash[:8]})",
        )

