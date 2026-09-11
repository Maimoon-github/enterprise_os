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