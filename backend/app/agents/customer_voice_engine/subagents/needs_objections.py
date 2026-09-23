"""VOICE-NEEDS: Customer Voice Needs & Objections Specialist Sub-Agent.

Responsible for extracting customer needs, pains, objections, and desired outcomes,
grounding findings in exact evidence spans and preserving customer vocabulary under DENY_ALL network policy.
"""

from __future__ import annotations

from typing import Any

from app.agents.customer_voice_engine.profiles import NEEDS_PROFILE, SpecialistModelProfile
from app.schemas.customer_voice import VoiceWorkflowStage


class VoiceNeedsAgent:
    """Specialist sub-agent for Customer Voice Needs & Objections (VOICE-NEEDS)."""

    SPECIALIST_ID = "VOICE-NEEDS"
    ROLE = VoiceWorkflowStage.NEEDS

    def __init__(
        self,
        llm_client: Any = None,
        profile: SpecialistModelProfile | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._profile = profile or NEEDS_PROFILE

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
    ) -> Any:
        """Execute needs, pains, objections, and customer vocabulary extraction for VOICE-NEEDS.

        Preserves:
        - grounded evidence spans
        - exact customer vocabulary extraction
        - frequency and impact severity
        - no demographic inference, causality, or population prevalence
        """
        import hashlib
        from app.integrations.sandbox.s_parse_core import analyze_needs_objections_core
        from app.schemas.customer_voice import EvidenceSpan, NeedObjectionFinding, VoiceSpecialistResult

        tenant_id = getattr(task, "tenant_id", "default")
        task_id = getattr(task, "task_id", getattr(task, "parent_task_id", "task-needs"))

        records_dict = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in records]
        spans_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in evidence_spans]

        input_hash = corpus_hash or hashlib.sha256(
            (str(records_dict) + str(spans_dict)).encode("utf-8")
        ).hexdigest()

        raw_needs = analyze_needs_objections_core(
            records=records_dict,
            spans=spans_dict,
        )

        needs_findings = [NeedObjectionFinding.model_validate(n) for n in raw_needs]
        out_bytes = str([n.model_dump() for n in needs_findings]).encode("utf-8")
        output_hash = hashlib.sha256(out_bytes).hexdigest()

        return VoiceSpecialistResult(
            specialist_id=self.SPECIALIST_ID,
            task_id=task_id,
            stage=self.ROLE,
            success=True,
            input_hash=input_hash,
            output_hash=output_hash,
            findings=needs_findings,
            evidence_spans=[EvidenceSpan.model_validate(s) for s in spans_dict],
            records=[],
            artifacts=[f"needs:{task_id}:{output_hash[:12]}"],
            provenance={
                "specialist_id": self.SPECIALIST_ID,
                "role": self.ROLE.value,
                "task_id": task_id,
                "tenant_id": tenant_id,
                "records_analyzed": len(records),
                "needs_and_objections_count": len(needs_findings),
                "input_corpus_hash": input_hash,
                "output_hash": output_hash,
            },
        )

