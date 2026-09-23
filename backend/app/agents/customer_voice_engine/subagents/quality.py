"""VOICE-QA: Customer Voice Quality Assurance Specialist Sub-Agent.

Independent quality assurance, privacy, trace, bias, and coverage assurance evaluator.
Evaluates candidate outputs across residual PII, evidence traceability, bias (frequency vs prevalence),
contradiction preservation, coverage, and schema adherence.
Returns strictly non-mutating evaluations with status PASS | REVISE | BLOCK under DENY_ALL network policy.
"""

from __future__ import annotations

from typing import Any

from app.agents.customer_voice_engine.profiles import QA_PROFILE, SpecialistModelProfile
from app.schemas.customer_voice import VoiceWorkflowStage


class VoiceQualityAgent:
    """Specialist sub-agent for Customer Voice Quality Assurance (VOICE-QA)."""

    SPECIALIST_ID = "VOICE-QA"
    ROLE = VoiceWorkflowStage.QA

    def __init__(
        self,
        llm_client: Any = None,
        profile: SpecialistModelProfile | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._profile = profile or QA_PROFILE

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
        topics: list[Any] | None = None,
        aspect_sentiment: list[Any] | None = None,
        needs_and_objections: list[Any] | None = None,
        journey_comparisons: list[Any] | None = None,
        corpus_hash: str | None = None,
        survey_methodology: Any | None = None,
    ) -> Any:
        """Execute independent quality, privacy, and traceability evaluation for VOICE-QA.

        Enforces:
        - non-mutating evaluation (candidate pre/post hash verified identical)
        - checks: residual PII, evidence traceability, bias, contradictions, coverage, schema validity
        - verdict: PASS | REVISE | BLOCK
        - residual PII, broken evidence, or cross-tenant contamination -> BLOCK
        """
        import hashlib
        from app.integrations.sandbox.s_parse_core import evaluate_voice_qa_core
        from app.schemas.customer_voice import EvidenceSpan, VoiceQAReport, VoiceSpecialistResult

        tenant_id = getattr(task, "tenant_id", "default")
        task_id = getattr(task, "task_id", getattr(task, "parent_task_id", "task-qa"))

        records_dict = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in records]
        spans_dict = [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in evidence_spans]
        topics_dict = [t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in (topics or [])]
        aspects_dict = [a.model_dump() if hasattr(a, "model_dump") else dict(a) for a in (aspect_sentiment or [])]
        needs_dict = [n.model_dump() if hasattr(n, "model_dump") else dict(n) for n in (needs_and_objections or [])]
        journey_dict = [j.model_dump() if hasattr(j, "model_dump") else dict(j) for j in (journey_comparisons or [])]
        survey_dict = survey_methodology.model_dump() if hasattr(survey_methodology, "model_dump") else (dict(survey_methodology) if survey_methodology else None)

        candidate_input_hash = corpus_hash or hashlib.sha256(
            (str(records_dict) + str(spans_dict)).encode("utf-8")
        ).hexdigest()

        raw_qa = evaluate_voice_qa_core(
            candidate_input_hash=candidate_input_hash,
            records=records_dict,
            spans=spans_dict,
            topics=topics_dict,
            aspect_sentiment=aspects_dict,
            needs_and_objections=needs_dict,
            journey_comparisons=journey_dict,
            tenant_id=tenant_id,
            survey_methodology=survey_dict,
        )

        qa_report = VoiceQAReport.model_validate(raw_qa)
        out_bytes = qa_report.model_dump_json().encode("utf-8")
        output_hash = hashlib.sha256(out_bytes).hexdigest()

        return VoiceSpecialistResult(
            specialist_id=self.SPECIALIST_ID,
            task_id=task_id,
            stage=self.ROLE,
            success=qa_report.status == "PASS",
            input_hash=candidate_input_hash,
            output_hash=output_hash,
            findings=qa_report.findings,
            evidence_spans=[EvidenceSpan.model_validate(s) for s in spans_dict],
            records=[],
            artifacts=[f"qa:{task_id}:{output_hash[:12]}"],
            qa_report=qa_report,
            provenance={
                "specialist_id": self.SPECIALIST_ID,
                "role": self.ROLE.value,
                "task_id": task_id,
                "tenant_id": tenant_id,
                "qa_verdict": qa_report.status,
                "residual_pii_check": qa_report.residual_pii_check,
                "evidence_traceability_check": qa_report.evidence_traceability_check,
                "bias_check": qa_report.bias_check,
                "schema_validity_check": qa_report.schema_validity_check,
                "candidate_input_hash": candidate_input_hash,
                "candidate_output_hash": qa_report.candidate_output_hash,
            },
        )

