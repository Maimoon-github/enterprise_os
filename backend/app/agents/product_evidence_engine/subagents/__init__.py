"""The six bounded specialist sub-agents of W_PROD under S_VAL."""

from app.agents.product_evidence_engine.subagents.appraisal import ProductAppraisalAgent
from app.agents.product_evidence_engine.subagents.claims import ProductClaimsAgent
from app.agents.product_evidence_engine.subagents.discovery import ProductDiscoveryAgent
from app.agents.product_evidence_engine.subagents.product_lab import ProductLabAgent
from app.agents.product_evidence_engine.subagents.regulatory import ProductRegulatoryAgent
from app.agents.product_evidence_engine.subagents.safety import ProductSafetyAgent

__all__ = [
    "ProductAppraisalAgent",
    "ProductClaimsAgent",
    "ProductDiscoveryAgent",
    "ProductLabAgent",
    "ProductRegulatoryAgent",
    "ProductSafetyAgent",
]
