"""Unit and Integration Tests for Task-32 (T32): Promote Validated Learning Deltas.

Validates the governed promotion flow:
T31 validated evidence -> W_LEARN promotion proposal -> IE validation/authorization -> governed MCP data path -> MEM -> promotion result/reference -> IE/CTS

Guarantees:
- Authoritative T31 prerequisite validation (fails closed if missing, incomplete, or ineligible)
- Model A separation: W_LEARN proposes; IE authorizes and commits; direct worker writes to MEM fail closed
- Tenant and brand isolation
- Strict memory namespace enforcement
- Confidence threshold gating (min 0.70)
- Idempotent re-promotion / duplicate prevention
- Retention of T31 lineage, justification, method version, and W3C audit provenance
- Zero shadow memory storage inside IE or session state
- Zero T33 audit closeout execution
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import pytest

from app.agents.learning_performance import LearningPerformanceAgent
from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.client import SandboxClient
from app.mcp.data_gateway import DataGateway
from app.persistence.repositories.artifact import ArtifactReference
from app.persistence.repositories.memory import (
    MemoryNamespace,
    MemoryRecord,
    MemoryRepository,
)
from app.schemas.agent_contracts import (
    AttributionDeliverable,
    AttributionModelType,
    AttributionWeight,
    ConfidenceInterval,
    CreativeDecayMetric,
    DataQualityIndicator,
    EvidenceEnvelope,
    LearningPromotionProposal,
    PromotionResult,
    RoasMetric,
)
from app.schemas.governance import RiskLevel, TenantScope, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from app.services.memory_promotion import MemoryPromotionService
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class _FakeMemoryRepository(MemoryRepository):
    """In-memory stand-in for Institutional Memory Repository."""

    def __init__(self) -> None:
        self.promoted_records: list[MemoryRecord] = []

    async def promote(self, record: MemoryRecord, min_confidence: float = 0.6) -> None:
        if record.confidence < min_confidence:
            raise ValueError(
                f"Memory record confidence {record.confidence:.2f} is below threshold {min_confidence:.2f}"
            )
        self.promoted_records.append(record)

    async def list_by_tenant(
        self,
        tenant_id: str,
        category: str | None = None,
        namespace: str | None = None,
    ) -> list[MemoryRecord]:
        recs = [r for r in self.promoted_records if r.tenant_id == tenant_id]
        if category:
            recs = [r for r in recs if r.category == category]
        if namespace:
            recs = [r for r in recs if r.namespace == namespace]
        return recs

    def all(self) -> list[MemoryRecord]:
        return list(self.promoted_records)


class _FakeVectorRepository:
    """Minimal in-memory vector repository for DataGateway dependency."""

    async def similarity_search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def index_document(self, *args: Any, **kwargs: Any) -> None:
        pass


class _FakeTaskStateRepository:
    """In-memory task state store."""

    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task '{task_id}' not found.")
        return self.states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state


def _setup_t32_environment(
    tenant_id: str = "tenant-alpha",
    t31_status: TaskStatus = TaskStatus.COMPLETED,
    t31_eligible: bool = True,
    has_t31: bool = True,
) -> tuple[
    MemoryPromotionService,
    DataGateway,
    _FakeMemoryRepository,
    dict[str, CanonicalTaskState],
    FakeProvenanceRepository,
    CallerIdentity,
]:
    memory_repo = _FakeMemoryRepository()
    vector_repo = _FakeVectorRepository()
    task_repo = _FakeTaskStateRepository()
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    task_service = TaskStateService(task_repo, provenance_recorder=prov_recorder)

    data_gateway = DataGateway(
        vector_repository=vector_repo,  # type: ignore[arg-type]
        memory_repository=memory_repo,  # type: ignore[arg-type]
        provenance_recorder=prov_recorder,
    )

    service = MemoryPromotionService(
        repository=memory_repo,
        data_gateway=data_gateway,
        task_state_service=task_service,
        provenance_recorder=prov_recorder,
        min_confidence=0.70,
    )

    task_states: dict[str, CanonicalTaskState] = {}
    if has_t31:
        t31 = CanonicalTaskState(
            task_id="task-t31",
            directive_id="dir-t31",
            worker_role=WorkerRole.LEARNING_PERFORMANCE,
            status=t31_status,
            governance_approved=True,
            cts_state={
                "tenant_id": tenant_id,
                "t32_eligible": t31_eligible,
                "attribution_deliverable": {
                    "deliverable_id": "deliv-t31-001",
                    "tenant_id": tenant_id,
                    "task_id": "task-t31",
                    "status": "success",
                    "channel_weights": [{"channel": "meta", "weight_percentage": 55.0}],
                },
            },
        )
        task_states["task-t31"] = t31
        task_repo.states["task-t31"] = t31

    t32 = CanonicalTaskState(
        task_id="task-t32",
        directive_id="dir-t32",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        status=TaskStatus.IN_PROGRESS,
        governance_approved=True,
        cts_state={"tenant_id": tenant_id},
    )
    task_states["task-t32"] = t32
    task_repo.states["task-t32"] = t32

    ie_caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id=tenant_id),
        risk_ceiling=RiskLevel.HIGH,
    )

    return service, data_gateway, memory_repo, task_states, prov_repo, ie_caller


def _create_valid_proposal(
    tenant_id: str = "tenant-alpha",
    statement: str = "Meta drives 55% higher conversion efficiency during evening peak hours.",
    confidence: float = 0.85,
    namespace: str = MemoryNamespace.ATTRIBUTION_HEURISTICS.value,
) -> LearningPromotionProposal:
    return LearningPromotionProposal(
        proposal_id="prop-t32-001",
        tenant_id=tenant_id,
        brand_id="brand-alpha",
        namespace=namespace,
        category="attribution",
        statement=statement,
        justification="Verified by multi-touch attribution analysis over 14-day telemetry window.",
        source_task_id="task-t31",
        evidence_references=["ev-conv-001", "ev-spend-002"],
        method_version="1.0",
        confidence=confidence,
        data_quality_metadata={"attribution_coverage": 1.0, "total_events": 100},
        proposing_agent="W_LEARN",
    )


# ============================================================================
# 1. Authoritative T31 Prerequisite Validation
# ============================================================================

@pytest.mark.asyncio
async def test_t32_fails_closed_when_t31_missing() -> None:
    """T32 promotion fails closed if source task-t31 is missing from task states."""
    service, _, _, task_states, _, caller = _setup_t32_environment(has_t31=False)
    proposal = _create_valid_proposal()

    with pytest.raises(ValueError, match="Authoritative T31 acceptance required"):
        await service.validate_and_promote(proposal, task_states=task_states, caller=caller)


@pytest.mark.asyncio
async def test_t32_fails_closed_when_t31_incomplete() -> None:
    """T32 promotion fails closed if task-t31 is still in progress or failed."""
    service, _, _, task_states, _, caller = _setup_t32_environment(t31_status=TaskStatus.IN_PROGRESS)
    proposal = _create_valid_proposal()

    with pytest.raises(ValueError, match=r"(?i)Authoritative T31 acceptance required.*in_progress"):
        await service.validate_and_promote(proposal, task_states=task_states, caller=caller)


@pytest.mark.asyncio
async def test_t32_fails_closed_when_t31_not_eligible() -> None:
    """T32 promotion fails closed if task-t31 deliverable is not marked t32_eligible."""
    service, _, _, task_states, _, caller = _setup_t32_environment(t31_eligible=False)
    # Clear deliverable so neither flag is set
    task_states["task-t31"].cts_state["attribution_deliverable"] = None
    proposal = _create_valid_proposal()

    with pytest.raises(ValueError, match="not marked t32_eligible"):
        await service.validate_and_promote(proposal, task_states=task_states, caller=caller)


# ============================================================================
# 2. Model A Separation: Caller Authority & Direct Worker Write Rejections
# ============================================================================

@pytest.mark.asyncio
async def test_t32_rejects_direct_worker_write_to_promotion_service() -> None:
    """Direct invocation of promotion service by worker agent (W_LEARN) raises PolicyViolationError."""
    service, _, _, task_states, _, _ = _setup_t32_environment()
    proposal = _create_valid_proposal()

    worker_caller = CallerIdentity(
        subject="W_LEARN",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    with pytest.raises(PolicyViolationError, match="Direct worker memory mutation forbidden"):
        await service.validate_and_promote(proposal, task_states=task_states, caller=worker_caller)


@pytest.mark.asyncio
async def test_t32_rejects_direct_worker_write_to_data_gateway() -> None:
    """Direct invocation of DataGateway.promote_memory by worker or specialist raises PolicyViolationError."""
    _, data_gateway, _, _, _, _ = _setup_t32_environment()

    mem_record = MemoryRecord(
        memory_id="mem-direct-001",
        tenant_id="tenant-alpha",
        category="attribution",
        statement="Direct worker mutation attempt",
        confidence=0.9,
    )

    worker_caller = CallerIdentity(
        subject="W_LEARN",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    with pytest.raises(PolicyViolationError, match="Direct worker memory mutation forbidden"):
        await data_gateway.promote_memory(worker_caller, tenant_id="tenant-alpha", record=mem_record)

    specialist_caller = CallerIdentity(
        subject="S_ATTR",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    with pytest.raises(PolicyViolationError, match="Direct worker memory mutation forbidden"):
        await data_gateway.promote_memory(specialist_caller, tenant_id="tenant-alpha", record=mem_record)


# ============================================================================
# 3. Scope & Namespace Governance
# ============================================================================

@pytest.mark.asyncio
async def test_t32_enforces_tenant_and_brand_scope() -> None:
    """Promotion proposal targeting a different tenant from T31 is rejected."""
    service, _, _, task_states, _, caller = _setup_t32_environment()
    proposal = _create_valid_proposal(tenant_id="tenant-beta")

    with pytest.raises(ValueError, match="Tenant scope mismatch"):
        await service.validate_and_promote(proposal, task_states=task_states, caller=caller)


@pytest.mark.asyncio
async def test_t32_enforces_caller_tenant_scope() -> None:
    """Caller whose tenant scope does not cover proposal tenant is rejected."""
    service, _, _, task_states, _, _ = _setup_t32_environment()
    proposal = _create_valid_proposal(tenant_id="tenant-alpha")

    mismatched_caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id="tenant-gamma"),
        risk_ceiling=RiskLevel.HIGH,
    )

    with pytest.raises(ValueError, match="Caller tenant scope.*does not match"):
        await service.validate_and_promote(proposal, task_states=task_states, caller=mismatched_caller)


@pytest.mark.asyncio
async def test_t32_rejects_invalid_namespace() -> None:
    """Proposal with an unrecognized memory namespace is rejected."""
    service, _, _, task_states, _, caller = _setup_t32_environment()
    proposal = _create_valid_proposal(namespace="unregistered_custom_namespace")

    with pytest.raises(ValueError, match="Invalid memory namespace"):
        await service.validate_and_promote(proposal, task_states=task_states, caller=caller)


# ============================================================================
# 4. Confidence Gating & Audit Rejection
# ============================================================================

@pytest.mark.asyncio
async def test_t32_rejects_low_confidence_delta() -> None:
    """Delta below minimum threshold (0.70) is rejected, MEM has 0 records, audit records rejection."""
    service, _, memory_repo, task_states, prov_repo, caller = _setup_t32_environment()
    proposal = _create_valid_proposal(confidence=0.55)

    result = await service.validate_and_promote(proposal, task_states=task_states, caller=caller)

    assert isinstance(result, PromotionResult)
    assert result.status == "rejected"
    assert "below threshold" in result.message
    assert len(memory_repo.all()) == 0

    # Verify audit provenance recorded rejection
    records = prov_repo._chains.get("tenant-alpha", [])
    activities = [r.activity for r in records]
    assert "learning_delta_proposed" in activities
    assert "learning_delta_rejected" in activities
    assert "learning_delta_promoted" not in activities


# ============================================================================
# 5. Successful Governed Promotion & Lineage
# ============================================================================

@pytest.mark.asyncio
async def test_t32_successful_promotion_flow() -> None:
    """Full canonical promotion flow: validates, routes through DataGateway to MEM, updates CTS, logs W3C audit."""
    service, _, memory_repo, task_states, prov_repo, caller = _setup_t32_environment()
    proposal = _create_valid_proposal(confidence=0.88)

    result = await service.validate_and_promote(proposal, task_states=task_states, caller=caller)

    # 1. Promotion result verification
    assert isinstance(result, PromotionResult)
    assert result.status == "promoted"
    assert result.memory_id.startswith("mem-")
    assert result.namespace == MemoryNamespace.ATTRIBUTION_HEURISTICS.value
    assert result.source_task_id == "task-t31"

    # 2. Institutional Memory repository record verification
    assert len(memory_repo.all()) == 1
    stored = memory_repo.all()[0]
    assert stored.memory_id == result.memory_id
    assert stored.tenant_id == "tenant-alpha"
    assert stored.namespace == MemoryNamespace.ATTRIBUTION_HEURISTICS.value
    assert stored.statement == proposal.statement
    assert stored.confidence == 0.88
    assert stored.promoted_by == "intelligence_engine"
    assert "task-t31" in stored.source_task_ids
    assert stored.metadata.get("proposing_agent") == "W_LEARN"
    assert stored.metadata.get("method_version") == "1.0"
    assert stored.promotion_justification == proposal.justification

    # 3. Canonical Task State (CTS) verification
    t32_task = task_states["task-t32"]
    assert t32_task.status == TaskStatus.COMPLETED
    assert t32_task.cts_state["promoted_memory_id"] == result.memory_id
    assert t32_task.cts_state["namespace"] == result.namespace
    assert t32_task.cts_state["t34_ready"] is True

    # 4. Provenance chain verification
    records = prov_repo._chains.get("tenant-alpha", [])
    activities = [r.activity for r in records]
    assert "learning_delta_proposed" in activities
    assert "learning_delta_promoted" in activities


# ============================================================================
# 6. Idempotency & Deduplication
# ============================================================================

@pytest.mark.asyncio
async def test_t32_idempotent_replay_no_duplicates() -> None:
    """Replaying an identical learning delta returns idempotent_noop without inserting extra rows in MEM."""
    service, _, memory_repo, task_states, _, caller = _setup_t32_environment()
    proposal = _create_valid_proposal(statement="Repeated attribution delta statement")

    # First promotion
    res1 = await service.validate_and_promote(proposal, task_states=task_states, caller=caller)
    assert res1.status == "promoted"
    assert len(memory_repo.all()) == 1
    first_mem_id = res1.memory_id

    # Replay with identical statement
    proposal_replay = _create_valid_proposal(statement="Repeated attribution delta statement")
    proposal_replay.proposal_id = "prop-replay-002"

    res2 = await service.validate_and_promote(proposal_replay, task_states=task_states, caller=caller)
    assert res2.status == "idempotent_noop"
    assert res2.memory_id == first_mem_id
    assert "idempotent" in res2.message.lower()

    # Crucial assertion: ZERO duplicate records in Institutional Memory!
    assert len(memory_repo.all()) == 1


# ============================================================================
# 7. Model A: Zero Shadow Memory Copy in IE
# ============================================================================

@pytest.mark.asyncio
async def test_t32_zero_shadow_memory_copy_in_ie() -> None:
    """IE receives only lightweight reference identifiers, never holding a durable shadow copy of MEM."""
    service, _, _, task_states, _, caller = _setup_t32_environment()
    proposal = _create_valid_proposal()

    result = await service.validate_and_promote(proposal, task_states=task_states, caller=caller)

    # Check PromotionResult contains only references
    assert hasattr(result, "memory_id")
    assert hasattr(result, "namespace")
    assert hasattr(result, "provenance_ref")

    # Ensure result does not contain durable repository collections or payload blobs
    result_dict = result.model_dump()
    assert "database" not in result_dict
    assert "repository" not in result_dict

    # Check CTS state only stores the ID reference
    t32_cts = task_states["task-t32"].cts_state
    assert isinstance(t32_cts["promoted_memory_id"], str)
    assert "memory_records" not in t32_cts
    assert "all_memories" not in t32_cts


# ============================================================================
# 8. Boundary Isolation: Zero T33 Audit-Closeout Execution
# ============================================================================

@pytest.mark.asyncio
async def test_t32_zero_t33_execution() -> None:
    """T32 promotes memory deltas but strictly triggers zero T33 audit closeout or financial execution."""
    service, _, _, task_states, prov_repo, caller = _setup_t32_environment()
    proposal = _create_valid_proposal()

    await service.validate_and_promote(proposal, task_states=task_states, caller=caller)

    # Check no T33 task created or executed
    assert "task-t33" not in task_states

    # Check no T33 provenance recorded
    records = prov_repo._chains.get("tenant-alpha", [])
    for r in records:
        assert "t33" not in r.activity.lower()
        assert "closeout" not in r.activity.lower()
        assert "audit_reconciliation" not in r.activity.lower()


# ============================================================================
# 9. W_LEARN Proposal Builder Integration
# ============================================================================

@pytest.mark.asyncio
async def test_w_learn_build_promotion_proposal() -> None:
    """W_LEARN agent can formulate structured LearningPromotionProposal from AttributionDeliverable."""
    sandbox_client = SandboxClient()
    agent = LearningPerformanceAgent(sandbox_client)

    envelope = EvidenceEnvelope(
        task_id="task-t31",
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        findings=["Meta ROAS is 3.5x"],
        evidence=["Channel Meta delivered 100 conversions", "Cost per conversion was $12"],
        confidence=ConfidenceInterval(point_estimate=0.86, lower_bound=0.76, upper_bound=0.91),
        proposed_state_changes={"learning_delta": "Allocate +15% budget to Meta evening peak."},
    )

    deliverable = AttributionDeliverable(
        deliverable_id="deliv-001",
        tenant_id="tenant-alpha",
        task_id="task-t31",
        model_type=AttributionModelType.LINEAR,
        channel_weights=[AttributionWeight(channel="meta", weight_percentage=60.0)],
        proposed_learning_deltas=["Allocate +15% budget to Meta evening peak."],
        confidence=ConfidenceInterval(point_estimate=0.86, lower_bound=0.76, upper_bound=0.91),
        data_quality=DataQualityIndicator(total_events=50, attribution_coverage=1.0),
    )

    proposal = agent.build_promotion_proposal(
        envelope,
        deliverable,
        brand_id="brand-alpha",
        namespace=MemoryNamespace.ATTRIBUTION_HEURISTICS.value,
    )

    assert isinstance(proposal, LearningPromotionProposal)
    assert proposal.tenant_id == "tenant-alpha"
    assert proposal.brand_id == "brand-alpha"
    assert proposal.namespace == "attribution_heuristics"
    assert proposal.statement == "Allocate +15% budget to Meta evening peak."
    assert proposal.confidence == 0.86
    assert proposal.proposing_agent == "W_LEARN"
    assert proposal.source_task_id == "task-t31"
    assert len(proposal.evidence_references) == 2


# ============================================================================
# 10. Backwards Compatibility for MemoryPromotionService.promote()
# ============================================================================

@pytest.mark.asyncio
async def test_memory_promotion_service_backwards_compatibility() -> None:
    """Existing service.promote() signature continues to work seamlessly."""
    memory_repo = _FakeMemoryRepository()
    service = MemoryPromotionService(memory_repo, min_confidence=0.70)

    # Below threshold
    low = await service.promote(
        tenant_id="tenant-alpha",
        category="attribution",
        statement="Low confidence test statement",
        confidence=0.5,
        source_task_ids=["task-t31"],
    )
    assert low is None
    assert len(memory_repo.all()) == 0

    # Above threshold
    high = await service.promote(
        tenant_id="tenant-alpha",
        category="attribution",
        statement="High confidence test statement",
        confidence=0.85,
        source_task_ids=["task-t31"],
    )
    assert high is not None
    assert len(memory_repo.all()) == 1
    assert high.statement == "High confidence test statement"