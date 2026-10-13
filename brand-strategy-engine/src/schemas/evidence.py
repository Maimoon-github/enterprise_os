"""Evidence reference schema and provenance contracts."""

from datetime import datetime, timezone
from typing import Literal
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
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC capture timestamp",
    )
