"""Promotes validated learning deltas into institutional memory."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from app.core.exceptions import PolicyViolationError
from app.persistence.repositories.memory import (
    MemoryNamespace,
    MemoryRecord,
    MemoryRepository,
)
from app.schemas.agent_contracts import (
    LearningPromotionProposal,
    PromotionResult,
)
from app.schemas.governance import RiskLevel, TenantScope
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.authorization_boundary import CallerIdentity

if TYPE_CHECKING:
    from app.mcp.data_gateway import DataGateway
    from app.services.provenance import ProvenanceRecorder
    from app.services.task_state import TaskStateService

logger = logging.getLogger(__name__)

_MIN_PROMOTION_CONFIDENCE = 0.7


class MemoryPromotionService:
    """Promotes a validated learning delta once it clears a confidence bar."""

    def __init__(
        self,
        repository: MemoryRepository | None = None,
        *,
        data_gateway: DataGateway | None = None,
        task_state_service: TaskStateService | None = None,
        provenance_recorder: ProvenanceRecorder | None = None,
        min_confidence: float = _MIN_PROMOTION_CONFIDENCE,
    ) -> None:
        self._repository = repository
        self._data_gateway = data_gateway
        self._task_state_service = task_state_service
        self._provenance_recorder = provenance_recorder
        self._min_confidence = min_confidence

    async def promote(
        self,
        *,
        tenant_id: str,
        category: str,
        statement: str,
        confidence: float,
        source_task_ids: list[str],
        brand_id: str | None = None,
        namespace: str = "brand_rules",
        justification: str = "",
        logical_id: str | None = None,
        version: int = 1,
        supersedes: str | None = None,
        session: Any = None,
    ) -> MemoryRecord | None:
        """Promote and persist a learning delta, or return None if not validated."""
        if confidence < self._min_confidence:
            return None

        record = MemoryRecord(
            memory_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            brand_id=brand_id,
            category=category,
            namespace=namespace,
            statement=statement,
            confidence=confidence,
            logical_id=logical_id,
            version=version,
            supersedes=supersedes,
            promotion_justification=justification,
            source_task_ids=source_task_ids,
        )
        if self._data_gateway is not None:
            caller = CallerIdentity(
                subject="intelligence_engine",
                tenant_scope=TenantScope(tenant_id=tenant_id),
                risk_ceiling=RiskLevel.MEDIUM,
            )
            await self._data_gateway.promote_memory(caller, tenant_id=tenant_id, record=record)
        elif self._repository is not None:
            if session is not None:
                try:
                    await self._repository.promote(record, session=session)
                except TypeError:
                    await self._repository.promote(record)
            else:
                await self._repository.promote(record)
        return record

    async def validate_and_promote(
        self,
        proposal: LearningPromotionProposal,
        *,
        task_states: dict[str, CanonicalTaskState],
        caller: CallerIdentity,
        governing_task_id: str = "task-t32",
    ) -> PromotionResult:
        """Centrally validate and promote a learning delta proposal from W_LEARN into Institutional Memory."""
        # 1. Verify Caller Authority
        subj_lower = caller.subject.lower()
        if (
            caller.subject.startswith("W_")
            or caller.subject.startswith("S_")
            or "worker" in subj_lower
            or "specialist" in subj_lower
        ):
            raise PolicyViolationError(
                "Direct worker memory mutation forbidden; mutations must be authorized and committed by Intelligence Engine"
            )

        # 2. Verify Proposing Agent
        if not proposal.proposing_agent or (
            not proposal.proposing_agent.startswith("W_")
            and "learning" not in proposal.proposing_agent.lower()
        ):
            raise ValueError(f"Unauthorized proposing agent: '{proposal.proposing_agent}'")

        # 3. Verify T31 Prerequisite
        if proposal.source_task_id not in task_states:
            raise ValueError(
                f"Authoritative T31 acceptance required: source task '{proposal.source_task_id}' not found in task states"
            )

        t31_task = task_states[proposal.source_task_id]
        if t31_task.status != TaskStatus.COMPLETED:
            raise ValueError(
                f"Authoritative T31 acceptance required: task '{proposal.source_task_id}' status is '{t31_task.status}', expected COMPLETED"
            )

        # Check if marked t32_eligible or has valid attribution deliverable
        is_eligible = t31_task.cts_state.get("t32_eligible", False)
        deliverable_dict = t31_task.cts_state.get("attribution_deliverable")
        if not is_eligible and not deliverable_dict:
            raise ValueError(
                f"T31 task '{proposal.source_task_id}' is not marked t32_eligible or lacks attribution deliverable"
            )

        # Check evidence integrity
        if not proposal.evidence_references and not deliverable_dict:
            raise ValueError(
                f"T31 evidence integrity failure: no evidence references supplied for proposal '{proposal.proposal_id}'"
            )

        # 4. Verify Tenant & Brand Scope
        t31_tenant = t31_task.cts_state.get("tenant_id") if hasattr(t31_task, "cts_state") else getattr(t31_task, "tenant_id", None)
        if t31_tenant and proposal.tenant_id != t31_tenant:
            raise ValueError(
                f"Tenant scope mismatch: proposal tenant '{proposal.tenant_id}' does not match T31 task tenant '{t31_tenant}'"
            )

        if caller.tenant_scope.tenant_id != proposal.tenant_id and caller.tenant_scope.tenant_id != "*":
            raise ValueError(
                f"Caller tenant scope '{caller.tenant_scope.tenant_id}' does not match proposal tenant '{proposal.tenant_id}'"
            )

        # 5. Verify Allowed Memory Namespace
        allowed_namespaces = {m.value for m in MemoryNamespace}
        if proposal.namespace not in allowed_namespaces:
            raise ValueError(
                f"Invalid memory namespace '{proposal.namespace}'. Allowed namespaces: {sorted(list(allowed_namespaces))}"
            )

        # 6. Audit Proposal Submission
        if self._provenance_recorder is not None:
            try:
                await self._provenance_recorder.record(
                    tenant_id=proposal.tenant_id,
                    entity_id=proposal.proposal_id,
                    activity="learning_delta_proposed",
                    agent=proposal.proposing_agent,
                    metadata={
                        "source_task_id": proposal.source_task_id,
                        "namespace": proposal.namespace,
                        "confidence": proposal.confidence,
                        "statement": proposal.statement,
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record proposal provenance: %s", exc)

        # 7. Verify Required Confidence / Acceptance State
        if proposal.confidence < self._min_confidence:
            if self._provenance_recorder is not None:
                try:
                    await self._provenance_recorder.record(
                        tenant_id=proposal.tenant_id,
                        entity_id=proposal.proposal_id,
                        activity="learning_delta_rejected",
                        agent="IE",
                        metadata={
                            "reason": f"Confidence {proposal.confidence:.2f} below required threshold {self._min_confidence:.2f}",
                            "source_task_id": proposal.source_task_id,
                        },
                    )
                except Exception as exc:
                    logger.warning("Failed to record rejection provenance: %s", exc)
            return PromotionResult(
                proposal_id=proposal.proposal_id,
                memory_id="",
                namespace=proposal.namespace,
                status="rejected",
                source_task_id=proposal.source_task_id,
                message=f"Rejected: confidence {proposal.confidence:.2f} below threshold {self._min_confidence:.2f}",
            )

        # 8. Check Existing Memory (Deduplication / Idempotent Replay / Conflicts)
        existing_records: list[MemoryRecord] = []
        if self._data_gateway is not None:
            existing_records = await self._data_gateway.query_memory(
                caller, tenant_id=proposal.tenant_id, namespace=proposal.namespace
            )
        elif self._repository is not None and hasattr(self._repository, "list_by_tenant"):
            existing_records = await self._repository.list_by_tenant(
                proposal.tenant_id, namespace=proposal.namespace
            )

        norm_proposal = proposal.statement.strip().lower()
        for existing in existing_records:
            if existing.is_active and existing.statement.strip().lower() == norm_proposal:
                # Idempotent replay: identical active memory record already exists
                # Update CTS state without adding duplicate MEM records
                if governing_task_id in task_states:
                    t32_task = task_states[governing_task_id]
                    t32_task.status = TaskStatus.COMPLETED
                    t32_task.cts_state["promoted_memory_id"] = existing.memory_id
                    t32_task.cts_state["namespace"] = existing.namespace
                    t32_task.cts_state["source_task_id"] = proposal.source_task_id
                    t32_task.cts_state["t34_ready"] = True
                    if self._task_state_service is not None:
                        try:
                            await self._task_state_service.save_state(proposal.tenant_id, t32_task)
                        except Exception as exc:
                            logger.warning("Failed to save CTS state for %s: %s", governing_task_id, exc)

                return PromotionResult(
                    proposal_id=proposal.proposal_id,
                    memory_id=existing.memory_id,
                    namespace=existing.namespace,
                    status="idempotent_noop",
                    provenance_ref=existing.provenance_ref or f"prov-{existing.memory_id}",
                    source_task_id=proposal.source_task_id,
                    cts_state_delta={
                        "status": "COMPLETED",
                        "promoted_memory_id": existing.memory_id,
                        "t34_ready": True,
                    },
                    message="Idempotent: identical active learning delta already exists in institutional memory",
                )

        # 9. Governed Mutation through Data Boundary (MEM write)
        record_id = f"mem-{uuid.uuid4().hex[:12]}"
        prov_ref = f"prov-{proposal.proposal_id}"
        record = MemoryRecord(
            memory_id=record_id,
            tenant_id=proposal.tenant_id,
            brand_id=proposal.brand_id,
            category=proposal.category,
            namespace=proposal.namespace,
            statement=proposal.statement,
            confidence=proposal.confidence,
            title=f"Learned Delta: {proposal.category}",
            promoted_by="intelligence_engine",
            promotion_justification=proposal.justification,
            provenance_ref=prov_ref,
            is_active=True,
            metadata={
                "proposing_agent": proposal.proposing_agent,
                "method_version": proposal.method_version,
                "data_quality": proposal.data_quality_metadata,
                "evidence_references": proposal.evidence_references,
            },
            source_task_ids=[proposal.source_task_id],
        )

        if self._data_gateway is not None:
            await self._data_gateway.promote_memory(caller, tenant_id=proposal.tenant_id, record=record)
        elif self._repository is not None:
            await self._repository.promote(record, min_confidence=self._min_confidence)

        # 10. Update CTS State for T32
        if governing_task_id in task_states:
            t32_task = task_states[governing_task_id]
            t32_task.status = TaskStatus.COMPLETED
            t32_task.cts_state["promoted_memory_id"] = record.memory_id
            t32_task.cts_state["namespace"] = record.namespace
            t32_task.cts_state["source_task_id"] = proposal.source_task_id
            t32_task.cts_state["t34_ready"] = True
            if self._task_state_service is not None:
                try:
                    await self._task_state_service.save_state(proposal.tenant_id, t32_task)
                except Exception as exc:
                    logger.warning("Failed to save CTS state for %s: %s", governing_task_id, exc)

        # 11. Record Provenance
        if self._provenance_recorder is not None:
            try:
                await self._provenance_recorder.record(
                    tenant_id=proposal.tenant_id,
                    entity_id=record.memory_id,
                    activity="learning_delta_promoted",
                    agent="IE",
                    metadata={
                        "proposal_id": proposal.proposal_id,
                        "source_task_id": proposal.source_task_id,
                        "confidence": proposal.confidence,
                        "namespace": proposal.namespace,
                        "category": proposal.category,
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record promotion provenance: %s", exc)

        # 12. Return Promotion Result (IE only holds reference metadata, no shadow persistence)
        return PromotionResult(
            proposal_id=proposal.proposal_id,
            memory_id=record.memory_id,
            namespace=record.namespace,
            version=1,
            status="promoted",
            provenance_ref=prov_ref,
            source_task_id=proposal.source_task_id,
            cts_state_delta={
                "status": "COMPLETED",
                "promoted_memory_id": record.memory_id,
                "t34_ready": True,
            },
            message="Successfully promoted validated learning delta into Institutional Memory",
        )