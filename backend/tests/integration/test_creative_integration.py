"""Integration tests for T20 Creative Content Generation & Channel Adaptation (W_CREAT + S_COPY)."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.agents.base import BoundedWorkerAgent
from app.agents.creative_content import CreativeContentAgent
from app.core.exceptions import (
    ApprovalRequiredError,
    SandboxInvocationError,
    SignatureVerificationError,
)
from app.integrations.ads.base import AdsAdapter
from app.integrations.sandbox.capabilities import validate_capability_access
from app.integrations.sandbox.client import SandboxClient
from app.mcp.data_gateway import DataGateway
from app.mcp.host import McpHost
from app.mcp.outbound_gateway import OutboundGateway, canonical_dispatch_bytes
from app.orchestration.context_assembly import BrandPersonaResolver, ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import ActionPreviewKind
from app.schemas.agent_contracts import (
    CreativePackage,
    EvidenceEnvelope,
    TaskGrant,
)
from app.schemas.dispatch import DispatchDirective
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.authorization_boundary import AuthorizationBoundary
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.security.scope_evaluator import ScopeEvaluator
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


class _RecordingCreativeAdsAdapter(AdsAdapter):
    channel = "meta"

    def __init__(self) -> None:
        self.applied: list[dict[str, str]] = []

    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        self.applied.append(payload)
        return {"status_code": "200", "channel": self.channel}


def test_all_creative_specialists_have_zero_direct_persistence_rag_or_gateway_imports() -> None:
    """Model-A Invariant: All six Creative specialists must not directly import RAG, DB, CMS, MCP or persistence."""
    subagents_dir = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "agents"
        / "creative_content_engine"
        / "subagents"
    )
    disallowed_prefixes = (
        "app.persistence",
        "app.services",
        "app.mcp",
        "app.security",
        "app.integrations.cms",
        "app.integrations.ads",
        "app.integrations.social",
        "app.orchestration.rag_query_dispatch",
        "sqlalchemy",
    )

    specialist_files = [p for p in subagents_dir.glob("*.py") if p.name != "__init__.py"]
    assert len(specialist_files) == 6

    for py_file in specialist_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in disallowed_prefixes:
                        assert not alias.name.startswith(prefix), (
                            f"Disallowed direct import '{alias.name}' in specialist: {py_file.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for prefix in disallowed_prefixes:
                    assert not node.module.startswith(prefix), (
                        f"Disallowed direct import '{node.module}' in specialist: {py_file.name}"
                    )


@pytest.mark.asyncio
async def test_governed_creative_package_to_hitl_outbound_mcp_flow(
    sample_directive: Directive, ed25519_keypair
) -> None:
    """T7 Lineage & Outbound Governance: CreativePackage -> IE -> HITL -> Outbound MCP."""
    private_key, public_pem = ed25519_keypair
    sample_directive = sample_directive.model_copy(
        update={"scope": sample_directive.scope.model_copy(update={"allowed_channels": ["meta"]})}
    )
    w_creat = CreativeContentAgent()
    workers: dict[WorkerRole, BoundedWorkerAgent] = {
        WorkerRole.CREATIVE_CONTENT: w_creat,
    }

    vector_repo = FakeVectorRepository()
    vector_repo.seed(
        tenant_id=sample_directive.tenant_id,
        text="Brand Persona Voice Guide: Tone is authoritative and bold.",
    )
    rag_controller = RagController(
        HybridRetriever(vector_repo), FreshnessPolicy(), SchemaValidator()
    )
    rag_dispatcher = RagQueryDispatcher(rag_controller)

    prov_repo = FakeProvenanceRepository()
    provenance_recorder = ProvenanceRecorder(prov_repo)

    hitl_coordinator = HitlCoordinator()
    crypto_validator = CryptographicValidator(public_pem)
    ads_adapter = _RecordingCreativeAdsAdapter()
    outbound_gateway = OutboundGateway(
        hitl_coordinator, crypto_validator, ads_adapters={"meta": ads_adapter}
    )
    data_gateway = DataGateway(vector_repo, AuthorizationBoundary(ScopeEvaluator()))
    mcp_host = McpHost(data_gateway, outbound_gateway)

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

    task = CanonicalTaskState(
        task_id="task-creat-outbound-1",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.PENDING,
        cts_state={
            "claims_dossier": {
                "tenant_id": sample_directive.tenant_id,
                "claims": [
                    {
                        "claim_id": "c-outbound-01",
                        "claim_text": "Verified 40% performance improvement.",
                        "validation_status": "SUPPORTED",
                    }
                ],
            },
            "strategy_plan": {
                "tenant_id": sample_directive.tenant_id,
                "channels": ["meta"],
                "target_audience": "enterprise architects",
            },
        },
    )

    # 1. Directive delegates task to W_CREAT coordinator
    envelope = await engine.delegate_task(
        directive=sample_directive,
        task=task,
        query="generate cross-channel ad creative",
        brand_id=sample_directive.tenant_id,
    )
    assert envelope.task_id == "task-creat-outbound-1"
    package = w_creat.extract_creative_package(envelope)
    assert package is not None
    assert package.qa_status == "PASS"

    # 2. Intelligence Engine builds mandatory human-review preview
    preview = await engine.build_preview(
        [envelope], kind=ActionPreviewKind.COPY, risk_level=RiskLevel.LOW
    )
    assert preview.requires_approval is True
    assert hitl_coordinator.is_pending(preview.preview_id)

    # 3. Unapproved outbound actuation fails closed
    unsigned_dispatch = DispatchDirective(
        dispatch_id="dispatch-creat-1",
        task_id=task.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="pending",
        approved_at=datetime.now(UTC),
        channel="meta",
        payload={"campaign_id": "meta-camp-42", "headline": package.ad_copy_variants[0].headline},
    )
    with pytest.raises(ApprovalRequiredError):
        await engine.dispatch_after_approval(unsigned_dispatch)

    # 4. Outbound actuation with invalid signature fails closed
    hitl_coordinator.decide(preview.preview_id, approved=True, approver="[email protected]")
    bad_sig_dispatch = unsigned_dispatch.model_copy(
        update={"approved_by": "[email protected]", "signature": "invalid-sig"}
    )
    with pytest.raises(SignatureVerificationError):
        await engine.dispatch_after_approval(bad_sig_dispatch)

    # 5. Approved and cryptographically signed dispatch actuates through OutboundGateway
    dispatch_to_sign = unsigned_dispatch.model_copy(update={"approved_by": "[email protected]"})
    signature = sign_payload(canonical_dispatch_bytes(dispatch_to_sign), private_key)
    valid_dispatch = dispatch_to_sign.model_copy(update={"signature": signature})

    result = await engine.dispatch_after_approval(valid_dispatch)
    assert result == {"status_code": "200", "channel": "meta"}
    assert len(ads_adapter.applied) == 1
    assert ads_adapter.applied[0]["campaign_id"] == "meta-camp-42"

    # 6. Provenance audit chain integrity intact
    assert await provenance_recorder.verify_chain(sample_directive.tenant_id) is True

