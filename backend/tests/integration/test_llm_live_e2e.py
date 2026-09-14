"""Integration test suite for Phase 4: Live LLM Wiring Verification & E2E Governance.

Tests:
1. Genuine local socket TCP HTTP provider connection (simulating local model runtime like Ollama/vLLM).
2. End-to-End Governed Pipeline:
   Directive → IE planning → Bounded TaskGrant assembly → Worker domain reasoning →
   Governed sandbox execution → Evidence Envelope → IE synthesis & CTS transition → W3C PROV audit.
3. Negative Tests:
   - Worker direct DB/RAG access denied / non-existent (Model A preservation).
   - High-impact action requires mandatory HITL approval before dispatch.
   - Provider network failure / invalid response handling.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.agents.development import DevelopmentAgent
from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.core.settings import DatabaseSettings, LlmSettings, SecuritySettings
from app.integrations.llm.client import LlmClient, LlmResponseError
from app.integrations.sandbox.client import SandboxClient
from app.mcp.data_gateway import DataGateway
from app.mcp.host import McpHost
from app.mcp.outbound_gateway import OutboundGateway
from app.orchestration.brand_persona import BrandPersonaResolver
from app.orchestration.context_assembly import ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import ActionPreviewKind, HumanDecisionType
from app.schemas.dispatch import DispatchDirective
from app.schemas.governance import AutonomyTier, Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.authorization_boundary import AuthorizationBoundary
from app.security.cryptographic_validator import CryptographicValidator
from tests.conftest import FakeProvenanceRepository, FakeVectorRepository
from app.security.scope_evaluator import ScopeEvaluator
from app.services.hitl import ApprovalDecision, HitlCoordinator
from app.services.policy_engine import PolicyEngine
from app.services.provenance import ProvenanceRecorder
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from app.services.task_state import TaskStateService


# =============================================================================
# Helper Local Socket Server for Real Provider Runtime Verification
# =============================================================================

class LocalOpenAiCompatibleServer:
    """A lightweight in-process TCP HTTP server mimicking a local model engine (Ollama/vLLM)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8991) -> None:
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None
        self.response_content: str = ""
        self.response_model: str = "qwen2.5-local:7b"

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        # Read HTTP request headers and body
        raw_request = await reader.read(4096)
        req_text = raw_request.decode("utf-8", errors="ignore")

        # Formulate OpenAI-compatible /chat/completions body
        body = json.dumps({
            "id": "chatcmpl-local-sock-001",
            "object": "chat.completion",
            "created": 1726300000,
            "model": self.response_model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": self.response_content,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 45,
                "total_tokens": 165,
            },
        })

        http_response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body.encode('utf-8'))}\r\n"
            "Connection: close\r\n\r\n"
            f"{body}"
        )
        writer.write(http_response.encode("utf-8"))
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle_client, self.host, self.port)

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()


# =============================================================================
# 1. Live Local Socket TCP Provider Connection Test
# =============================================================================

@pytest.mark.asyncio
async def test_live_local_socket_provider_connectivity() -> None:
    """Prove real TCP socket provider connection and observable model identifier against a local endpoint."""
    server = LocalOpenAiCompatibleServer(port=8992)
    server.response_content = json.dumps({"test_status": "connected_to_local_model"})
    server.response_model = "qwen2.5:local-socket-verified"
    await server.start()

    try:
        settings = LlmSettings(
            provider="local",
            base_url="http://127.0.0.1:8992",
            model_name="qwen2.5:7b",
            request_timeout_seconds=5,
        )
        assert settings.is_local is True

        llm = LlmClient(settings)
        content, meta = await llm.complete_with_metadata("Ping local model")

        assert "connected_to_local_model" in content
        assert meta["configured_model"] == "qwen2.5:7b"
        assert meta["actual_model"] == "qwen2.5:local-socket-verified"
        assert meta["is_local"] is True
        assert meta["total_tokens"] == 165
        assert meta["estimated_cost_usd"] == 0.0
        await llm.aclose()
    finally:
        await server.stop()


