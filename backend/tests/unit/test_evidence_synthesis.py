"""Verifies evidence-envelope consolidation and confidence handling."""
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.schemas.agent_contracts import EvidenceEnvelope


def test_synthesis_averages_confidence() -> None:
    envelopes = [
        EvidenceEnvelope(worker_id="W_DEV", task_id="t", summary="a", confidence=0.4),
        EvidenceEnvelope(worker_id="W_STRAT", task_id="t", summary="b", confidence=0.8),
    ]
    result = EvidenceSynthesizer().synthesize(envelopes)
    assert result["confidence"] == 0.6


def test_synthesis_empty_returns_zero() -> None:
    result = EvidenceSynthesizer().synthesize([])
    assert result["confidence"] == 0.0
