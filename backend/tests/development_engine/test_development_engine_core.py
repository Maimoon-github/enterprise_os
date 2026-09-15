"""Focused unit and integration tests for Task DE-01: Development Engine Core (W_DEV).

Validates:
1. W_DEV identity, subordinate boundary, and operational status.
2. Intelligence Engine registration and retrieval of W_DEV.
3. Structured invocation via DevelopmentTaskGrant and DevelopmentEngineRequest.
4. Fail-closed rejection of missing, malformed, expired, or out-of-scope grants.
5. Path traversal and unauthorized tool/capability rejection.
6. Cross-tenant isolation enforcement.
7. Model-A architectural boundaries (zero direct persistence/RAG/actuation).
8. Full bounded IE -> W_DEV -> IE invocation flow.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
import uuid

import pytest

from app.agents.development_engine.development import DevelopmentAgent
from app.core.exceptions import PolicyViolationError
from app.orchestration.context_assembly import BrandPersonaResolver, ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.agent_contracts import (
    ConfidenceInterval,
    DevelopmentDeliverable,
    EvidenceEnvelope,
    TaskGrant,
)
from app.schemas.development import (
    DevelopmentEngineIdentity,
    DevelopmentEngineRequest,
    DevelopmentEngineResult,
    DevelopmentEngineStatus,
    DevelopmentTaskGrant,
)
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.hitl import HitlCoordinator
from app.services.policy_engine import PolicyEngine
from app.services.provenance import ProvenanceRecorder
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from tests.conftest import (
    FakeProvenanceRepository,
    FakeSandboxClient,
    FakeVectorRepository,
)


@pytest.fixture
def fake_sandbox() -> FakeSandboxClient:
    return FakeSandboxClient()


@pytest.fixture
def dev_agent(fake_sandbox: FakeSandboxClient) -> DevelopmentAgent:
    return DevelopmentAgent(fake_sandbox)


@pytest.fixture
def sample_dev_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-dev-001",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        brand_id="brand-omega",
        objective="Implement header component",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        component_name="HeaderComponent",
        target_files=["components/header.py", "templates/header.html"],
        token_budget=5000,
        sandbox_capabilities=[SandboxCapability.CODE.value],
    )


# ===========================================================================
# 1. Identity & Status Tests
# ===========================================================================

def test_w_dev_identity(dev_agent: DevelopmentAgent) -> None:
    """W_DEV exposes clearly defined subordinate development engine identity."""
    identity = dev_agent.get_identity()
    assert isinstance(identity, DevelopmentEngineIdentity)
    assert identity.engine_id == "W_DEV"
    assert identity.engine_name == "Development Engine"
    assert identity.worker_role == WorkerRole.DEVELOPMENT
    assert identity.capability == SandboxCapability.CODE
    assert identity.is_subordinate is True
    assert identity.authority_scope == "development_domain_only"


def test_w_dev_initial_status(dev_agent: DevelopmentAgent) -> None:
    """W_DEV starts in IDLE status with no active tasks."""
    status = dev_agent.get_status()
    assert isinstance(status, DevelopmentEngineStatus)
    assert status.engine_id == "W_DEV"
    assert status.status == "IDLE"
    assert status.active_task_id is None
    assert "generate_diff" in status.supported_operations


# ===========================================================================
# 2. Registration & IE Integration Tests
# ===========================================================================

def test_w_dev_registration_with_intelligence_engine(dev_agent: DevelopmentAgent) -> None:
    """W_DEV can be registered and retrieved from Intelligence Engine."""
    ie = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(PolicyEngine()),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(
            RagQueryDispatcher(
                RagController(HybridRetriever(FakeVectorRepository()), FreshnessPolicy(), SchemaValidator())
            ),
            BrandPersonaResolver(),
        ),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=ProvenanceRecorder(FakeProvenanceRepository()),
        workers={},
    )

    assert ie.get_worker(WorkerRole.DEVELOPMENT) is None
    ie.register_worker(WorkerRole.DEVELOPMENT, dev_agent)
    assert ie.get_worker(WorkerRole.DEVELOPMENT) is dev_agent


# ===========================================================================
# 3. Invocation & Structured Contracts Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_w_dev_successful_invocation(
    dev_agent: DevelopmentAgent, sample_dev_grant: DevelopmentTaskGrant
) -> None:
    """W_DEV executes a valid request and returns a structured DevelopmentEngineResult."""
    request = DevelopmentEngineRequest(
        grant=sample_dev_grant,
        context={
            "tenant_id": "tenant-alpha",
            "component_name": "HeaderComponent",
            "target_files": ["components/header.py", "templates/header.html"],
        },
    )

    result = await dev_agent.invoke_development(request)

    assert isinstance(result, DevelopmentEngineResult)
    assert result.task_id == sample_dev_grant.task_id
    assert result.engine_id == "W_DEV"
    assert result.status == "SUCCESS"
    assert result.evidence_envelope is not None
    assert result.evidence_envelope.worker_role == WorkerRole.DEVELOPMENT
    assert result.provenance["engine_id"] == "W_DEV"
    assert dev_agent.get_status().status == "IDLE"
    assert dev_agent.get_status().active_task_id is None


@pytest.mark.asyncio
async def test_w_dev_direct_run_enforces_grant_validation(
    dev_agent: DevelopmentAgent, sample_dev_grant: DevelopmentTaskGrant
) -> None:
    """DevelopmentAgent.run validates the task grant fail-closed."""
    envelope = await dev_agent.run(sample_dev_grant, {"tenant_id": "tenant-alpha"})
    assert isinstance(envelope, EvidenceEnvelope)
    assert envelope.task_id == sample_dev_grant.task_id


# ===========================================================================
# 4. Fail-Closed Grant Validation Tests
# ===========================================================================

def test_rejects_none_grant(dev_agent: DevelopmentAgent) -> None:
    """None grant fails closed."""
    with pytest.raises(PolicyViolationError, match="Task grant cannot be None"):
        dev_agent.validate_task_grant(None)  # type: ignore[arg-type]


def test_rejects_wrong_worker_role(dev_agent: DevelopmentAgent) -> None:
    """Non-development worker role fails closed."""
    with pytest.raises((ValueError, PolicyViolationError)):
        DevelopmentTaskGrant(
            task_id="task-wrong-role",
            worker_role=WorkerRole.STRATEGY,  # type: ignore[arg-type]
            tenant_scope=TenantScope(tenant_id="tenant-1"),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )


def test_rejects_expired_grant(dev_agent: DevelopmentAgent) -> None:
    """Expired grant fails closed."""
    with pytest.raises((ValueError, PolicyViolationError), match="expired"):
        DevelopmentTaskGrant(
            task_id="task-expired",
            worker_role=WorkerRole.DEVELOPMENT,
            tenant_scope=TenantScope(tenant_id="tenant-1"),
            expires_at=datetime.now(UTC) - timedelta(minutes=10),
        )


@pytest.mark.parametrize(
    "invalid_path",
    [
        "../secret.py",
        "/etc/shadow",
        "c:\\windows\\system32",
        "c:/secrets/keys.txt",
        ".env",
        "credentials.json",
        "nested/../escape.py",
    ],
)
def test_rejects_path_traversal_and_sensitive_files(invalid_path: str) -> None:
    """Path traversal and forbidden patterns fail closed."""
    with pytest.raises((ValueError, PolicyViolationError)):
        DevelopmentTaskGrant(
            task_id="task-traversal",
            worker_role=WorkerRole.DEVELOPMENT,
            tenant_scope=TenantScope(tenant_id="tenant-1"),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            target_files=[invalid_path],
        )


def test_rejects_unauthorized_sandbox_capabilities() -> None:
    """W_DEV rejects sandbox capabilities other than CODE."""
    with pytest.raises((ValueError, PolicyViolationError), match="Unauthorized sandbox capability"):
        DevelopmentTaskGrant(
            task_id="task-bad-cap",
            worker_role=WorkerRole.DEVELOPMENT,
            tenant_scope=TenantScope(tenant_id="tenant-1"),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            sandbox_capabilities=["scrape"],
        )


def test_rejects_unauthorized_tool_permissions() -> None:
    """W_DEV rejects forbidden tools that attempt direct data-store access."""
    with pytest.raises((ValueError, PolicyViolationError), match="breaches Model-A boundary"):
        DevelopmentTaskGrant(
            task_id="task-bad-tool",
            worker_role=WorkerRole.DEVELOPMENT,
            tenant_scope=TenantScope(tenant_id="tenant-1"),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            tool_permissions=["app.persistence.database_query"],
        )


def test_rejects_cross_tenant_request_mismatch(sample_dev_grant: DevelopmentTaskGrant) -> None:
    """DevelopmentEngineRequest fails closed if context tenant does not match grant tenant."""
    with pytest.raises((ValueError, PolicyViolationError), match="Tenant isolation breach"):
        DevelopmentEngineRequest(
            grant=sample_dev_grant,
            context={"tenant_id": "tenant-other-corp"},
        )


# ===========================================================================
# 5. Model-A Architectural Boundary Tests
# ===========================================================================

def test_w_dev_has_zero_direct_data_or_actuation_imports() -> None:
    """W_DEV module must have zero direct imports of persistence, RAG, MCP, or external adapters."""
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "agents"
        / "development_engine"
        / "development.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    disallowed_prefixes = (
        "app.persistence",
        "app.services.rag",
        "app.mcp",
        "app.security",
        "app.integrations.cms.client",
        "app.integrations.ads",
        "app.integrations.social",
        "app.orchestration.rag_query_dispatch",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(disallowed_prefixes), (
                    f"W_DEV imports forbidden module: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(disallowed_prefixes), (
                f"W_DEV imports from forbidden module: {node.module}"
            )


# ===========================================================================
# 6. Full Intelligence Engine -> W_DEV -> Intelligence Engine Invocation Flow
# ===========================================================================

@pytest.mark.asyncio
async def test_intelligence_engine_invokes_development_worker(
    dev_agent: DevelopmentAgent,
) -> None:
    """Full IE -> W_DEV -> IE invocation pipeline succeeds and transitions task state."""
    provenance_repo = FakeProvenanceRepository()
    task_sm = TaskStateMachine()

    ie = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(PolicyEngine()),
        dag_scheduler=DagScheduler(),
        task_state_machine=task_sm,
        context_assembler=ContextAssembler(
            RagQueryDispatcher(
                RagController(HybridRetriever(FakeVectorRepository()), FreshnessPolicy(), SchemaValidator())
            ),
            BrandPersonaResolver(),
        ),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=ProvenanceRecorder(provenance_repo),
        workers={WorkerRole.DEVELOPMENT: dev_agent},
    )

    directive = Directive(
        directive_id="dir-dev-100",
        tenant_id="tenant-alpha",
        scope=TenantScope(tenant_id="tenant-alpha"),
        objective="Build new customer landing component",
        risk_ceiling=RiskLevel.LOW,
        budget_cap=5000.0,
    )

    task = CanonicalTaskState(
        task_id=str(uuid.uuid4()),
        directive_id=directive.directive_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
        governance_approved=True,
    )

    result = await ie.invoke_development_worker(
        directive,
        task,
        query="generate landing component",
        brand_id="brand-default",
        target_files=["components/landing.py", "templates/landing.html"],
        component_name="LandingComponent",
    )

    assert isinstance(result, DevelopmentEngineResult)
    assert result.status == "SUCCESS"
    assert result.engine_id == "W_DEV"
    assert result.task_id == task.task_id
    assert result.evidence_envelope.worker_role == WorkerRole.DEVELOPMENT

    # Verify task state transitioned to COMPLETED
    assert task.status == TaskStatus.COMPLETED

    # Verify provenance was recorded
    records = await provenance_repo.chain(directive.tenant_id)
    assert len(records) >= 1
    assert records[-1].entity_id == task.task_id
    assert records[-1].activity == "development_engine_execution"
    assert records[-1].agent == "W_DEV"
