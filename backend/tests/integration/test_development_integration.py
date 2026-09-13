"""Integration tests for T21 UI Templates, CMS Schemas & Code Diff Engineering (W_DEV + S_CODE)."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents.base import BoundedWorkerAgent
from app.agents.development import DevelopmentAgent
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
    DevelopmentDeliverable,
    EvidenceEnvelope,
    TaskGrant,
)
from app.schemas.cms import CmsPageModel, CmsPublishState
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


def test_w_dev_module_has_zero_direct_persistence_cms_or_rag_imports() -> None:
    """W_DEV must not directly import persistence, RAG, CMS client, DB, or services (Model-A Invariant)."""
    source_file = Path(__file__).resolve().parents[2] / "app" / "agents" / "development.py"
    tree = ast.parse(source_file.read_text(encoding="utf-8"))

    disallowed_prefixes = (
        "app.persistence",
        "app.services",
        "app.mcp",
        "app.security",
        "app.integrations.llm",
        "app.integrations.cms.client",
        "app.integrations.ads",
        "app.integrations.social",
        "app.orchestration.rag_query_dispatch",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in disallowed_prefixes:
                    assert not alias.name.startswith(prefix), f"Disallowed direct import in W_DEV: {alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module:
            for prefix in disallowed_prefixes:
                assert not node.module.startswith(prefix), f"Disallowed direct import in W_DEV: {node.module}"


def test_unauthorized_capability_rejected_for_w_dev() -> None:
    """W_DEV is authorized strictly for SandboxCapability.CODE; other capabilities fail closed."""
    profile = validate_capability_access(
        capability=SandboxCapability.CODE,
        worker_role=WorkerRole.DEVELOPMENT,
        operation="generate_diff",
    )
    assert profile.allowed_worker == WorkerRole.DEVELOPMENT

    unauthorized = [
        SandboxCapability.ALLOC,
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
                worker_role=WorkerRole.DEVELOPMENT,
                operation="any",
            )


@pytest.mark.asyncio
async def test_governed_ie_grant_to_w_dev_pipeline(sample_directive: Directive) -> None:
    """Full governed execution: T06 CMS models + T15 grant -> IE -> W_DEV -> S_CODE -> Development Deliverable -> IE."""
    sandbox_client = SandboxClient()
    w_dev = DevelopmentAgent(sandbox_client)

    workers: dict[WorkerRole, BoundedWorkerAgent] = {
        WorkerRole.DEVELOPMENT: w_dev,
    }

    vector_repo = FakeVectorRepository()
    vector_repo.seed(
        tenant_id=sample_directive.tenant_id,
        text="Landing page design specification and component hierarchy.",
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
        task_id="task-dev-gov-1",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
        cts_state={
            "staged_cms_models": [
                {
                    "page_id": "page-campaign-01",
                    "tenant_id": sample_directive.tenant_id,
                    "slug": "spring-launch",
                    "title": "Spring Campaign Showcase",
                    "layout_id": "landing_v2",
                    "publish_state": "staged",
                }
            ],
            "component_name": "CampaignHero",
            "component_type": "component",
            "target_files": ["components/campaign_hero.py", "templates/campaign_hero.html"],
        },
    )

    envelope = await engine.delegate_task(
        directive=sample_directive,
        task=task,
        query="generate responsive campaign hero component and schema diff",
        brand_id=sample_directive.tenant_id,
    )

    assert envelope.task_id == "task-dev-gov-1"
    assert envelope.worker_role == WorkerRole.DEVELOPMENT
    assert envelope.confidence.point_estimate >= 0.8
    assert "diff:task-dev-gov-1" in envelope.generated_artifacts
    assert "dev:task-dev-gov-1" in envelope.generated_artifacts
    assert envelope.provenance["capability"] == "S_CODE"

    # Extract strongly typed DevelopmentDeliverable
    deliverable = w_dev.extract_development_deliverable(envelope)
    assert deliverable is not None
    assert deliverable.tenant_id == sample_directive.tenant_id
    assert deliverable.component_name == "CampaignHero"
    assert len(deliverable.ui_templates) >= 1
    assert len(deliverable.code_diffs) >= 1
    assert deliverable.code_diffs[0].ast_validated is True
    assert deliverable.security_checks_passed is True

    # Verify provenance recorded
    chain_records = await prov_repo.chain(sample_directive.tenant_id)
    assert len(chain_records) > 0
