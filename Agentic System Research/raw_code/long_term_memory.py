# File: long_term_memory.py
"""
Layer 4: Long-Term Memory.

Durable institutional knowledge:
- Persistent knowledge store partitioned by tenant and namespace.
- Direct worker/sub-agent mutations are strictly prohibited.
- Governed promotion workflow: proposals require explicit review/approval.
- Access mediated via policy-filtered retrieval.
"""

from __future__ import annotations

import dataclasses
import enum
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from audit_provenance import ImmutableAuditLedger

logger = logging.getLogger("long_term_memory")


class MemoryNamespace(str, enum.Enum):
    """Namespaces for durable institutional knowledge."""
    BRAND_RULES = "brand_rules"
    ATTRIBUTION_HEURISTICS = "attribution_heuristics"
    REGULATORY_POLICIES = "regulatory_policies"
    NEGATIVE_CONSTRAINTS = "negative_constraints"
    PRODUCT_SPECS = "product_specs"


@dataclasses.dataclass(frozen=True)
class MemoryItem:
    item_id: str
    tenant_id: str
    brand_id: str
    namespace: MemoryNamespace
    title: str
    content: str
    version: int
    effective_timestamp: datetime
    promoted_by: str
    promotion_justification: str
    provenance_ref: str
    is_active: bool = True
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class PromotionProposal:
    proposal_id: str
    tenant_id: str
    brand_id: str
    namespace: MemoryNamespace
    title: str
    content: str
    justification: str
    proposing_agent_id: str
    created_at: datetime
    is_reviewed: bool = False
    is_approved: bool = False
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None


class InstitutionalMemoryStore:
    """
    Central-authority-owned institutional memory.
    Workers propose promotions; central authority reviews and promotes.
    """

    def __init__(self, audit_ledger: Optional[ImmutableAuditLedger] = None):
        self.audit_ledger = audit_ledger
        self._items: Dict[str, MemoryItem] = {}
        self._proposals: Dict[str, PromotionProposal] = {}

    def propose_promotion(self, tenant_id: str, brand_id: str, namespace: MemoryNamespace,
                          title: str, content: str, justification: str,
                          proposing_agent_id: str) -> PromotionProposal:
        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        proposal = PromotionProposal(
            proposal_id=proposal_id,
            tenant_id=tenant_id,
            brand_id=brand_id,
            namespace=namespace,
            title=title,
            content=content,
            justification=justification,
            proposing_agent_id=proposing_agent_id,
            created_at=datetime.now(timezone.utc)
        )
        self._proposals[proposal_id] = proposal

        if self.audit_ledger:
            self.audit_ledger.append_entry(
                actor_id=proposing_agent_id,
                action_type="MEMORY_PROMOTION_PROPOSED",
                details={
                    "proposal_id": proposal_id,
                    "tenant_id": tenant_id,
                    "namespace": namespace.value,
                    "title": title
                }
            )

        logger.info("Promotion proposal %s registered by %s (namespace: %s)",
                    proposal_id, proposing_agent_id, namespace.value)
        return proposal

    def review_promotion(self, proposal_id: str, reviewer_id: str,
                         approved: bool, review_notes: str,
                         provenance_ref: str = "") -> Optional[MemoryItem]:
        if proposal_id not in self._proposals:
            raise KeyError(f"Proposal '{proposal_id}' not found.")
        proposal = self._proposals[proposal_id]
        if proposal.is_reviewed:
            raise ValueError(f"Proposal '{proposal_id}' has already been reviewed.")

        proposal.is_reviewed = True
        proposal.is_approved = approved
        proposal.reviewed_by = reviewer_id
        proposal.review_notes = review_notes

        if not approved:
            if self.audit_ledger:
                self.audit_ledger.append_entry(
                    actor_id=reviewer_id,
                    action_type="MEMORY_PROMOTION_REJECTED",
                    details={"proposal_id": proposal_id, "reviewer": reviewer_id, "notes": review_notes}
                )
            logger.info("Promotion proposal %s rejected by %s: %s", proposal_id, reviewer_id, review_notes)
            return None

        # Create promoted durable item
        item_id = f"mem_{uuid.uuid4().hex[:12]}"
        item = MemoryItem(
            item_id=item_id,
            tenant_id=proposal.tenant_id,
            brand_id=proposal.brand_id,
            namespace=proposal.namespace,
            title=proposal.title,
            content=proposal.content,
            version=1,
            effective_timestamp=datetime.now(timezone.utc),
            promoted_by=reviewer_id,
            promotion_justification=proposal.justification,
            provenance_ref=provenance_ref or f"proposal:{proposal_id}",
            is_active=True
        )
        self._items[item_id] = item

        if self.audit_ledger:
            self.audit_ledger.record_entity(item_id, "InstitutionalMemoryItem", {"title": proposal.title, "namespace": proposal.namespace.value})
            self.audit_ledger.append_entry(
                actor_id=reviewer_id,
                action_type="MEMORY_PROMOTION_APPROVED",
                details={
                    "item_id": item_id,
                    "proposal_id": proposal_id,
                    "reviewer": reviewer_id,
                    "namespace": proposal.namespace.value
                }
            )

        logger.info("Promotion proposal %s APPROVED. Persisted institutional memory item %s.",
                    proposal_id, item_id)
        return item

    def direct_write_blocked(self, agent_id: str) -> None:
        """Explicitly prohibits direct writes from workers or sub-agents."""
        raise PermissionError(f"Direct writes to institutional memory blocked for agent '{agent_id}'. Use propose_promotion().")

    def query(self, tenant_id: str, namespace: MemoryNamespace,
              filter_query: Optional[str] = None) -> List[MemoryItem]:
        results: List[MemoryItem] = []
        for item in self._items.values():
            if item.tenant_id != tenant_id or not item.is_active:
                continue
            if item.namespace != namespace:
                continue
            if filter_query:
                tokens = set(re.findall(r"\w+", filter_query.lower()))
                item_tokens = set(re.findall(r"\w+", (item.title + " " + item.content).lower()))
                if not tokens.intersection(item_tokens):
                    continue
            results.append(item)
        return results