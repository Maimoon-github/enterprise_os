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
