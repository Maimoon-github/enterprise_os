"""Verifies evidence-envelope consolidation and confidence handling."""

from __future__ import annotations

import pytest

from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.schemas.agent_contracts import ConfidenceInterval, EvidenceEnvelope
from app.schemas.governance import WorkerRole


def _envelope(task_id: str, point: float, evidence: list[str]) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        task_id=task_id,
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        confidence=ConfidenceInterval(
            point_estimate=point, lower_bound=point - 0.1, upper_bound=point + 0.1
        ),
        evidence=evidence,
    )


def test_synthesize_merges_evidence_from_all_envelopes() -> None:
    synthesizer = EvidenceSynthesizer()
    envelopes = [
        _envelope("t1", 0.8, ["roas improved 12%"]),
        _envelope("t1", 0.6, ["attribution window shortened"]),
    ]

    synthesized = synthesizer.synthesize(envelopes)

    assert synthesized.task_id == "t1"
    assert "roas improved 12%" in synthesized.evidence
    assert "attribution window shortened" in synthesized.evidence


def test_synthesize_weights_higher_confidence_envelopes_more() -> None:
    synthesizer = EvidenceSynthesizer()
    envelopes = [_envelope("t1", 0.9, ["strong evidence"]), _envelope("t1", 0.1, ["weak evidence"])]

    synthesized = synthesizer.synthesize(envelopes)

    # The weighted point estimate should lean toward the higher-confidence envelope.
    assert synthesized.confidence.point_estimate > 0.5


def test_synthesize_raises_on_empty_envelopes() -> None:
    synthesizer = EvidenceSynthesizer()

    with pytest.raises(ValueError):
        synthesizer.synthesize([])