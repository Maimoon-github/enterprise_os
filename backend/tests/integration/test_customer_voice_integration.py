"""Integration tests for T17: Customer Voice Ingestion, Sentiment & Objection Analysis."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents.base import BoundedWorkerAgent
from app.agents.customer_voice import CustomerVoiceAgent
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
from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import Directive, TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.hitl import HitlCoordinator
from app.services.provenance import ProvenanceRecorder
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from tests.conftest import FakeProvenanceRepository, FakeVectorRepository


def test_w_voice_module_has_zero_direct_persistence_or_rag_imports() -> None:
    """W_VOICE must not directly import persistence, RAG, CMS, DB, or services."""
    source_file = Path(__file__).resolve().parents[2] / "app" / "agents" / "customer_voice.py"
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
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in disallowed_prefixes:
                    assert not alias.name.startswith(prefix), f"Disallowed import: {alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module:
            for prefix in disallowed_prefixes:
                assert not node.module.startswith(prefix), f"Disallowed import: {node.module}"


def test_unauthorized_capability_rejected_for_w_voice() -> None:
    """W_VOICE is only authorized for SandboxCapability.PARSE; any other capability fails closed."""
    # PARSE is authorized for CUSTOMER_VOICE
    profile = validate_capability_access(
        capability=SandboxCapability.PARSE,
        worker_role=WorkerRole.CUSTOMER_VOICE,
        operation="analyze_customer_voice",
    )
    assert profile.allowed_worker == WorkerRole.CUSTOMER_VOICE

    # CODE, VAL, ALLOC, COPY, SCRAPE, ATTR must be rejected for CUSTOMER_VOICE
    unauthorized_capabilities = [
        SandboxCapability.CODE,
        SandboxCapability.VAL,
        SandboxCapability.ALLOC,
        SandboxCapability.COPY,
        SandboxCapability.SCRAPE,
        SandboxCapability.ATTR,
    ]

    for cap in unauthorized_capabilities:
        with pytest.raises(SandboxInvocationError, match="Capability access denied"):
            validate_capability_access(
                capability=cap,
                worker_role=WorkerRole.CUSTOMER_VOICE,
            )


@pytest.mark.asyncio
async def test_governed_ie_grant_to_w_voice_pipeline(sample_directive: Directive) -> None:
    """Full governed execution: IE Grant -> W_VOICE coordinator -> EvidenceEnvelope -> IE."""
    w_voice = CustomerVoiceAgent()

    workers: dict[WorkerRole, BoundedWorkerAgent] = {
        WorkerRole.CUSTOMER_VOICE: w_voice,
    }

    vector_repo = FakeVectorRepository()
    vector_repo.seed(
        tenant_id=sample_directive.tenant_id,
        text="Customer review for solar pack: 'Great solar charging efficiency, but customer support took 3 days to answer replacement question.'",
        source="customer_reviews_db",
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
        task_id="task-voice-governed-1",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.CUSTOMER_VOICE,
        status=TaskStatus.PENDING,
        cts_state={
            "feedback_items": [
                {
                    "item_id": "review-sol-9",
                    "text": "Great solar charging efficiency, but customer support took 3 days to answer replacement question.",
                    "source_type": "product_review",
                    "channel": "marketplace",
                }
            ]
        },
    )

    envelope = await engine.delegate_task(
        directive=sample_directive,
        task=task,
        query="customer voice review solar pack",
        brand_id="acme",
    )

    assert envelope.task_id == "task-voice-governed-1"
    assert envelope.worker_role == WorkerRole.CUSTOMER_VOICE
    assert envelope.confidence.point_estimate >= 0.7

    # Verify artifacts and findings
    assert "voice:task-voice-governed-1" in envelope.generated_artifacts
    assert len(envelope.findings) > 0
    assert envelope.provenance["capability"] == "NONE"

    # Verify typed models
    analysis = w_voice.extract_customer_voice_analysis(envelope)
    assert analysis is not None
    assert analysis.total_items_analyzed >= 1

    payload = w_voice.extract_customer_voice_payload(envelope)
    assert payload is not None
    assert payload.records_analyzed >= 1


@pytest.mark.asyncio
async def test_evidence_synthesizer_merges_w_voice_envelope() -> None:
    """Synthesizer successfully merges W_VOICE customer voice evidence into consolidated multi-worker synthesis."""
    w_voice = CustomerVoiceAgent()

    grant = TaskGrant(
        task_id="task-voice-synth",
        worker_role=WorkerRole.CUSTOMER_VOICE,
        tenant_scope=TenantScope(tenant_id="acme"),
        brand_id="acme",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    context: dict[str, object] = {
        "items": [
            {
                "item_id": "ticket-feedback-1",
                "text": "Loved the fast delivery and excellent packaging. Highly recommended!",
                "source_type": "review",
            }
        ]
    }

    envelope = await w_voice.run(grant, context)
    assert envelope.confidence.point_estimate >= 0.8

    synthesizer = EvidenceSynthesizer()
    synthesized = synthesizer.synthesize([envelope])

    assert synthesized.task_id == "task-voice-synth"
    assert synthesized.confidence.point_estimate >= 0.8
    assert any("Customer Voice" in line for line in synthesized.evidence)
