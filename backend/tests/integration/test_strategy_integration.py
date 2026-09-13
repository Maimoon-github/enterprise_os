"""Integration tests for T19 Omnichannel Strategy, Funnel & Budget Allocation."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents.base import BoundedWorkerAgent
from app.agents.customer_voice import CustomerVoiceAgent
from app.agents.product_evidence import ProductEvidenceAgent
from app.agents.strategy import StrategyAgent
from app.core.exceptions import SandboxInvocationError
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
from app.schemas.agent_contracts import (
    ConfidenceInterval,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    TaskGrant,
)
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.hitl import HitlCoordinator
from app.services.provenance import ProvenanceRecorder
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from tests.conftest import FakeProvenanceRepository, FakeVectorRepository


def test_w_strat_module_has_zero_direct_persistence_or_rag_imports() -> None:
    """W_STRAT must not directly import persistence, RAG, CMS, DB, or services (Model-A Invariant)."""
    source_file = Path(__file__).resolve().parents[2] / "app" / "agents" / "strategy.py"
    tree = ast.parse(source_file.read_text(encoding="utf-8"))

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

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in disallowed_prefixes:
                    assert not alias.name.startswith(prefix), f"Disallowed direct import in W_STRAT: {alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module:
            for prefix in disallowed_prefixes:
                assert not node.module.startswith(prefix), f"Disallowed direct import in W_STRAT: {node.module}"


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
        SandboxCapability.SCRAPE,
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
    sandbox_client = SandboxClient()
    w_strat = StrategyAgent(sandbox_client)

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
        provenance_recorder=ProvenanceRecorder(FakeProvenanceRepository()),
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
    sandbox_client = SandboxClient()
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
