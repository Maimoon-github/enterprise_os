"""Backward-compatibility forwarder to customer_voice_engine."""

from app.agents.customer_voice_engine.customer_voice import *  # noqa: F401, F403
from app.agents.customer_voice_engine.customer_voice import CustomerVoiceAgent

__all__ = ["CustomerVoiceAgent"]
