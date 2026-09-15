"""Backward-compatibility forwarder to competitor_intel_engine."""

from app.agents.competitor_intel_engine.competitor_intel import *  # noqa: F401, F403
from app.agents.competitor_intel_engine.competitor_intel import CompetitorIntelAgent

__all__ = ["CompetitorIntelAgent"]
