"""VOICE-THEMES: Customer Voice Themes Specialist Sub-Agent.

Responsible for thematic reasoning, embeddings clustering, observed share estimation,
and topic trend extraction over the immutable sanitized corpus under DENY_ALL network policy.
"""

from __future__ import annotations

from typing import Any

from app.agents.customer_voice_engine.profiles import THEMES_PROFILE, SpecialistModelProfile
from app.schemas.customer_voice import VoiceWorkflowStage


class VoiceThemesAgent:
    """Specialist sub-agent for Customer Voice Themes (VOICE-THEMES)."""

    SPECIALIST_ID = "VOICE-THEMES"
    ROLE = VoiceWorkflowStage.THEMES

    def __init__(
        self,
        llm_client: Any = None,
        profile: SpecialistModelProfile | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._profile = profile or THEMES_PROFILE

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
        survey_methodology: Any | None = None,
    ) -> Any:
        """Execute thematic clustering and observed share analysis for VOICE-THEMES.

        Preserves:
        - observed_count and observed_share_of_analyzed_corpus
        - outlier_or_unassigned_rate
        - embedding model/version and cluster algorithm/parameters
        - cluster_diagnostics (silhouette proxy)
        - representative evidence spans
        - trend: 'not_assessed' (no frequency-only trend heuristics)
        - population inference omitted unless supplied survey methodology supports it
        """
        import hashlib
        from app.integrations.sandbox.s_parse_core import analyze_themes_core
        from app.schemas.customer_voice import EvidenceSpan, TopicFinding, VoiceSpecialistResult

        tenant_id = getattr(task, "tenant_id", "default")
        task_id = getattr(task, "task_id", getattr(task, "parent_task_id", "task-themes"))

        records_dict = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in records]
        spans_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in evidence_spans]
        survey_dict = survey_methodology.model_dump() if hasattr(survey_methodology, "model_dump") else (dict(survey_methodology) if survey_methodology else None)

        input_hash = corpus_hash or hashlib.sha256(
            (str(records_dict) + str(spans_dict)).encode("utf-8")
        ).hexdigest()

        raw_topics = analyze_themes_core(
            records=records_dict,
            spans=spans_dict,
            survey_methodology=survey_dict,
        )

        topic_findings = [TopicFinding.model_validate(t) for t in raw_topics]
        out_bytes = str([t.model_dump() for t in topic_findings]).encode("utf-8")
        output_hash = hashlib.sha256(out_bytes).hexdigest()

        return VoiceSpecialistResult(
            specialist_id=self.SPECIALIST_ID,
            task_id=task_id,
            stage=self.ROLE,
            success=True,
            input_hash=input_hash,
            output_hash=output_hash,
            findings=topic_findings,
            evidence_spans=[EvidenceSpan.model_validate(s) for s in spans_dict],
            records=[],
            artifacts=[f"themes:{task_id}:{output_hash[:12]}"],
            provenance={
                "specialist_id": self.SPECIALIST_ID,
                "role": self.ROLE.value,
                "task_id": task_id,
                "tenant_id": tenant_id,
                "records_analyzed": len(records),
                "topics_discovered": len(topic_findings),
                "input_corpus_hash": input_hash,
                "output_hash": output_hash,
            },
        )