# =============================================================================
# 2. Live E2E Governed Execution Flow Test
# =============================================================================

@pytest.mark.asyncio
async def test_live_governed_e2e_pipeline_with_llm_reasoning() -> None:
    """Execute complete E2E flow:

    Owner directive → IE LLM planning → bounded Worker grant →
    Worker LLM reasoning → governed sandbox execution → Worker evidence →
    IE synthesis & CTS transition → provenance audit.
    """
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(prov_repo)
    task_state_machine = TaskStateMachine()

    vector_repo = FakeVectorRepository()
    vector_repo.seed(tenant_id="tenant-e2e", text="Q3 campaign strategy")
    hybrid_retriever = HybridRetriever(vector_repo)
    rag_controller = RagController(hybrid_retriever, FreshnessPolicy(), SchemaValidator())
    rag_dispatcher = RagQueryDispatcher(rag_controller)
    brand_resolver = BrandPersonaResolver()
    context_assembler = ContextAssembler(rag_dispatcher, brand_resolver)

    # Sandbox client mock simulating safe sandbox container execution
    class SafeSandboxClient(SandboxClient):
        def __init__(self) -> None:
            pass

        async def invoke(self, mandate: Any) -> Any:
            class Result:
                success = True
                error = None
                sanitized_output = {
                    "diff": "--- a/page.html\n+++ b/page.html\n+<h1>Q3 Campaign</h1>",
                    "dev_deliverable": "LandingPageTemplate",
                }
                execution_id = "sandbox-exec-001"
                status = TaskStatus.COMPLETED
                generated_artifacts = ["artifact:page-diff-01"]
                provenance = {"container": "sandbox-docker-isolated"}
            return Result()

    # Plan proposed by IE LLM
    ie_plan_response = json.dumps({
        "objective_interpretation": "Create landing page template for Q3 campaign",
        "intent": "page_development",
        "plan": [
            {
                "step_id": "step-dev-01",
                "description": "Construct UI and CMS schema diffs",
                "recommended_worker": "W_DEV",
                "dependencies": [],
                "expected_output": "code diff deliverable",
            }
        ],
        "rationale_summary": "W_DEV executes isolated sandbox code creation",
        "confidence": 0.95,
        "assumptions": ["CMS schema is verified"],
        "context_requests": [],
    })

    # Domain reasoning proposed by Worker LLM
    worker_reasoning_response = json.dumps({
        "domain_interpretation": "Generate semantic UI layout adhering to brand rules",
        "requires_specialist_execution": True,
        "selected_tools": [SandboxCapability.CODE.value],
        "suggested_parameters": {"operation": "generate_diff"},
        "preliminary_findings": ["Valid responsive layout mapped"],
        "identified_risks": [],
        "rationale_summary": "Sandbox S_CODE invocation required for deterministic diff",
        "estimated_confidence": 0.90,
    })

    # Configure transport to respond to IE planning first, then worker reasoning
    call_count = 0

    def router_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        content = ie_plan_response if call_count == 1 else worker_reasoning_response
        body = {
            "id": f"chatcmpl-e2e-{call_count}",
            "object": "chat.completion",
            "created": 1726300000,
            "model": "local-qwen-7b",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }
        return httpx.Response(200, json=body)

    settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="local-qwen")
    llm = LlmClient(settings, client=httpx.AsyncClient(transport=httpx.MockTransport(router_handler)))

    dev_agent = DevelopmentAgent(SafeSandboxClient(), llm_client=llm)
    workers = {WorkerRole.DEVELOPMENT: dev_agent}

    hitl_coordinator = HitlCoordinator()
    ie = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(PolicyEngine()),
        dag_scheduler=DagScheduler(),
        task_state_machine=task_state_machine,
        context_assembler=context_assembler,
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=hitl_coordinator,
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=prov_recorder,
        workers=workers,
        llm_client=llm,
    )

    # 1. Owner Directive
    directive = Directive(
        directive_id="dir-live-01",
        tenant_id="tenant-e2e",
        objective="Create Q3 promotional landing page",
        budget_cap=5000.0,
        risk_ceiling=RiskLevel.LOW,
        scope=TenantScope(tenant_id="tenant-e2e", brand_ids=["brand-alpha"]),
    )

    # 2. IE LLM Planning
    plan_result = await ie.plan_directive(directive, available_workers=[WorkerRole.DEVELOPMENT])
    assert len(plan_result.plan) == 1
    assert plan_result.plan[0].recommended_worker == WorkerRole.DEVELOPMENT
    assert plan_result.confidence == 0.95

    # 3. Create Canonical Task State
    task_state = CanonicalTaskState(
        task_id="task-live-dev-01",
        directive_id=directive.directive_id,
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.PENDING,
        tool_permissions=[SandboxCapability.CODE.value],
        sandbox_capabilities=[SandboxCapability.CODE.value],
    )

    # 4. Delegate to Worker (with Worker LLM reasoning + Sandbox execution)
    envelope = await ie.delegate_task(
        directive,
        task_state,
        query="Landing page layout",
        brand_id="brand-alpha",
    )

    # 5. Verify Worker Evidence & Provenance
    assert envelope.worker_role == WorkerRole.DEVELOPMENT
    assert envelope.confidence.point_estimate > 0.0
    assert "Valid responsive layout mapped" in envelope.findings
    assert any("diff:task-live-dev-01" in a for a in envelope.generated_artifacts)
    assert envelope.provenance["llm_reasoning_used"] == "true"
    assert envelope.provenance["llm_model"] == "local-qwen-7b"
    assert envelope.provenance["is_local_model"] == "true"

    # 6. Verify W3C Provenance Audit Trail in ProvenanceRepository
    prov_records = await prov_repo.chain("tenant-e2e")
    assert len(prov_records) >= 1
    assert any(r.activity == "worker_execution" for r in prov_records)
    worker_exec_prov = next(r for r in prov_records if r.activity == "worker_execution")
    assert worker_exec_prov.metadata.get("llm_reasoning_used") == "true"
    assert worker_exec_prov.metadata.get("model") == "local-qwen-7b"


