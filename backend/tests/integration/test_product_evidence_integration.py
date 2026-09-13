"""Integration tests for T16 Product Formulation, Evidence & Compliance Verification."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents.product_evidence import ProductEvidenceAgent
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
from app.schemas.agent_contracts import ClaimValidationStatus, TaskGrant
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxInvocationMandate
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.hitl import HitlCoordinator
from app.services.provenance import ProvenanceRecorder
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from tests.conftest import FakeProvenanceRepository, FakeVectorRepository


def test_w_prod_module_has_zero_direct_persistence_or_rag_imports() -> None:
    """W_PROD must not directly import persistence, RAG, CMS, DB, or services."""
    source_file = Path("app/agents/product_evidence.py")
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


def test_unauthorized_capability_rejected_for_w_prod() -> None:
    """W_PROD is only authorized for SandboxCapability.VAL; any other capability fails closed."""
    # VAL is authorized for PRODUCT_EVIDENCE
    profile = validate_capability_access(
        capability=SandboxCapability.VAL,
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        operation="validate_product_dossier",
    )
    assert profile.allowed_worker == WorkerRole.PRODUCT_EVIDENCE

    # CODE, SCRAPE, ALLOC, COPY, PARSE, ATTR must be rejected for PRODUCT_EVIDENCE
    unauthorized_capabilities = [
        SandboxCapability.CODE,
        SandboxCapability.SCRAPE,
        SandboxCapability.ALLOC,
        SandboxCapability.COPY,
        SandboxCapability.PARSE,
        SandboxCapability.ATTR,
    ]

    for cap in unauthorized_capabilities:
        with pytest.raises(SandboxInvocationError, match="Capability access denied"):
            validate_capability_access(
                capability=cap,
                worker_role=WorkerRole.PRODUCT_EVIDENCE,
            )


@pytest.mark.asyncio
async def test_governed_ie_grant_to_w_prod_pipeline(sample_directive: Directive) -> None:
    """Full governed execution: IE Grant -> W_PROD -> S_VAL in sandbox -> EvidenceEnvelope -> IE."""
    sandbox_client = SandboxClient()
    w_prod = ProductEvidenceAgent(sandbox_client)

    workers = {
        WorkerRole.PRODUCT_EVIDENCE: w_prod,
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
        task_id="task-prod-governed-1",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        status=TaskStatus.PENDING,
        cts_state={
            "claim": "Demonstrated 40% reduction in fine lines across 30 subjects with bio-peptide formulation. *Results may vary.",
            "required_disclaimer": "*Results may vary.",
        },
    )

    envelope = await engine.delegate_task(
        directive=sample_directive,
        task=task,
        query="bio-peptide clinical trial results and claims",
        brand_id="acme",
    )

    assert envelope.task_id == "task-prod-governed-1"
    assert envelope.worker_role == WorkerRole.PRODUCT_EVIDENCE
    assert envelope.confidence.point_estimate >= 0.7

    # Verify artifacts and findings
    assert "dossier:task-prod-governed-1" in envelope.generated_artifacts
    assert len(envelope.findings) > 0
    assert envelope.provenance["capability"] == "S_VAL"

    # Verify typed models
    dossier = w_prod.extract_claims_dossier(envelope)
    assert dossier is not None
    assert dossier.total_claims >= 1

    spec = w_prod.extract_product_specification(envelope)
    assert spec is not None
    assert spec.validation_status == "VALIDATED"


@pytest.mark.asyncio
async def test_evidence_synthesizer_merges_w_prod_envelope(sample_directive: Directive) -> None:
    """Synthesizer successfully merges W_PROD claims dossier evidence into consolidated multi-worker synthesis."""
    sandbox_client = SandboxClient()
    w_prod = ProductEvidenceAgent(sandbox_client)

    grant = TaskGrant(
        task_id="task-prod-synth",
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        tenant_scope=TenantScope(tenant_id="acme"),
        brand_id="acme",
        validated_evidence=[
            {
                "doc_id": "doc-pep",
                "tenant_id": "acme",
                "text": "Tested peptide active ingredient shows 38% firming effect. *Results based on 4-week study.",
            }
        ],
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    context = {
        "claims": [
            {
                "id": "c-1",
                "text": "Clinically tested to improve firming by 38%. *Results based on 4-week study.",
                "evidence_ids": ["doc-pep"],
            }
        ],
        "required_disclaimer": "*Results based on 4-week study.",
    }

    envelope = await w_prod.run(grant, context)
    assert envelope.confidence.point_estimate >= 0.8

    synthesizer = EvidenceSynthesizer()
    synthesized = synthesizer.synthesize([envelope])

    assert synthesized.task_id == "task-prod-synth"
    assert synthesized.confidence.point_estimate >= 0.8
    assert any("Claims Dossier" in line for line in synthesized.evidence)
