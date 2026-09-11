"""Consolidates worker evidence and confidence intervals."""

from __future__ import annotations

from app.schemas.agent_contracts import ConfidenceInterval, EvidenceEnvelope


class SynthesizedEvidence:
    """The consolidated result of merging one or more evidence envelopes."""

    def __init__(
        self,
        task_id: str,
        evidence: list[str],
        confidence: ConfidenceInterval,
    ) -> None:
        self.task_id = task_id
        self.evidence = evidence
        self.confidence = confidence


class EvidenceSynthesizer:
    """Merges evidence envelopes using a confidence-weighted average."""

    def synthesize(self, envelopes: list[EvidenceEnvelope]) -> SynthesizedEvidence:
        """Return a single ``SynthesizedEvidence`` from one or more envelopes.

        Raises ``ValueError`` if ``envelopes`` is empty.
        """

        if not envelopes:
            raise ValueError("Cannot synthesize evidence from an empty envelope list.")

        task_id = envelopes[0].task_id
        total_weight = sum(env.confidence.point_estimate for env in envelopes) or 1.0

        weighted_point = sum(
            env.confidence.point_estimate * env.confidence.point_estimate for env in envelopes
        ) / total_weight
        weighted_lower = sum(
            env.confidence.lower_bound * env.confidence.point_estimate for env in envelopes
        ) / total_weight
        weighted_upper = sum(
            env.confidence.upper_bound * env.confidence.point_estimate for env in envelopes
        ) / total_weight

        merged_evidence: list[str] = []
        for env in envelopes:
            merged_evidence.extend(env.evidence)

        return SynthesizedEvidence(
            task_id=task_id,
            evidence=merged_evidence,
            confidence=ConfidenceInterval(
                point_estimate=weighted_point,
                lower_bound=weighted_lower,
                upper_bound=weighted_upper,
            ),
        )