"""Integration tests for T20 Creative Content Generation & Channel Adaptation (W_CREAT + S_COPY)."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents.base import BoundedWorkerAgent
from app.agents.creative_content import CreativeContentAgent
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
    CreativePackage,
    EvidenceEnvelope,
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


def test_w_creat_module_has_zero_direct_persistence_or_rag_imports() -> None:
    """W_CREAT must not directly import persistence, RAG, CMS, DB, or services (Model-A Invariant)."""
    source_file = Path(__file__).resolve().parents[2] / "app" / "agents" / "creative_content.py"
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
                    assert not alias.name.startswith(prefix), f"Disallowed direct import in W_CREAT: {alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module:
            for prefix in disallowed_prefixes:
                assert not node.module.startswith(prefix), f"Disallowed direct import in W_CREAT: {node.module}"


def test_unauthorized_capability_rejected_for_w_creat() -> None:
    """W_CREAT is authorized strictly for SandboxCapability.COPY; other capabilities fail closed."""
    profile = validate_capability_access(
        capability=SandboxCapability.COPY,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        operation="generate_variants",
    )
    assert profile.allowed_worker == WorkerRole.CREATIVE_CONTENT

    unauthorized = [
        SandboxCapability.CODE,
        SandboxCapability.ALLOC,
        SandboxCapability.VAL,
        SandboxCapability.SCRAPE,
        SandboxCapability.PARSE,
        SandboxCapability.ATTR,
    ]
    for cap in unauthorized:
        with pytest.raises(SandboxInvocationError, match="Capability access denied"):
            validate_capability_access(
                capability=cap,
                worker_role=WorkerRole.CREATIVE_CONTENT,
                operation="any",
            )


@pytest.mark.asyncio
async def test_governed_ie_grant_to_w_creat_pipeline(sample_directive: Directive) -> None:
    """Full governed execution: T16 claims + T19 strategy -> IE Grant -> W_CREAT -> S_COPY -> Creative EvidenceEnvelope -> IE."""
    sample_directive = sample_directive.model_copy(
        update={"scope": sample_directive.scope.model_copy(update={"allowed_channels": ["meta", "linkedin"]})}
    )
    w_creat = CreativeContentAgent()

    workers: dict[WorkerRole, BoundedWorkerAgent] = {
        WorkerRole.CREATIVE_CONTENT: w_creat,
    }

    vector_repo = FakeVectorRepository()
    vector_repo.seed(
        tenant_id=sample_directive.tenant_id,
        text="Brand Persona Voice Guide: Tone is authoritative and bold. Required disclaimer: *Clinically evaluated.",
    )
    rag_controller = RagController(
        HybridRetriever(vector_repo), FreshnessPolicy(), SchemaValidator()
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)

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
        task_id="task-creat-gov-1",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.PENDING,
        cts_state={
            "claims_dossier": {
                "tenant_id": sample_directive.tenant_id,
                "claims": [
                    {
                        "claim_id": "claim-omega-01",
                        "claim_text": "Demonstrated 45% latency reduction under load.",
                        "validation_status": "SUPPORTED",
                        "confidence": 0.96,
                    }
                ],
            },
            "strategy_plan": {
                "tenant_id": sample_directive.tenant_id,
                "plan_id": "strat-gov-plan",
                "channel_allocations": [
                    {"channel": "linkedin", "allocated_amount": 12000.0, "percentage_of_total": 0.60},
                    {"channel": "meta", "allocated_amount": 8000.0, "percentage_of_total": 0.40},
                ],
                "target_audience": "enterprise architects",
            },
            "policy_constraints": ["prohibit:miracle", "prohibit:guarantee"],
        },
    )

    envelope = await engine.delegate_task(
        directive=sample_directive,
        task=task,
        query="generate cross-channel ad copy and visual briefs",
        brand_id=sample_directive.tenant_id,
    )

    assert envelope.task_id == "task-creat-gov-1"
    assert envelope.worker_role == WorkerRole.CREATIVE_CONTENT
    assert envelope.confidence.point_estimate >= 0.8
    assert "creative:task-creat-gov-1" in envelope.generated_artifacts
    assert "copy:task-creat-gov-1" in envelope.generated_artifacts
    assert envelope.provenance["capability"] == "NONE"

    # Extract strongly typed CreativePackage
    package = w_creat.extract_creative_package(envelope)
    assert package is not None
    assert package.tenant_id == sample_directive.tenant_id
    assert len(package.ad_copy_variants) >= 2
    assert len(package.visual_briefs) >= 2
    assert len(package.schedules) >= 2

    # Verify claim grounding
    for variant in package.ad_copy_variants:
        assert "claim-omega-01" in variant.source_claim_ids

    # Verify audit provenance recorded
    chain_records = await prov_repo.chain(sample_directive.tenant_id)
    assert len(chain_records) > 0
