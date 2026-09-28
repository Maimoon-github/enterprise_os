"""Verifies directive -> workers -> HITL -> actuation -> telemetry -> learning flow."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.agents.base import BoundedWorkerAgent
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
from app.schemas.governance import Directive, RiskLevel, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
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
from tests.conftest import (
    FakeProvenanceRepository,
    FakeVectorRepository,
    create_mock_remote_sandbox,
)
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

    from app.agents.creative_content import CreativeContentAgent

    # Zero-sandbox W_CREAT coordinator
    workers: dict[WorkerRole, BoundedWorkerAgent] = {
        sample_task.worker_role: CreativeContentAgent()
    }
    sample_task.cts_state = {
        "claims_dossier": {
            "tenant_id": sample_directive.tenant_id,
            "claims": [
                {
                    "claim_id": "c-1",
                    "text": "summer campaign hooks and offers verified",
                    "validation_status": "SUPPORTED",
                }
            ],
        },
        "strategy_plan": {
            "tenant_id": sample_directive.tenant_id,
            "channels": ["meta"],
            "target_audience": "enterprise growth audience",
        },
    }

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
    assert envelope.provenance["capability"] == "NONE"
    assert len(envelope.generated_artifacts) > 0

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
    from app.schemas.task_state import CanonicalTaskState, TaskDependency, TaskStatus

    # Set up real SandboxClient backed by specialist micro-tools
    sandbox_client = SandboxClient()

    workers: dict[WorkerRole, BoundedWorkerAgent] = {
        WorkerRole.STRATEGY: StrategyAgent(create_mock_remote_sandbox()),
        WorkerRole.PRODUCT_EVIDENCE: ProductEvidenceAgent(sandbox_client),
        WorkerRole.CREATIVE_CONTENT: CreativeContentAgent(),
        WorkerRole.DEVELOPMENT: DevelopmentAgent(sandbox_client),
    }

    vector_repository = FakeVectorRepository()
    vector_repository.seed(tenant_id=sample_directive.tenant_id, text="Q3 strategic positioning")
    vector_repository.seed(
        tenant_id=sample_directive.tenant_id,
        text="Clinically tested to improve performance by 40% in enterprise benchmark testing.",
    )
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


class _InMemoryTaskStateRepo:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        return self.states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state

    async def compare_and_swap_state(
        self, tenant_id: str, expected_version: int, state: CanonicalTaskState
    ) -> bool:
        current = self.states.get(state.task_id)
        if current is not None and current.version != expected_version:
            return False
        self.states[state.task_id] = state
        return True


@pytest.mark.asyncio
async def test_governed_e2e_hold_checkpoint_recovery_flow(
    sample_directive: Directive, ed25519_keypair
) -> None:
    """Executes full governed acceptance flow with hold -> checkpoint -> recovery.

    Verifies that:
    1. Active hold blocks grant assembly fail-closed.
    2. Checkpoint recovery restores task state with incremented version and audit lineage.
    3. Recovered worker evidence flows into ActionPreview and signed HITL approval.
    4. Outbound dispatch actuates through MCP_ACT with sole authority.
    5. Resulting CTS (COMPLETED), dispatch receipt, and hash-chained provenance agree.
    """
    from app.agents.creative_content import CreativeContentAgent
    from app.core.exceptions import PolicyViolationError
    from app.services.task_state import TaskStateService

    private_key, public_pem = ed25519_keypair
    tenant_id = sample_directive.tenant_id

    # 1. Wire governance repositories and services
    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)
    task_repo = _InMemoryTaskStateRepo()
    task_state_machine = TaskStateMachine()
    task_state_service = TaskStateService(
        repository=task_repo,
        state_machine=task_state_machine,
        provenance_recorder=provenance_recorder,
    )

    vector_repository = FakeVectorRepository()
    vector_repository.seed(tenant_id=tenant_id, text="Verified brand copy guidelines")
    rag_controller = RagController(
        HybridRetriever(vector_repository), FreshnessPolicy(), SchemaValidator()
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    hitl_coordinator = HitlCoordinator()
    crypto_validator = CryptographicValidator(public_pem)
    ads_adapter = _RecordingAdsAdapter()
    outbound_gateway = OutboundGateway(
        hitl_coordinator,
        crypto_validator,
        ads_adapters={"meta": ads_adapter},
        task_state_service=task_state_service,
        provenance_recorder=provenance_recorder,
    )
    data_gateway = DataGateway(vector_repository, AuthorizationBoundary(ScopeEvaluator()))
    mcp_host = McpHost(data_gateway, outbound_gateway)

    worker_role = WorkerRole.CREATIVE_CONTENT
    workers: dict[WorkerRole, BoundedWorkerAgent] = {worker_role: CreativeContentAgent()}

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=task_state_machine,
        context_assembler=ContextAssembler(rag_dispatcher, BrandPersonaResolver()),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=hitl_coordinator,
        mcp_host=mcp_host,
        provenance_recorder=provenance_recorder,
        workers=workers,
    )

    # 2. Initialize CanonicalTaskState
    task_id = "task-e2e-recovery-1"
    task = CanonicalTaskState(
        task_id=task_id,
        directive_id=sample_directive.directive_id,
        worker_role=worker_role,
        status=TaskStatus.PENDING,
        cts_state={
            "claims_dossier": {
                "tenant_id": tenant_id,
                "claims": [
                    {
                        "claim_id": "c-101",
                        "text": "Clinically proven results",
                        "validation_status": "SUPPORTED",
                    }
                ],
            },
            "strategy_plan": {
                "tenant_id": tenant_id,
                "channels": ["meta"],
                "target_audience": "enterprise growth audience",
            },
        },
    )
    await task_state_service.save_state(tenant_id, task)

    # Advance to GRANTED then IN_PROGRESS (creating checkpoints)
    granted = await task_state_service.transition(
        tenant_id, task, TaskStatus.GRANTED, note="Grant issued"
    )
    in_prog = await task_state_service.transition(
        tenant_id, granted, TaskStatus.IN_PROGRESS, note="Execution started"
    )
    assert in_prog.status == TaskStatus.IN_PROGRESS
    checkpoint_to_recover = in_prog.checkpoints[-1].checkpoint_id

    # 3. Enter HELD state (e.g. governance/compliance review)
    held = await task_state_service.hold_task(
        tenant_id, task_id, reason="Compliance audit hold"
    )
    assert held.status == TaskStatus.HELD
    assert held.hold_reason == "Compliance audit hold"

    # Verify active hold fails closed against task delegation
    with pytest.raises(PolicyViolationError, match="active hold in place"):
        await engine.assemble_task_grant(sample_directive, held, query="brand copy")

    # 4. Checkpoint Recovery: Authoritatively restore task state from checkpoint
    recovered = await task_state_service.recover_task_checkpoint(
        tenant_id, task_id, checkpoint_to_recover
    )
    assert recovered.status == TaskStatus.IN_PROGRESS
    assert recovered.hold_reason is None
    assert recovered.version > held.version

    # 5. Worker execution after recovery generates evidence envelope
    envelope = await engine.delegate_task(
        sample_directive, recovered, query="brand copy"
    )
    assert envelope.task_id == task_id
    assert envelope.confidence.point_estimate > 0.0
    assert len(envelope.generated_artifacts) > 0

    # 6. Advance task to AWAITING_APPROVAL and build ActionPreview
    awaiting = await task_state_service.transition(
        tenant_id, recovered, TaskStatus.AWAITING_APPROVAL, note="Evidence ready for HITL"
    )
    preview = await engine.build_preview(
        [envelope], kind=ActionPreviewKind.COPY, risk_level=RiskLevel.LOW
    )
    assert preview.requires_approval is True
    assert hitl_coordinator.is_pending(preview.preview_id)

    # 7. HITL Decision & Signed Clearance
    hitl_coordinator.decide(preview.preview_id, approved=True, approver="[email protected]")
    approved_task = await task_state_service.transition(
        tenant_id, awaiting, TaskStatus.APPROVED, note="Approved by human reviewer"
    )
    assert approved_task.status == TaskStatus.APPROVED

    # 8. Outbound Dispatch: Signed actuation via OutboundGateway
    dispatch = DispatchDirective(
        dispatch_id="dispatch-rec-e2e-1",
        task_id=task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="meta",
        tenant_id=tenant_id,
        payload={"campaign_id": "meta-recovery-campaign-99"},
    )
    sig = sign_payload(canonical_dispatch_bytes(dispatch), private_key)
    signed_dispatch = dispatch.model_copy(update={"signature": sig})

    result = await outbound_gateway.execute(signed_dispatch)
    assert result == {"status_code": "200", "channel": "meta"}
    assert ads_adapter.applied == [{"campaign_id": "meta-recovery-campaign-99"}]

    # 9. Verify resulting CTS, dispatch receipt, and provenance agree
    final_task = await task_state_service.get_state(task_id)
    assert final_task.status == TaskStatus.COMPLETED
    assert final_task.cts_state.get("deployment") == result
    assert final_task.task_id == signed_dispatch.task_id

    # Provenance chain verification
    assert await provenance_recorder.verify_chain(tenant_id) is True
    audit_chain = await provenance_recorder.audit_chain(tenant_id)
    activities = [r.activity for r in audit_chain]

    assert "task_checkpoint_recovery" in activities
    assert "worker_execution" in activities
    assert "mcp_act_readiness_validation" in activities
    assert "outbound_dispatch_intent_persisted" in activities
    assert "outbound_meta_deployment_executed" in activities


@pytest.mark.asyncio
async def test_t14_governed_end_to_end_feedback_loop(ed25519_keypair: tuple[str, str]) -> None:
    """T14: Approved release -> trusted signal -> durable evidence -> IE/Learning -> validated Strategy input -> proposed action requiring approval."""
    from datetime import timedelta
    from app.agents.strategy_engine.strategy import StrategyAgent
    from app.integrations.cms.client import CmsClient
    from app.schemas.agent_contracts import TaskGrant
    from app.schemas.governance import TenantScope
    from app.schemas.strategy import PerformanceContextReference
    from app.schemas.telemetry import RecordKind, TelemetryEnvelope, TrustClass
    from app.services.telemetry import TelemetryService

    tenant_id = "tenant-t14"
    brand_id = "brand-t14"

    # 1. Approved CMS release stamps release_id
    cms = CmsClient()
    deploy_res = await cms.deploy_payload(
        {"items": [{"content_type": "pages", "id": "page-t14", "title": "Verified Performance Page"}]},
        tenant_id=tenant_id,
    )
    assert deploy_res["status"] == "published"
    release_id = deploy_res["release_id"]
    assert release_id is not None

    # 2. Trusted Telemetry signal admitted into durable repository with release stamp
    from tests.integration.test_layer8_security import FakeTelemetryRepository
    telemetry_repo = FakeTelemetryRepository()
    telemetry_service = TelemetryService(telemetry_repo)
    env = TelemetryEnvelope(
        envelope_id="env-t14-1",
        tenant_id=tenant_id,
        brand_id=brand_id,
        channel="meta",
        record_kind=RecordKind.METRIC_SNAPSHOT,
        trust_class=TrustClass.PROVIDER_VERIFIED,
        source_id="meta_ads_webhook",
        source_account_id="act-meta-14",
        source_revision=release_id,
        logical_event_id="evt-perf-14",
        payload={"spend": 1250.0, "roas": 4.1, "conversions": 85},
    )
    receipt = await telemetry_service.admit(env)
    assert receipt.receipt_id is not None
    assert receipt.status in ("accepted", "admitted")
    assert receipt.source_revision == release_id

    # 3. IE-mediated Performance Context Assembly via RAG bridge
    vector_repo = FakeVectorRepository()
    vector_repo.seed(tenant_id=tenant_id, text=f"Release {release_id} performance: ROAS 4.1x on Meta Ads.")
    rag_controller = RagController(
        HybridRetriever(vector_repo), FreshnessPolicy(), SchemaValidator()
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)
    hitl_coordinator = HitlCoordinator()
    assembler = ContextAssembler(rag_dispatcher, BrandPersonaResolver())

    _, public_pem = ed25519_keypair
    crypto_validator = CryptographicValidator(public_pem)
    outbound_gateway = OutboundGateway(
        hitl_coordinator, crypto_validator, ads_adapters={"meta": _RecordingAdsAdapter()}
    )
    data_gateway = DataGateway(vector_repo, AuthorizationBoundary(ScopeEvaluator()))
    mcp_host = McpHost(data_gateway, outbound_gateway)

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=assembler,
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=hitl_coordinator,
        mcp_host=mcp_host,
        provenance_recorder=ProvenanceRecorder(FakeProvenanceRepository()),
        workers={},
    )

    perf_ctx_dict = await engine.build_performance_context(
        tenant_id=tenant_id,
        brand_id=brand_id,
        channels=["meta", "google"],
        requested_metrics=["roas", "spend"],
        raw_performance_data={
            "meta": {"status": "valid", "value": 4.1},
            "google": {"status": "valid", "value": 2500.0},
        },
    )
    perf_ctx = PerformanceContextReference.model_validate(perf_ctx_dict)
    assert perf_ctx.is_valid is True
    assert perf_ctx.quality_flags["has_stale_data"] is False
    assert perf_ctx.quality_flags["has_suppression"] is False
    assert perf_ctx.metrics["meta"]["value"] == 4.1

    # 4. Learning hand-off: receives governed performance context without DB/gateway credentials
    learning_evidence = {
        "model_id": "w_learn_attribution_v1",
        "tenant_id": tenant_id,
        "performance_context_id": perf_ctx.context_id,
        "channel_weights": {"meta": 0.65, "google": 0.35},
        "uncertainty_score": 0.04,
    }

    # 5. Validated Strategy Input: StrategyAgent validates context & produces proposal
    strat_grant = TaskGrant(
        task_id="task-strat-t14",
        directive_id="dir-t14",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id=tenant_id, allowed_channels=["meta", "google"]),
        brand_id=brand_id,
        allowed_capabilities=[],
        risk_ceiling=RiskLevel.MEDIUM,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    strat_context = {
        "budget_ceiling": 10000.0,
        "channels": ["meta", "google"],
        "approved_claims": [{"claim_id": "c-14", "text": "Clinically proven results", "status": "approved"}],
        "objections": [{"objection_id": "o-14", "theme": "Pricing transparency"}],
        "competitor_signals": {"competitor": "CompetitorZ", "benchmark_price": "59.99"},
        "performance_context": perf_ctx,
        "require_performance_context": True,
        "learning_evidence": learning_evidence,
    }

    mock_sandbox = create_mock_remote_sandbox()
    strat_agent = StrategyAgent(mock_sandbox)
    strat_envelope = await strat_agent.run(strat_grant, strat_context)
    assert strat_envelope.task_id == "task-strat-t14"
    assert "strategy_plan" in strat_envelope.payload

    # 6. Proposed Action still requires mandatory HITL approval before actuation
    preview = await engine.build_preview(
        [strat_envelope], kind=ActionPreviewKind.SPEND, risk_level=RiskLevel.MEDIUM
    )
    assert preview.requires_approval is True
    assert hitl_coordinator.is_pending(preview.preview_id) is True

    # 7. Approving through HITL resolves preview
    hitl_coordinator.decide(preview.preview_id, approved=True, approver="[email protected]")
    assert hitl_coordinator.is_pending(preview.preview_id) is False