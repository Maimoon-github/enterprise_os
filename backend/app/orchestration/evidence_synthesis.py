"""Consolidates worker evidence and confidence intervals."""
from __future__ import annotations

from app.schemas.agent_contracts import EvidenceEnvelope


class EvidenceSynthesizer:
    def synthesize(self, envelopes: list[EvidenceEnvelope]) -> dict:
        if not envelopes:
            return {"summary": "", "confidence": 0.0, "citations": []}
        confidence = sum(e.confidence for e in envelopes) / len(envelopes)
        citations = sorted({c for e in envelopes for c in e.citations})
        summary = " | ".join(e.summary for e in envelopes if e.summary)
        return {"summary": summary, "confidence": confidence, "citations": citations}
