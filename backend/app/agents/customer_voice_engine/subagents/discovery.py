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
