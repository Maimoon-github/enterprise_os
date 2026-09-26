"""Integration tests for T19 Omnichannel Strategy, Funnel & Budget Allocation."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.agents.base import BoundedWorkerAgent
from app.agents.customer_voice import CustomerVoiceAgent
from app.agents.product_evidence import ProductEvidenceAgent
from app.agents.strategy import StrategyAgent
from app.core.exceptions import PolicyViolationError, SandboxInvocationError
from app.integrations.sandbox.capabilities import validate_capability_access
from app.integrations.sandbox.client import SandboxClient
from app.orchestration.context_assembly import BrandPersonaResolver, ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.core.settings import SandboxSettings
from app.schemas.action_preview import ActionPreviewKind, ReviewStatus
from app.schemas.agent_contracts import (
    ConfidenceInterval,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    TaskGrant,
)
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.provenance import ProvRelationType
from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxInvocationMandate
from app.schemas.strategy import StrategyResultEnvelope
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.hitl import HitlCoordinator
from app.services.provenance import ProvenanceRecorder, compute_canonical_sha256
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from tests.conftest import (
    FakeProvenanceRepository,
    FakeVectorRepository,
    create_mock_remote_sandbox,
)


def test_w_strat_module_has_zero_direct_persistence_or_rag_imports() -> None:
    """W_STRAT must not directly import persistence, RAG, CMS, DB, or services (Model-A Invariant)."""
    agents_dir = Path(__file__).resolve().parents[2] / "app" / "agents"
    source_files = [
        agents_dir / "strategy.py",
        agents_dir / "strategy_engine" / "strategy.py",
    ]

    disallowed_prefixes = (
        "app.persistence",
        "app.services",
        "app.mcp",
        "app.security",
        "app.integrations.llm",
        "app.integrations.cms",
        "app.integrations.ads",
        "app.integrations.social",
        "app.orchestration.rag_query_dispatch",
    )

    for source_file in source_files:
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in disallowed_prefixes:
                        assert not alias.name.startswith(prefix), f"Disallowed direct import in {source_file.name}: {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                for prefix in disallowed_prefixes:
                    assert not node.module.startswith(prefix), f"Disallowed direct import in {source_file.name}: {node.module}"


def test_s_alloc_module_has_zero_persistence_or_rag_imports() -> None:
    """S_ALLOC reasoning specialist must not directly import persistence, RAG, CMS, DB, or services."""
    source_file = Path(__file__).resolve().parents[2] / "app" / "agents" / "strategy_engine" / "subagents" / "allocation.py"
    tree = ast.parse(source_file.read_text(encoding="utf-8"))

    disallowed_prefixes = (
        "app.persistence",
        "app.services",
        "app.mcp",
        "app.security",
        "app.integrations.cms",
        "app.integrations.ads",
        "app.integrations.social",
        "app.orchestration.rag_query_dispatch",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in disallowed_prefixes:
                    assert not alias.name.startswith(prefix), f"Disallowed direct import in S_ALLOC: {alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module:
            for prefix in disallowed_prefixes:
                assert not node.module.startswith(prefix), f"Disallowed direct import in S_ALLOC: {node.module}"


def test_unauthorized_capability_rejected_for_w_strat() -> None:
    """W_STRAT is authorized strictly for SandboxCapability.ALLOC; other capabilities fail closed."""
    profile = validate_capability_access(
        capability=SandboxCapability.ALLOC,
        worker_role=WorkerRole.STRATEGY,
        operation="optimize_budget",
    )
    assert profile.allowed_worker == WorkerRole.STRATEGY

    unauthorized = [
        SandboxCapability.CODE,
        SandboxCapability.COPY,
        SandboxCapability.VAL,
        SandboxCapability.COMP,
        SandboxCapability.PARSE,
        SandboxCapability.ATTR,
    ]
    for cap in unauthorized:
        with pytest.raises(SandboxInvocationError, match="Capability access denied"):
            validate_capability_access(
                capability=cap,
                worker_role=WorkerRole.STRATEGY,
                operation="any",
            )


@pytest.mark.asyncio
async def test_governed_ie_grant_to_w_strat_pipeline(sample_directive: Directive) -> None:
    """Full governed execution: T16/T17/T18 context -> IE Grant -> W_STRAT -> S_ALLOC in sandbox -> Strategy EvidenceEnvelope -> IE."""
    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)
    sandbox_client = create_mock_remote_sandbox(provenance_recorder=provenance_recorder)
    w_strat = StrategyAgent(sandbox_client)

    # Verify W_STRAT and S_ALLOC use distinct purpose-scoped LLM client identities when configured
    w_strat_client = MagicMock()
    s_alloc_client = MagicMock()
    w_strat_with_llms = StrategyAgent(
        sandbox_client,
        llm_client=w_strat_client,
        allocation_agent=w_strat.allocation_agent.__class__(llm_client=s_alloc_client),
    )
    assert w_strat_with_llms._llm_client is not w_strat_with_llms.allocation_agent._llm_client

    workers: dict[WorkerRole, BoundedWorkerAgent] = {
        WorkerRole.STRATEGY: w_strat,
    }

    vector_repo = FakeVectorRepository()
    vector_repo.seed(
        tenant_id=sample_directive.tenant_id,
        text="Clinical test CT-409: Demonstrated 40% reduction in fine lines across 30 subjects with bio-peptide formulation. *Results may vary.",
    )
    rag_controller = RagController(
        HybridRetriever(vector_repo), FreshnessPolicy(), SchemaValidator()
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(rag_dispatcher, BrandPersonaResolver()),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=provenance_recorder,
        workers=workers,
    )

    task = CanonicalTaskState(
        task_id="task-strat-governed-1",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        cts_state={
            "budget_cap": 30000.0,
            "claims_dossier": {
                "tenant_id": sample_directive.tenant_id,
                "claims": [
                    {
                        "claim_id": "c1",
                        "claim_text": "Clinically proven 40% reduction in fine lines",
                        "validation_status": "SUPPORTED",
                        "confidence": 0.94,
                    }
                ],
            },
            "customer_voice_analysis": {
                "tenant_id": sample_directive.tenant_id,
                "objection_profiles": [
                    {"objection_type": "product_scent", "theme": "Fragrance sensitivity concern", "frequency": 8}
                ],
            },
            "competitor_intelligence": {
                "tenant_id": sample_directive.tenant_id,
                "competitor": "SerumCorp",
                "benchmark_price": "52.00",
                "active_ads": 20,
                "threat_level": "medium",
            },
        },
    )

    envelope = await engine.delegate_task(
        directive=sample_directive,
        task=task,
        query="omnichannel acquisition media plan and budget allocation",
        brand_id=sample_directive.tenant_id,
    )

    assert envelope.task_id == "task-strat-governed-1"
    assert envelope.worker_role == WorkerRole.STRATEGY
    assert envelope.confidence.point_estimate >= 0.75

    # Verify artifacts and findings
    assert "strategy:task-strat-governed-1" in envelope.generated_artifacts
    assert len(envelope.findings) > 0
    assert envelope.provenance["capability"] == "S_ALLOC"
    assert "sandbox_execution_id" in envelope.provenance
    assert envelope.provenance["sandbox_execution_id"] != ""

    # Verify sandbox lifecycle provenance was persisted
    sandbox_prov_records = [
        r for r in prov_repo.records
        if r.metadata.get("capability") == "S_ALLOC" or r.activity == "sandbox_execution"
    ]
    assert len(sandbox_prov_records) >= 1
    assert any(
        r.metadata.get("status") == "completed" and r.metadata.get("capability") == "S_ALLOC"
        for r in sandbox_prov_records
    )

    # Verify typed models
    plan = w_strat.extract_strategy_plan(envelope)
    assert plan is not None
    assert plan.total_allocated <= sample_directive.budget_cap
    assert plan.budget_ceiling == sample_directive.budget_cap
    assert len(plan.channel_allocations) == len(sample_directive.scope.allowed_channels)
    assert len(plan.funnel_stages) == 4
    assert len(plan.scenarios) == 3
    assert plan.recommended_scenario == "scenario_balanced"


@pytest.mark.asyncio
async def test_evidence_synthesizer_merges_w_strat_envelope() -> None:
    """EvidenceSynthesizer merges W_STRAT strategy proposal envelope with T16 and T17 evidence envelopes."""
    sandbox_client = create_mock_remote_sandbox()
    w_strat = StrategyAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-strat-synth",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "google", "tiktok"]),
        brand_id="acme",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    context: dict[str, object] = {
        "budget_ceiling": 40000.0,
        "claims_dossier": {
            "tenant_id": "acme",
            "claims": [{"validation_status": "SUPPORTED", "confidence": 0.9}],
        },
        "customer_voice_analysis": {
            "tenant_id": "acme",
            "objection_profiles": [{"theme": "delivery_time"}],
        },
        "competitor_intelligence": {
            "tenant_id": "acme",
            "competitor": "CompetitorZ",
            "benchmark_price": "39.99",
            "threat_level": "low",
        },
    }

    envelope_strat = await w_strat.run(grant, context)

    # Simulated T16 envelope
    envelope_prod = EvidenceEnvelope(
        task_id="task-prod-01",
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        confidence=ConfidenceInterval(point_estimate=0.90, lower_bound=0.85, upper_bound=0.95),
        evidence=["Verified claims dossier: 100% compliant."],
        findings=["All 4 claims clinically supported."],
    )

    # Simulated T17 envelope
    envelope_voice = EvidenceEnvelope(
        task_id="task-voice-01",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        confidence=ConfidenceInterval(point_estimate=0.82, lower_bound=0.70, upper_bound=0.90),
        evidence=["Customer sentiment: 78% positive."],
        findings=["Objection on delivery time identified."],
    )

    synthesizer = EvidenceSynthesizer()
    synthesized = synthesizer.synthesize([envelope_prod, envelope_voice, envelope_strat])

    assert synthesized.confidence.point_estimate >= 0.80
    assert any("Omnichannel Strategy Plan" in line for line in synthesized.evidence)
    assert any("Verified claims dossier" in line for line in synthesized.evidence)
    assert any("Customer sentiment" in line for line in synthesized.evidence)


@pytest.mark.asyncio
async def test_strategy_spend_generates_hitl_preview_and_requires_authorized_approval(sample_directive: Directive) -> None:
    """Strategy spend proposal reaches HITL as SPEND preview and cannot dispatch without authorized finance sign-off."""
    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)
    sandbox_client = create_mock_remote_sandbox(provenance_recorder=provenance_recorder)
    w_strat = StrategyAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-strat-hitl",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=sample_directive.scope,
        brand_id=sample_directive.tenant_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    context: dict[str, object] = {
        "budget_ceiling": sample_directive.budget_cap,
        "claims_dossier": {
            "tenant_id": sample_directive.tenant_id,
            "claims": [
                {
                    "claim_id": "c1",
                    "claim_text": "Clinically proven 40% reduction in fine lines",
                    "validation_status": "SUPPORTED",
                    "confidence": 0.95,
                }
            ],
        },
        "customer_voice_analysis": {
            "tenant_id": sample_directive.tenant_id,
            "objection_profiles": [
                {
                    "objection_type": "price",
                    "theme": "Price sensitivity objection",
                    "frequency": 6,
                }
            ],
        },
        "competitor_intelligence": {
            "tenant_id": sample_directive.tenant_id,
            "competitor": "SerumCorp",
            "benchmark_price": "50.00",
            "threat_level": "medium",
        },
    }

    envelope = await w_strat.run(grant, context)
    plan = w_strat.extract_strategy_plan(envelope)
    assert plan is not None

    synthesizer = EvidenceSynthesizer()
    synthesized = synthesizer.synthesize([envelope])

    preview_generator = HitlPreviewGenerator()
    preview = preview_generator.generate(
        preview_id="prev-strat-spend-1",
        evidence=synthesized,
        kind=ActionPreviewKind.SPEND,
        risk_level=RiskLevel.HIGH,
        spend_amount=plan.total_allocated,
    )
    preview.tenant_id = sample_directive.tenant_id

    coordinator = HitlCoordinator()
    coordinator.submit_for_approval(preview)

    # 1. Action preview starts PENDING and requires approval
    assert preview.requires_approval is True
    assert preview.review_status == ReviewStatus.PENDING
    assert coordinator.is_pending(preview.preview_id) is True
    assert coordinator.is_approved(preview.preview_id) is False

    # 2. Unauthorized role cannot approve spend (engineering denied for SPEND preview)
    with pytest.raises(PolicyViolationError, match="not authorized to sign off on 'spend'"):
        coordinator.decide(
            preview.preview_id,
            approved=True,
            approver="eng_lead",
            approver_role="engineering",
            tenant_id=sample_directive.tenant_id,
        )
    assert coordinator.is_approved(preview.preview_id) is False

    # 3. Tenant mismatch rejected
    with pytest.raises(PolicyViolationError, match="Tenant authority mismatch"):
        coordinator.decide(
            preview.preview_id,
            approved=True,
            approver="finance_lead",
            approver_role="finance",
            tenant_id="unauthorized_other_tenant",
        )
    assert coordinator.is_approved(preview.preview_id) is False

    # 4. Authorized finance approver successfully approves spend
    decision = coordinator.decide(
        preview.preview_id,
        approved=True,
        approver="finance_director",
        approver_role="finance",
        tenant_id=sample_directive.tenant_id,
    )
    assert decision.approved is True
    assert decision.clearance is not None
    assert decision.clearance.is_valid is True
    assert preview.review_status == ReviewStatus.APPROVED
    assert coordinator.is_approved(preview.preview_id) is True


@pytest.mark.asyncio
async def test_strategy_remote_sandbox_failure_fails_closed_without_local_fallback() -> None:
    """Configured remote sandbox failure never falls back to local micro-tools and records failure provenance."""
    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)
    client = SandboxClient(
        settings=SandboxSettings(endpoint="http://remote-sandbox.internal:8000"),
        provenance_recorder=provenance_recorder,
    )

    # Inject mock remote client whose execution fails
    mock_sandbox = MagicMock()
    mock_sandbox.file = MagicMock()
    mock_sandbox.shell = MagicMock()
    mock_sandbox.shell.exec_command.side_effect = RuntimeError("Container unreachable")
    client._sandbox = mock_sandbox

    mandate = SandboxInvocationMandate(
        task_id="task-strat-remote-fail",
        worker_role=WorkerRole.STRATEGY,
        tenant_id="tenant_01",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "15000.0", "channels": "meta,google"},
        network_policy=NetworkPolicy.DISABLED,
    )

    result = await client.invoke(mandate)
    assert result.success is False
    assert result.status.value == "failed"
    assert "Container unreachable" in (result.error or "")

    # And verify W_STRAT invocation fails closed with zero confidence envelope
    w_strat = StrategyAgent(client)
    grant = TaskGrant(
        task_id="task-strat-remote-fail-w",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant_01", allowed_channels=["meta", "google"]),
        brand_id="tenant_01",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    envelope = await w_strat.run(grant, {"budget_ceiling": 15000.0})
    assert envelope.confidence.point_estimate == 0.0
    assert any("sandbox execution failed" in e for e in envelope.evidence)

    # Directly verify that local micro-tool execution is strictly forbidden
    with pytest.raises(SandboxInvocationError, match="strictly prohibited"):
        client._execute_in_isolated_runtime(mandate)

    # Verify fail-closed: failure provenance recorded, no local fallback execution
    failed_records = [
        r for r in prov_repo.records
        if r.metadata.get("status") == "failed" or r.metadata.get("lifecycle_stage") == "failed"
    ]
    assert len(failed_records) >= 1
    assert failed_records[0].metadata.get("capability") == "S_ALLOC"
    assert failed_records[0].metadata.get("execution_id") == mandate.execution_id
    assert failed_records[0].metadata.get("task_id") == mandate.task_id


@pytest.mark.asyncio
async def test_w_strat_orchestration_e2e_lifecycle_and_w3c_prov_lineage(sample_directive: Directive) -> None:
    """Proves T5 end-to-end W_STRAT orchestration and W3C PROV lineage invariants."""
    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)
    sandbox_client = create_mock_remote_sandbox(provenance_recorder=provenance_recorder)

    w_strat = StrategyAgent(sandbox_client)
    allocation_specialist_spy = AsyncMock(wraps=w_strat.allocation_agent)
    w_strat._allocation_agent = allocation_specialist_spy
    sandbox_invoke_spy = AsyncMock(wraps=sandbox_client.invoke)
    sandbox_client.invoke = sandbox_invoke_spy

    rag_repo = FakeVectorRepository()
    rag_controller = RagController(
        HybridRetriever(rag_repo),
        FreshnessPolicy(),
        SchemaValidator(),
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    workers: dict[WorkerRole, BoundedWorkerAgent] = {
        WorkerRole.STRATEGY: w_strat,
    }

    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(rag_dispatcher, BrandPersonaResolver()),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=provenance_recorder,
        workers=workers,
    )

    task = CanonicalTaskState(
        task_id="task-strat-prov-e2e",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        cts_state={
            "budget_cap": 25000.0,
            "claims_dossier": {
                "tenant_id": sample_directive.tenant_id,
                "claims": [{"claim_id": "c1", "validation_status": "SUPPORTED", "confidence": 0.95}],
            },
            "customer_voice_analysis": {
                "tenant_id": sample_directive.tenant_id,
                "objection_profiles": [{"objection_type": "price", "frequency": 4}],
            },
            "competitor_intelligence": {
                "tenant_id": sample_directive.tenant_id,
                "competitor": "BrandX",
                "benchmark_price": "45.00",
            },
        },
    )

    # 1. Orchestrated invocation
    result = await engine.invoke_strategy_worker(
        directive=sample_directive,
        task=task,
        query="omnichannel acquisition media plan and budget allocation",
        brand_id=sample_directive.tenant_id,
    )

    # 2. Exactly one bounded allocation specialist invocation & one hardened S_ALLOC invocation
    assert allocation_specialist_spy.reason.await_count == 1
    assert sandbox_invoke_spy.await_count == 1
    assert sandbox_invoke_spy.await_args is not None
    mandate_arg = sandbox_invoke_spy.await_args[0][0]
    assert mandate_arg.capability == SandboxCapability.ALLOC
    assert mandate_arg.network_policy == NetworkPolicy.DISABLED

    # 3. Typed StrategyResultEnvelope round-trip
    assert isinstance(result, StrategyResultEnvelope)
    assert result.task_id == "task-strat-prov-e2e"
    assert result.worker_role == WorkerRole.STRATEGY
    assert result.strategy_plan is not None
    assert result.strategy_plan.total_allocated <= 25000.0
    assert len(result.channel_proposals) > 0

    # 4. Verify W3C PROV records and lineage
    records = prov_repo.records
    worker_records = [r for r in records if "worker_execution" in r.activity]
    assert len(worker_records) >= 2  # started + completed

    started_rec = next(r for r in worker_records if r.metadata.get("lifecycle_stage") == "started")
    completed_rec = next(r for r in worker_records if r.metadata.get("lifecycle_stage") == "completed")

    assert completed_rec.activity == "worker_execution"
    assert completed_rec.agent == "W_STRAT"
    assert completed_rec.entity_id == task.task_id

    # 5. Linkage to sandbox execution ID
    sb_exec_id = completed_rec.metadata.get("sandbox_execution_id")
    assert sb_exec_id is not None
    assert sb_exec_id == mandate_arg.execution_id

    # 6. W3C bundle relations & entities
    bundle = completed_rec.w3c_prov
    assert bundle is not None
    act_ids = [a["id"] for a in bundle["activities"]]
    agent_ids = [ag["id"] for ag in bundle["agents"]]
    entity_dict = {e["id"]: e for e in bundle["entities"]}

    assert any(a["id"] == f"urn:enterprise_os:activity:worker_execution:{task.task_id}:completed" for a in bundle["activities"])
    assert "urn:enterprise_os:agent:worker:W_STRAT" in agent_ids

    # Entity digests
    input_entity_id = f"urn:enterprise_os:entity:task_grant:{task.task_id}"
    output_entity_id = f"urn:enterprise_os:entity:worker_result:{task.task_id}:completed"
    assert input_entity_id in entity_dict
    assert output_entity_id in entity_dict

    input_entity = entity_dict[input_entity_id]
    output_entity = entity_dict[output_entity_id]
    assert input_entity["value_hash"] == completed_rec.metadata["input_sha256"]
    assert output_entity["value_hash"] == completed_rec.metadata["output_sha256"]

    # Relations: used, wasAssociatedWith, wasGeneratedBy
    relations = bundle["relations"]
    relation_types = [r["relation_type"] for r in relations]
    assert ProvRelationType.WAS_ASSOCIATED_WITH.value in relation_types
    assert ProvRelationType.USED.value in relation_types
    assert ProvRelationType.WAS_GENERATED_BY.value in relation_types

    # Specific relation checks
    assoc = next(r for r in relations if r["relation_type"] == ProvRelationType.WAS_ASSOCIATED_WITH.value)
    assert assoc["target_id"] == "urn:enterprise_os:agent:worker:W_STRAT"

    used_input = next(
        r for r in relations
        if r["relation_type"] == ProvRelationType.USED.value and r["target_id"] == input_entity_id
    )
    assert "worker_execution" in used_input["source_id"]

    gen_output = next(
        r for r in relations
        if r["relation_type"] == ProvRelationType.WAS_GENERATED_BY.value and r["source_id"] == output_entity_id
    )
    assert "worker_execution" in gen_output["target_id"]

    # 7. Append-only hash chain integrity & idempotency
    assert await provenance_recorder.verify_chain(sample_directive.tenant_id) is True
    chain_len_before = len(prov_repo.records)
    re_rec = await provenance_recorder.record_worker_execution(
        tenant_id=sample_directive.tenant_id,
        task_id=task.task_id,
        worker_role=task.worker_role,
        lifecycle_stage="completed",
        output_data=result,
    )
    assert re_rec.record_id == completed_rec.record_id
    assert len(prov_repo.records) == chain_len_before


@pytest.mark.asyncio
async def test_w_strat_failure_lineage_never_reports_success(sample_directive: Directive) -> None:
    """Proves that worker failures produce terminal failed lineage and never report success."""
    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)
    client = SandboxClient(
        settings=SandboxSettings(endpoint="http://remote-sandbox.internal:8000"),
        provenance_recorder=provenance_recorder,
    )

    mock_sandbox = MagicMock()
    mock_sandbox.shell = MagicMock()
    mock_sandbox.shell.exec_command.side_effect = RuntimeError("Container crashed")
    client._sandbox = mock_sandbox

    w_strat = StrategyAgent(client)
    rag_repo = FakeVectorRepository()
    rag_controller = RagController(
        HybridRetriever(rag_repo),
        FreshnessPolicy(),
        SchemaValidator(),
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    workers: dict[WorkerRole, BoundedWorkerAgent] = {WorkerRole.STRATEGY: w_strat}
    engine = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(rag_dispatcher, BrandPersonaResolver()),
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=provenance_recorder,
        workers=workers,
    )

    task = CanonicalTaskState(
        task_id="task-strat-fail-lineage",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        cts_state={"budget_cap": 10000.0},
    )

    envelope = await engine.delegate_task(
        directive=sample_directive,
        task=task,
        query="propose strategy",
        brand_id=sample_directive.tenant_id,
    )

    assert envelope.confidence.point_estimate == 0.0

    # Verify provenance recorded failure, never completed/success
    worker_records = [
        r for r in prov_repo.records
        if "worker_execution" in r.activity and r.entity_id == task.task_id
    ]
    completed_records = [
        r for r in worker_records
        if r.metadata.get("lifecycle_stage") == "completed"
    ]
    assert len(completed_records) == 0, "Failed worker execution must NEVER produce a completed record"

    failed_records = [
        r for r in worker_records
        if r.metadata.get("lifecycle_stage") == "failed"
    ]
    assert len(failed_records) == 1
    assert failed_records[0].metadata["lifecycle_stage"] == "failed"
    assert await provenance_recorder.verify_chain(sample_directive.tenant_id) is True

