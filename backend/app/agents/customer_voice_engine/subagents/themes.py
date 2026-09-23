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
