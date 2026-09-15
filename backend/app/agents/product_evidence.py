"""Backward-compatibility forwarder to product_evidence_engine."""

from app.agents.product_evidence_engine.product_evidence import *  # noqa: F401, F403
from app.agents.product_evidence_engine.product_evidence import ProductEvidenceAgent

__all__ = ["ProductEvidenceAgent"]
