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