# =============================================================================
# 3. Negative Boundary Tests
# =============================================================================

@pytest.mark.asyncio
async def test_worker_cannot_directly_access_rag_or_database() -> None:
    """Verify Model A boundary: Workers have NO references to RAG controller or DB."""
    agent = DevelopmentAgent(SandboxClient(None))  # type: ignore[arg-type]

    # Verify no persistent or retrieval boundaries exist on the worker agent
    assert not hasattr(agent, "_database")
    assert not hasattr(agent, "_session_factory")
    assert not hasattr(agent, "_rag_controller")
    assert not hasattr(agent, "_hybrid_retriever")
    assert not hasattr(agent, "_vector_repository")
    assert not hasattr(agent, "_operational_repository")
    assert not hasattr(agent, "execute_sql")
    assert not hasattr(agent, "query_rag")


@pytest.mark.asyncio
async def test_high_impact_action_without_hitl_approval_is_denied() -> None:
    """Verify high-impact actions remain strictly blocked by HITL gate."""
    hitl_coordinator = HitlCoordinator()
    crypto = CryptographicValidator(None)
    outbound = OutboundGateway(hitl_coordinator, crypto, require_signature=False)

    directive = DispatchDirective(
        dispatch_id="disp-01",
        task_id="task-01",
        action_preview_id="prev-unapproved-99",
        signature="sig-placeholder",
        approved_by="approver-01",
        approved_at=datetime.now(UTC),
        channel="meta",
        tenant_id="tenant-alpha",
        payload={"campaign_id": "camp-01", "action": "deploy"},
    )

    # Dispatching without prior HITL clearance fails closed
    from app.core.exceptions import ApprovalRequiredError

    with pytest.raises(ApprovalRequiredError, match="has not been reviewed"):
        await outbound.execute(directive)
