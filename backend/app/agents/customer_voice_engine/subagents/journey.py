"""VOICE-JOURNEY: Customer Voice Journey Specialist Sub-Agent.

Responsible for descriptive channel, touchpoint, segment, and temporal comparisons.
Strictly prohibits causal assertions and enforces mandatory non-causal disclosures
under DENY_ALL network policy.
"""

from __future__ import annotations

from typing import Any

from app.agents.customer_voice_engine.profiles import JOURNEY_PROFILE, SpecialistModelProfile
from app.schemas.customer_voice import VoiceWorkflowStage


class VoiceJourneyAgent:
    """Specialist sub-agent for Customer Voice Journey (VOICE-JOURNEY)."""

    SPECIALIST_ID = "VOICE-JOURNEY"
    ROLE = VoiceWorkflowStage.JOURNEY

    def __init__(
        self,
        llm_client: Any = None,
        profile: SpecialistModelProfile | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._profile = profile or JOURNEY_PROFILE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    @property
    def role(self) -> VoiceWorkflowStage:
        return self.ROLE

    @property
    def profile(self) -> SpecialistModelProfile:
        return self._profile

    @property
    def llm_client(self) -> Any:
        return self._llm_client

    async def execute(
        self,
        task: Any,
        records: list[Any],
        evidence_spans: list[Any],
        *,
        themes_findings: list[Any] | None = None,
        sentiment_findings: list[Any] | None = None,
        needs_findings: list[Any] | None = None,
        corpus_hash: str | None = None,
        segments: list[str] | None = None,
        time_interval: str | None = None,
    ) -> Any:
        """Execute descriptive journey and channel comparisons for VOICE-JOURNEY.

        Enforces:
        - descriptive_comparison only; never infer causality
        - mandatory causal_claim_disclaimer
        - explicit segments and time intervals preserved without demographic fabrication
        - grounded in exact evidence spans
        """
        import hashlib
        from app.integrations.sandbox.s_parse_core import analyze_journey_core
        from app.schemas.customer_voice import EvidenceSpan, JourneyComparison, VoiceSpecialistResult

        tenant_id = getattr(task, "tenant_id", "default")
        task_id = getattr(task, "task_id", getattr(task, "parent_task_id", "task-journey"))

        records_dict = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in records]
        spans_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in evidence_spans]
        themes_dict = [t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in (themes_findings or [])]
        sentiment_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in (sentiment_findings or [])]
        needs_dict = [n.model_dump() if hasattr(n, "model_dump") else dict(n) for n in (needs_findings or [])]

        input_hash = corpus_hash or hashlib.sha256(
            (str(records_dict) + str(spans_dict)).encode("utf-8")
        ).hexdigest()

        raw_comparisons = analyze_journey_core(
            records=records_dict,
            spans=spans_dict,
            themes_findings=themes_dict,
            sentiment_findings=sentiment_dict,
            needs_findings=needs_dict,
            segments=segments,
            time_interval=time_interval,
        )

        journey_findings = [JourneyComparison.model_validate(c) for c in raw_comparisons]
        out_bytes = str([c.model_dump() for c in journey_findings]).encode("utf-8")
        output_hash = hashlib.sha256(out_bytes).hexdigest()

        return VoiceSpecialistResult(
            specialist_id=self.SPECIALIST_ID,
            task_id=task_id,
            stage=self.ROLE,
            success=True,
            input_hash=input_hash,
            output_hash=output_hash,
            findings=journey_findings,
            evidence_spans=[EvidenceSpan.model_validate(s) for s in spans_dict],
            records=[],
            artifacts=[f"journey:{task_id}:{output_hash[:12]}"],
            provenance={
                "specialist_id": self.SPECIALIST_ID,
                "role": self.ROLE.value,
                "task_id": task_id,
                "tenant_id": tenant_id,
                "records_analyzed": len(records),
                "comparisons_count": len(journey_findings),
                "input_corpus_hash": input_hash,
                "output_hash": output_hash,
            },
        )

