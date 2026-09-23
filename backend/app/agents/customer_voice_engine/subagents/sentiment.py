"""VOICE-SENTIMENT: Customer Voice Sentiment Specialist Sub-Agent.

Responsible for aspect-level sentiment scoring, emotion detection, calibration,
and grounding evidence spans over the immutable sanitized corpus under DENY_ALL network policy.
"""

from __future__ import annotations

from typing import Any

from app.agents.customer_voice_engine.profiles import SENTIMENT_PROFILE, SpecialistModelProfile
from app.schemas.customer_voice import VoiceWorkflowStage


class VoiceSentimentAgent:
    """Specialist sub-agent for Customer Voice Sentiment (VOICE-SENTIMENT)."""

    SPECIALIST_ID = "VOICE-SENTIMENT"
    ROLE = VoiceWorkflowStage.SENTIMENT

    def __init__(
        self,
        llm_client: Any = None,
        profile: SpecialistModelProfile | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._profile = profile or SENTIMENT_PROFILE

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
        corpus_hash: str | None = None,
        supported_locales: set[str] | None = None,
        model_name: str = "absa_classifier_v1.0",
    ) -> Any:
        """Execute aspect-level sentiment classification for VOICE-SENTIMENT.

        Preserves:
        - aspect, polarity, optional emotion, model score, score_is_calibrated=False
        - locale and model version
        - grounded evidence spans
        - uncertainty reasons (low sample count, unsupported locale/model)
        - never labels uncalibrated scores as confidence or probability
        - unsupported locale/model -> 'not_assessed'
        """
        import hashlib
        from app.integrations.sandbox.s_parse_core import analyze_aspect_sentiment_core
        from app.schemas.customer_voice import AspectSentimentFinding, EvidenceSpan, VoiceSpecialistResult

        tenant_id = getattr(task, "tenant_id", "default")
        task_id = getattr(task, "task_id", getattr(task, "parent_task_id", "task-sentiment"))

        records_dict = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in records]
        spans_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in evidence_spans]

        input_hash = corpus_hash or hashlib.sha256(
            (str(records_dict) + str(spans_dict)).encode("utf-8")
        ).hexdigest()

        raw_aspects = analyze_aspect_sentiment_core(
            records=records_dict,
            spans=spans_dict,
            supported_locales=supported_locales,
            model_name=model_name,
        )

        aspect_findings = [AspectSentimentFinding.model_validate(a) for a in raw_aspects]
        out_bytes = str([a.model_dump() for a in aspect_findings]).encode("utf-8")
        output_hash = hashlib.sha256(out_bytes).hexdigest()

        return VoiceSpecialistResult(
            specialist_id=self.SPECIALIST_ID,
            task_id=task_id,
            stage=self.ROLE,
            success=True,
            input_hash=input_hash,
            output_hash=output_hash,
            findings=aspect_findings,
            evidence_spans=[EvidenceSpan.model_validate(s) for s in spans_dict],
            records=[],
            artifacts=[f"sentiment:{task_id}:{output_hash[:12]}"],
            provenance={
                "specialist_id": self.SPECIALIST_ID,
                "role": self.ROLE.value,
                "task_id": task_id,
                "tenant_id": tenant_id,
                "records_analyzed": len(records),
                "aspects_analyzed": len(aspect_findings),
                "model_name": model_name,
                "input_corpus_hash": input_hash,
                "output_hash": output_hash,
            },
        )

