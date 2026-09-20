"""Unit tests for Task T15: Intelligence Engine Context Assembly and Brand Persona Layer.

Verifies the 9-stage deterministic precedence model:
1. Authority & tenant scope
2. CTS task state / holds / dependencies
3. Policy and risk constraints
4. Brand persona and brand rules (subordinate to policy)
5. Fresh RAG evidence + provenance
6. Task-specific instructions
7. Tool/capability allowlist
8. Token/context budget
9. Expected output schema
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import PolicyViolationError, RetrievalGovernanceError
from app.orchestration.brand_persona import BrandPersona, BrandPersonaResolver
from app.orchestration.context_assembly import ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import IntelligenceEngineToken, RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.agent_contracts import ContextRequest, TaskGrant
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskDependency, TaskStatus
from app.services.hitl import HitlCoordinator
from app.services.provenance import ProvenanceRecorder
from app.services.rag.controller import RagController
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient


@pytest.fixture
def mock_rag_controller() -> RagController:
    controller = RagController(retriever=AsyncMock())
    return controller


@pytest.fixture
def rag_dispatcher(mock_rag_controller: RagController) -> RagQueryDispatcher:
    return RagQueryDispatcher(mock_rag_controller)


@pytest.fixture
def brand_resolver() -> BrandPersonaResolver:
    resolver = BrandPersonaResolver()
    resolver.register(
        BrandPersona(
            tenant_id="tenant-alpha",
            brand_id="brand-premium",
            voice="authoritative and sleek",
            version="2.1",
            prohibited_terms=("cheap", "discount"),
            required_disclaimers=("*Results verified under clinical testing.",),
            tone_attributes=("bold", "precise"),
        )
    )
    resolver.register(
        BrandPersona(
            tenant_id="tenant-alpha",
            brand_id="brand-budget",
            voice="approachable and friendly",
            version="1.0",
            prohibited_terms=("exclusive",),
            required_disclaimers=(),
            tone_attributes=("warm", "simple"),
        )
    )
    resolver.register(
        BrandPersona(
            tenant_id="tenant-beta",
            brand_id="default",
            voice="scientific and cautious",
            version="1.0",
            prohibited_terms=("cure-all",),
            required_disclaimers=("*Subject to doctor consultation.",),
        )
    )
    return resolver


@pytest.fixture
def context_assembler(
    rag_dispatcher: RagQueryDispatcher, brand_resolver: BrandPersonaResolver
) -> ContextAssembler:
    return ContextAssembler(rag_dispatcher, brand_resolver)


@pytest.fixture
def intelligence_engine(
    context_assembler: ContextAssembler,
) -> IntelligenceEngine:
    from app.agents.base import BoundedWorkerAgent
    from app.agents.creative_content import CreativeContentAgent
    from app.agents.development import DevelopmentAgent

    fake_sandbox = FakeSandboxClient()
    workers: dict[WorkerRole, BoundedWorkerAgent] = {
        WorkerRole.CREATIVE_CONTENT: CreativeContentAgent(),
        WorkerRole.DEVELOPMENT: DevelopmentAgent(fake_sandbox),
    }

    return IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=context_assembler,
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=AsyncMock(),
        provenance_recorder=ProvenanceRecorder(FakeProvenanceRepository()),
        workers=workers,
    )


# --------------------------------------------------------------------------
# 1. Valid Context Assembly & Bounded Task Grant Generation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_context_assembly_and_grant(
    intelligence_engine: IntelligenceEngine,
    mock_rag_controller: RagController,
) -> None:
    now = datetime.now(UTC)
    mock_rag_controller.retrieve = AsyncMock(
        return_value=[
            {
                "doc_id": "doc-101",
                "tenant_id": "tenant-alpha",
                "text": "Target audience engagement surged 45% in Q3.",
                "source": "analytics_mcp",
                "provenance_hash": "hash-101",
                "retrieved_at": now - timedelta(days=2),
            }
        ]
    )

    directive = Directive(
        directive_id="dir-alpha-1",
        tenant_id="tenant-alpha",
        objective="Draft high-converting ad hooks for summer campaign.",
        budget_cap=8000.0,
        risk_ceiling=RiskLevel.LOW,
        scope=TenantScope(tenant_id="tenant-alpha", brand_ids=["brand-premium"]),
    )

    task = CanonicalTaskState(
        task_id=str(uuid.uuid4()),
        directive_id=directive.directive_id,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.PENDING,
        governance_approved=True,
    )

    grant, context = await intelligence_engine.assemble_task_grant(
        directive,
        task,
        query="summer campaign copy performance",
        brand_id="brand-premium",
    )

    # Validate TaskGrant typed contract
    assert isinstance(grant, TaskGrant)
    assert grant.task_id == task.task_id
    assert grant.worker_role == WorkerRole.CREATIVE_CONTENT
    assert grant.tenant_scope.tenant_id == "tenant-alpha"
    assert grant.brand_id == "brand-premium"
    assert grant.sandbox_capabilities == []
    assert grant.tool_permissions == []
    assert len(grant.provenance_references) == 1
    assert grant.provenance_references[0] == "hash-101"
    assert grant.cts_state["status"] == "pending"
    assert grant.brand_rules["voice"] == "authoritative and sleek"
    assert "cheap" in grant.brand_rules["prohibited_terms"]

    # Validate assembled context payload
    assert context["task_id"] == task.task_id
    assert len(context["documents"]) == 1
    assert context["authority_scope"]["tenant_id"] == "tenant-alpha"
    assert "budget_breakdown" in context


# --------------------------------------------------------------------------
# 2. Wrong Tenant Rejection / Cross-Tenant Leakage Prevention
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_directive_scope_mismatch_rejected(
    intelligence_engine: IntelligenceEngine,
) -> None:
    # Directive tenant_id does not match scope tenant_id
    directive = Directive(
        directive_id="dir-mismatch",
        tenant_id="tenant-alpha",
        objective="Analyze competitors",
        budget_cap=1000.0,
        risk_ceiling=RiskLevel.LOW,
        scope=TenantScope(tenant_id="tenant-beta"),
    )
    task = CanonicalTaskState(
        task_id=str(uuid.uuid4()),
        directive_id=directive.directive_id,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.PENDING,
    )

    with pytest.raises(PolicyViolationError, match="Directive tenant .* does not match scope tenant"):
        await intelligence_engine.assemble_task_grant(directive, task, query="test")


@pytest.mark.asyncio
async def test_cross_tenant_rag_leakage_prevented(
    rag_dispatcher: RagQueryDispatcher,
    mock_rag_controller: RagController,
) -> None:
    # RAG controller returns a document belonging to a foreign tenant
    mock_rag_controller.retrieve = AsyncMock(
        return_value=[
            {
                "doc_id": "foreign-doc",
                "tenant_id": "tenant-attacker",
                "text": "confidential competitor data",
                "provenance_hash": "hash-foreign",
                "retrieved_at": datetime.now(UTC),
            }
        ]
    )

    token = IntelligenceEngineToken(issued_to="intelligence_engine")
    with pytest.raises(RetrievalGovernanceError, match="Cross-tenant retrieval detected"):
        await rag_dispatcher.dispatch(token, tenant_id="tenant-victim", query="test")


# --------------------------------------------------------------------------
# 3. Brand-Specific Isolation Within Tenant
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brand_specific_persona_isolation(
    brand_resolver: BrandPersonaResolver,
) -> None:
    p_prem = brand_resolver.resolve(tenant_id="tenant-alpha", brand_id="brand-premium")
    p_budg = brand_resolver.resolve(tenant_id="tenant-alpha", brand_id="brand-budget")

    assert p_prem.voice == "authoritative and sleek"
    assert "cheap" in p_prem.prohibited_terms
    assert "exclusive" not in p_prem.prohibited_terms

    assert p_budg.voice == "approachable and friendly"
    assert "exclusive" in p_budg.prohibited_terms
    assert "cheap" not in p_budg.prohibited_terms

    # Resolving for a foreign tenant never returns tenant-alpha brands
    p_foreign = brand_resolver.resolve(tenant_id="tenant-gamma", brand_id="brand-premium")
    assert p_foreign.tenant_id == "tenant-gamma"
    assert p_foreign.voice == "neutral"  # Sane isolated default


# --------------------------------------------------------------------------
# 4. Stale Evidence Exclusion
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stale_evidence_excluded(
    rag_dispatcher: RagQueryDispatcher,
    mock_rag_controller: RagController,
) -> None:
    now = datetime.now(UTC)
    mock_rag_controller.retrieve = AsyncMock(
        return_value=[
            {
                "doc_id": "doc-fresh",
                "tenant_id": "tenant-alpha",
                "text": "Fresh performance metrics.",
                "provenance_hash": "hash-fresh",
                "retrieved_at": now - timedelta(days=1),
            },
            {
                "doc_id": "doc-stale",
                "tenant_id": "tenant-alpha",
                "text": "Outdated 2022 survey data.",
                "provenance_hash": "hash-stale",
                "retrieved_at": now - timedelta(days=95),
            },
        ]
    )

    token = IntelligenceEngineToken(issued_to="intelligence_engine")
    docs = await rag_dispatcher.dispatch(
        token,
        tenant_id="tenant-alpha",
        query="metrics",
        freshness_target=timedelta(days=30),
    )

    assert len(docs) == 1
    assert docs[0]["doc_id"] == "doc-fresh"


# --------------------------------------------------------------------------
# 5. Missing Provenance Exclusion
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_provenance_excluded(
    rag_dispatcher: RagQueryDispatcher,
    mock_rag_controller: RagController,
) -> None:
    now = datetime.now(UTC)
    mock_rag_controller.retrieve = AsyncMock(
        return_value=[
            {
                "doc_id": "doc-verified",
                "tenant_id": "tenant-alpha",
                "text": "Verified statement.",
                "provenance_hash": "hash-valid-123",
                "retrieved_at": now,
            },
            {
                "doc_id": "doc-untracked",
                "tenant_id": "tenant-alpha",
                "text": "Untracked untrusted snippet.",
                "provenance_hash": "",  # Missing provenance
                "retrieved_at": now,
            },
        ]
    )

    token = IntelligenceEngineToken(issued_to="intelligence_engine")
    docs = await rag_dispatcher.dispatch(
        token, tenant_id="tenant-alpha", query="data", provenance_required=True
    )

    assert len(docs) == 1
    assert docs[0]["doc_id"] == "doc-verified"


# --------------------------------------------------------------------------
# 6. CTS Hold Rejection
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cts_active_hold_rejects_grant(
    intelligence_engine: IntelligenceEngine,
) -> None:
    directive = Directive(
        directive_id="dir-1",
        tenant_id="tenant-alpha",
        objective="Do work",
        budget_cap=5000.0,
        risk_ceiling=RiskLevel.LOW,
        scope=TenantScope(tenant_id="tenant-alpha"),
    )

    # 1. Status is HELD
    held_task = CanonicalTaskState(
        task_id="task-held",
        directive_id=directive.directive_id,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.HELD,
        hold_reason="Awaiting regulatory compliance review",
    )
    with pytest.raises(PolicyViolationError, match="active hold in place"):
        await intelligence_engine.assemble_task_grant(directive, held_task, query="test")

    # 2. Status is PENDING but hold_reason is set
    pending_held_task = CanonicalTaskState(
        task_id="task-held-2",
        directive_id=directive.directive_id,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.PENDING,
        hold_reason="Legal investigation pending",
    )
    with pytest.raises(PolicyViolationError, match="active hold in place"):
        await intelligence_engine.assemble_task_grant(directive, pending_held_task, query="test")


# --------------------------------------------------------------------------
# 7. Unmet Prerequisite Locks & Dependencies Rejection
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unresolved_prerequisite_locks_rejects_grant(
    intelligence_engine: IntelligenceEngine,
) -> None:
    directive = Directive(
        directive_id="dir-1",
        tenant_id="tenant-alpha",
        objective="Do work",
        budget_cap=5000.0,
        risk_ceiling=RiskLevel.LOW,
        scope=TenantScope(tenant_id="tenant-alpha"),
    )

    locked_task = CanonicalTaskState(
        task_id="task-locked",
        directive_id=directive.directive_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
        prerequisite_locks=["db_migration_in_flight"],
    )
    with pytest.raises(PolicyViolationError, match="unresolved prerequisite locks"):
        await intelligence_engine.assemble_task_grant(directive, locked_task, query="test")


@pytest.mark.asyncio
async def test_unmet_dag_dependency_rejects_grant(
    intelligence_engine: IntelligenceEngine,
) -> None:
    directive = Directive(
        directive_id="dir-1",
        tenant_id="tenant-alpha",
        objective="Do work",
        budget_cap=5000.0,
        risk_ceiling=RiskLevel.LOW,
        scope=TenantScope(tenant_id="tenant-alpha"),
    )

    dep_task = CanonicalTaskState(
        task_id="task-downstream",
        directive_id=directive.directive_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
        dependencies=[
            TaskDependency(upstream_task_id="task-upstream", downstream_task_id="task-downstream")
        ],
    )

    # Without task-upstream completed
    with pytest.raises(PolicyViolationError, match="unmet upstream dependencies"):
        await intelligence_engine.assemble_task_grant(
            directive, dep_task, query="test", completed_upstream_task_ids=set()
        )

    # With task-upstream completed, grant assembly succeeds
    grant, _ = await intelligence_engine.assemble_task_grant(
        directive, dep_task, query="test", completed_upstream_task_ids={"task-upstream"}
    )
    assert grant.task_id == "task-downstream"


# --------------------------------------------------------------------------
# 8. Token Overflow & Precedence Truncation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_token_overflow_truncation_preserves_policy_and_governance(
    context_assembler: ContextAssembler,
    mock_rag_controller: RagController,
) -> None:
    now = datetime.now(UTC)
    # Return 10 long documents
    mock_rag_controller.retrieve = AsyncMock(
        return_value=[
            {
                "doc_id": f"doc-{i}",
                "tenant_id": "tenant-alpha",
                "text": f"Verbose evidence content for document {i} " * 50,
                "provenance_hash": f"hash-{i}",
                "retrieved_at": now,
            }
            for i in range(10)
        ]
    )

    token = IntelligenceEngineToken(issued_to="intelligence_engine")
    req = ContextRequest(
        task_id="task-token-overflow",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        query="overflow test",
        max_tokens=2500,  # Small token budget
    )

    context = await context_assembler.assemble(
        token,
        tenant_id="tenant-alpha",
        request=req,
        policy_constraints=["mandatory_rule:no_pii", "disclaimer_req:true"],
        risk_tier="high",
    )

    # Mandatory policy constraints and governance MUST be preserved
    assert "mandatory_rule:no_pii" in context["policy_constraints"]
    assert "risk_tier:high" in context["policy_constraints"]
    assert context["brand_persona"] is not None

    # Evidence documents must be budget-constrained (fewer than 10 documents)
    docs = context["documents"]
    assert len(docs) < 10
    # Provenance references must remain intact for kept documents
    assert len(context["provenance_references"]) == len(docs)


# --------------------------------------------------------------------------
# 9. Tool / Capability Allowlist & Monotonic Attenuation
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_capability_monotonic_attenuation(
    intelligence_engine: IntelligenceEngine,
) -> None:
    directive = Directive(
        directive_id="dir-dev",
        tenant_id="tenant-alpha",
        objective="Build template",
        budget_cap=5000.0,
        risk_ceiling=RiskLevel.LOW,
        scope=TenantScope(tenant_id="tenant-alpha"),
    )
    task = CanonicalTaskState(
        task_id=str(uuid.uuid4()),
        directive_id=directive.directive_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
    )

    grant, _ = await intelligence_engine.assemble_task_grant(directive, task, query="build UI")
    assert grant.sandbox_capabilities == ["S_CODE"]
    assert "ast_parser" in grant.tool_permissions
    assert "price_tracker" not in grant.tool_permissions  # S_SCRAPE tool cannot leak to W_DEV


# --------------------------------------------------------------------------
# 10. Brand Persona / Policy Conflict Resolution (Policy Wins)
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_brand_persona_subordinate_to_policy(
    brand_resolver: BrandPersonaResolver,
) -> None:
    persona = brand_resolver.resolve(tenant_id="tenant-alpha", brand_id="brand-premium")
    # Enterprise compliance mandates "untested" and "miracle" are strictly prohibited
    enterprise_policy_prohibited = ["untested", "miracle"]

    sanitized = brand_resolver.sanitize_against_policy(
        persona, policy_prohibited_terms=enterprise_policy_prohibited
    )

    # Both brand rules and enterprise policy prohibited terms must be present
    assert "cheap" in sanitized.prohibited_terms
    assert "discount" in sanitized.prohibited_terms
    assert "untested" in sanitized.prohibited_terms
    assert "miracle" in sanitized.prohibited_terms
