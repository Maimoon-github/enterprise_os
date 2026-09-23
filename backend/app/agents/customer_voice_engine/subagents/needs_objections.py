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
