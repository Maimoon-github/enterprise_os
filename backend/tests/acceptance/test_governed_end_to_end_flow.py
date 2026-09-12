"""Verifies directive -> workers -> HITL -> actuation -> telemetry -> learning flow."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.exceptions import ApprovalRequiredError
from app.integrations.ads.base import AdsAdapter
from app.mcp.data_gateway import DataGateway
from app.mcp.host import McpHost
from app.mcp.outbound_gateway import OutboundGateway, canonical_dispatch_bytes
from app.orchestration.brand_persona import BrandPersonaResolver
from app.orchestration.context_assembly import ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import ActionPreviewKind
from app.schemas.dispatch import DispatchDirective
from app.schemas.governance import Directive, RiskLevel
from app.schemas.telemetry import TelemetryEventType
from app.security.authorization_boundary import AuthorizationBoundary
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.security.scope_evaluator import ScopeEvaluator
from app.services.hitl import HitlCoordinator
from app.services.memory_promotion import MemoryPromotionService
from app.services.provenance import ProvenanceRecorder
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from app.services.telemetry import TelemetryNormalizer
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient, FakeVectorRepository
from tests.integration.test_telemetry_learning_loop import (
    _InMemoryMemoryRepository,
    _InMemoryTelemetryRepository,
)


class _RecordingAdsAdapter(AdsAdapter):
    channel = "meta"

    def __init__(self) -> None:
        self.applied: list[dict[str, str]] = []

    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        self.applied.append(payload)
        return {"status_code": "200", "channel": self.channel}


@pytest.mark.asyncio
async def test_governed_end_to_end_flow(
    sample_directive: Directive, sample_task, ed25519_keypair
) -> None:
    private_key, public_pem = ed25519_keypair

    # -- Wire the Intelligence Engine and every collaborator it composes. --
    vector_repository = FakeVectorRepository()
    vector_repository.seed(
        tenant_id=sample_directive.tenant_id, text="summer campaign hooks and offers"
    )
    rag_controller = RagController(
        HybridRetriever(vector_repository), FreshnessPolicy(), SchemaValidator()
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    fake_sandbox = FakeSandboxClient()
    from app.agents.creative_content import CreativeContentAgent

    workers = {sample_task.worker_role: CreativeContentAgent(fake_sandbox)}

    hitl_coordinator = HitlCoordinator()
    crypto_validator = CryptographicValidator(public_pem)
    ads_adapter = _RecordingAdsAdapter()
    outbound_gateway = OutboundGateway(
        hitl_coordinator, crypto_validator, ads_adapters={"meta": ads_adapter}
    )
    data_gateway = DataGateway(vector_repository, AuthorizationBoundary(ScopeEvaluator()))
    mcp_host = McpHost(data_gateway, outbound_gateway)

    provenance_recorder = ProvenanceRecorder(FakeProvenanceRepository())

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(rag_dispatcher, BrandPersonaResolver()),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=hitl_coordinator,
        mcp_host=mcp_host,
        provenance_recorder=provenance_recorder,
        workers=workers,
    )

    # -- 1. Directive delegates a bounded task grant to the worker. --
    envelope = await engine.delegate_task(
        sample_directive, sample_task, query="summer campaign hooks"
    )
    assert envelope.task_id == sample_task.task_id
    assert fake_sandbox.invocations, "the worker must have executed through the sandbox boundary"

    # -- 2. The Intelligence Engine builds a mandatory human-review preview. --
    preview = await engine.build_preview(
        [envelope], kind=ActionPreviewKind.COPY, risk_level=RiskLevel.LOW
    )
    assert preview.requires_approval is True
    assert hitl_coordinator.is_pending(preview.preview_id)

    # -- 3. Actuation is blocked until a human approves the preview. --
    unsigned_dispatch = DispatchDirective(
        dispatch_id="dispatch-1",
        task_id=sample_task.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="pending",
        approved_at=datetime.now(UTC),
        channel="meta",
        payload={"campaign_id": "42"},
    )
    with pytest.raises(ApprovalRequiredError):
        await engine.dispatch_after_approval(unsigned_dispatch)

    # -- 4. A human approves; the engine signs and actuates the dispatch. --
    hitl_coordinator.decide(preview.preview_id, approved=True, approver="[email protected]")
    dispatch_to_sign = unsigned_dispatch.model_copy(update={"approved_by": "[email protected]"})
    signature = sign_payload(canonical_dispatch_bytes(dispatch_to_sign), private_key)
    approved_dispatch = dispatch_to_sign.model_copy(update={"signature": signature})

    result = await engine.dispatch_after_approval(approved_dispatch)
    assert result == {"status_code": "200", "channel": "meta"}
    assert ads_adapter.applied == [{"campaign_id": "42"}]

    # -- 5. Telemetry from the actuated campaign feeds the learning loop. --
    telemetry_repository = _InMemoryTelemetryRepository()
    telemetry_normalizer = TelemetryNormalizer(telemetry_repository)
    await telemetry_normalizer.ingest(
        tenant_id=sample_directive.tenant_id,
        event_type=TelemetryEventType.ROAS,
        channel="meta",
        occurred_at=datetime.now(UTC),
        metrics={"roas": 4.1},
    )
    roas_events = await telemetry_normalizer.for_learning_loop(sample_directive.tenant_id)
    assert len(roas_events) == 1

    # -- 6. A validated learning delta is promoted into institutional memory. --
    memory_repository = _InMemoryMemoryRepository()
    memory_promotion_service = MemoryPromotionService(memory_repository, min_confidence=0.7)
    promoted = await memory_promotion_service.promote(
        tenant_id=sample_directive.tenant_id,
        category="creative_performance",
        statement="Hook-led copy variants outperform benefit-led copy for this brand.",
        confidence=0.9,
        source_task_ids=[sample_task.task_id],
    )
    assert promoted is not None
    assert len(memory_repository.all()) == 1

    # -- 7. Every control-plane step left an intact, hash-chained audit trail. --
    assert await provenance_recorder.verify_chain(sample_directive.tenant_id) is True
    chain = await provenance_recorder.audit_chain(sample_directive.tenant_id)
    assert any(record.activity == "worker_execution" for record in chain)

    # -- 8. Closed-loop verification: BrandPersonaResolver dynamically absorbs promoted insight --
    persona_resolver = BrandPersonaResolver(memory_repository=memory_repository)
    resolved_persona = await persona_resolver.resolve_with_memory(tenant_id=sample_directive.tenant_id)
    assert any("Hook-led copy variants outperform" in h for h in resolved_persona.learned_heuristics)


@pytest.mark.asyncio
async def test_governed_multi_worker_dag_pipeline(
    sample_directive: Directive, ed25519_keypair
) -> None:
    """Executes a multi-worker DAG across Strategy, Product Evidence, Creative Content, and Dev."""
    from app.agents.creative_content import CreativeContentAgent
    from app.agents.development import DevelopmentAgent
    from app.agents.product_evidence import ProductEvidenceAgent
    from app.agents.strategy import StrategyAgent
    from app.integrations.sandbox.client import SandboxClient
    from app.schemas.governance import WorkerRole
    from app.schemas.task_state import CanonicalTaskState, TaskDependency, TaskStatus

    # Set up real SandboxClient backed by specialist micro-tools
    sandbox_client = SandboxClient()

    workers = {
        WorkerRole.STRATEGY: StrategyAgent(sandbox_client),
        WorkerRole.PRODUCT_EVIDENCE: ProductEvidenceAgent(sandbox_client),
        WorkerRole.CREATIVE_CONTENT: CreativeContentAgent(sandbox_client),
        WorkerRole.DEVELOPMENT: DevelopmentAgent(sandbox_client),
    }

    vector_repository = FakeVectorRepository()
    vector_repository.seed(tenant_id=sample_directive.tenant_id, text="Q3 strategic positioning")
    rag_controller = RagController(
        HybridRetriever(vector_repository), FreshnessPolicy(), SchemaValidator()
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    hitl_coordinator = HitlCoordinator()
    _, public_pem = ed25519_keypair
    crypto_validator = CryptographicValidator(public_pem)
    outbound_gateway = OutboundGateway(
        hitl_coordinator, crypto_validator, ads_adapters={"meta": _RecordingAdsAdapter()}
    )
    data_gateway = DataGateway(vector_repository, AuthorizationBoundary(ScopeEvaluator()))
    mcp_host = McpHost(data_gateway, outbound_gateway)
    provenance_recorder = ProvenanceRecorder(FakeProvenanceRepository())

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(rag_dispatcher, BrandPersonaResolver()),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=hitl_coordinator,
        mcp_host=mcp_host,
        provenance_recorder=provenance_recorder,
        workers=workers,
    )

    # Construct DAG: Strategy -> Product Evidence -> Creative Content -> Development
    task_strat = CanonicalTaskState(
        task_id="task-strat",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
    )
    task_prod = CanonicalTaskState(
        task_id="task-prod",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        status=TaskStatus.PENDING,
        dependencies=[TaskDependency(upstream_task_id="task-strat", downstream_task_id="task-prod")],
    )
    task_creat = CanonicalTaskState(
        task_id="task-creat",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.PENDING,
        dependencies=[TaskDependency(upstream_task_id="task-prod", downstream_task_id="task-creat")],
    )
    task_dev = CanonicalTaskState(
        task_id="task-dev",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
        dependencies=[TaskDependency(upstream_task_id="task-creat", downstream_task_id="task-dev")],
    )

    dag_tasks = [task_strat, task_prod, task_creat, task_dev]

    # Execute DAG
    envelopes = await engine.execute_dag(sample_directive, dag_tasks)

    assert len(envelopes) == 4
    for t_id, env in envelopes.items():
        assert env.task_id == t_id
        assert env.confidence.point_estimate >= 0.5

    from app.schemas.artifact import compute_content_hash

    # Development and Creative workers generate immutable artifacts
    dev_envelope = envelopes["task-dev"]
    assert len(dev_envelope.generated_artifacts) > 0
    assert any("diff:task-dev" in art for art in dev_envelope.generated_artifacts)

    creative_envelope = envelopes["task-creat"]
    assert len(creative_envelope.generated_artifacts) > 0
    assert any("copy:task-creat" in art for art in creative_envelope.generated_artifacts)

    # Artifact hashing generates valid 64-char SHA-256 digest
    diff_content = dev_envelope.payload.get("diff", "diff output")
    assert len(compute_content_hash(diff_content)) == 64

    # Build action preview from all worker outputs
    all_envelopes = list(envelopes.values())
    preview = await engine.build_preview(
        all_envelopes, kind=ActionPreviewKind.CODE_DIFF, risk_level=RiskLevel.MEDIUM
    )
    assert preview.requires_approval is True
    assert hitl_coordinator.is_pending(preview.preview_id)
    assert preview.diff is not None
    assert "LandingHeader" in preview.diff