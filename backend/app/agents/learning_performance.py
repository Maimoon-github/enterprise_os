"""Backward-compatibility forwarder to learning_performance_engine."""

from app.agents.learning_performance_engine.learning_performance import *  # noqa: F401, F403
from app.agents.learning_performance_engine.learning_performance import LearningPerformanceAgent

__all__ = ["LearningPerformanceAgent"]
