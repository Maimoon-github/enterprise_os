"""VOICE-DISCOVERY: Customer Voice Discovery Specialist Sub-Agent.

Responsible for approved own-brand source acquisition, record normalization,
language identification, deterministic PII handling, and deduplication coordination.
Only specialist with ALLOWLIST network egress for authorized source acquisition.
"""

from __future__ import annotations

from typing import Any

from app.agents.customer_voice_engine.profiles import DISCOVERY_PROFILE, SpecialistModelProfile
from app.schemas.customer_voice import VoiceWorkflowStage


class VoiceDiscoveryAgent:
    """Specialist sub-agent for Customer Voice Discovery (VOICE-DISCOVERY)."""

    SPECIALIST_ID = "VOICE-DISCOVERY"
    ROLE = VoiceWorkflowStage.DISCOVERY

    def __init__(
        self,
        llm_client: Any = None,
        profile: SpecialistModelProfile | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._profile = profile or DISCOVERY_PROFILE

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
        raw_items: list[dict[str, Any]],
        *,
        sandbox_client: Any = None,
        egress_grant: Any = None,
        hmac_key: str | None = None,
    ) -> Any:
        """Execute Discovery and Sanitization Pipeline for VOICE-DISCOVERY.

        Dispatches raw items to deterministic de-identification, language detection,
        injection neutralization, deduplication, and evidence span indexing.
        Produces strongly typed VoiceSpecialistResult containing sanitized FeedbackRecords,
        EvidenceSpans, and canonical immutable_corpus_hash before any downstream agent
        receives customer text.
        """
        import hashlib
        from app.integrations.sandbox.s_parse_core import run_discovery_sanitization_pipeline
        from app.schemas.customer_voice import EvidenceSpan, FeedbackRecord, VoiceSpecialistResult

        tenant_id = getattr(task, "tenant_id", "default")
        task_id = getattr(task, "task_id", getattr(task, "parent_task_id", "task-discovery"))

        input_hash = hashlib.sha256(str(raw_items).encode("utf-8")).hexdigest()

        # Execute through isolated preprocessing pipeline
        pipeline_res = run_discovery_sanitization_pipeline(
            raw_items=raw_items,
            tenant_id=tenant_id,
            task_id=task_id,
            hmac_key=hmac_key,
        )

        records = [FeedbackRecord.model_validate(r) for r in pipeline_res.get("records", [])]
        spans = [EvidenceSpan.model_validate(s) for s in pipeline_res.get("evidence_spans", [])]
        corpus_hash = pipeline_res.get("immutable_corpus_hash", "")

        return VoiceSpecialistResult(
            specialist_id=self.SPECIALIST_ID,
            task_id=task_id,
            stage=self.ROLE,
            success=pipeline_res.get("status") == "success",
            input_hash=input_hash,
            output_hash=corpus_hash,
            findings=[
                f"Discovery & Sanitization completed: {len(records)} records de-identified and indexed.",
                f"Immutable Corpus Hash: {corpus_hash}",
            ],
            evidence_spans=spans,
            records=records,
            artifacts=[f"corpus:{task_id}:{corpus_hash[:12]}"],
            provenance={
                "specialist_id": self.SPECIALIST_ID,
                "role": self.ROLE.value,
                "task_id": task_id,
                "tenant_id": tenant_id,
                "records_analyzed": len(records),
                "immutable_corpus_hash": corpus_hash,
            },
        )

