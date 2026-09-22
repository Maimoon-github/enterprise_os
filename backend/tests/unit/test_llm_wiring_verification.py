"""Unit tests verifying Phase 4 LLM wiring, runtime, boundaries, and governance.

Covers:
- Provider connection, observable model identity, token/cost metadata, local model priority.
- Failure handling: missing credentials, provider timeout, invalid JSON schema.
- Intelligence Engine bounded planning & worker selection without bypassing PAB/CTS.
- Bounded domain reasoning across all seven worker agents.
- Governed tool calling: fail-closed rejection of unauthorized tools, cross-tenant leaks, budget overruns.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from app.agents.base import BoundedWorkerAgent, WorkerReasoningOutput
from app.agents.competitor_intel import CompetitorIntelAgent
from app.agents.creative_content import CreativeContentAgent
from app.agents.customer_voice import CustomerVoiceAgent
from app.agents.development import DevelopmentAgent
from app.agents.learning_performance import LearningPerformanceAgent
from app.agents.product_evidence import ProductEvidenceAgent
from app.agents.strategy import StrategyAgent
from app.core.exceptions import ConfigurationError, PolicyViolationError
from app.core.settings import LlmSettings
from app.integrations.llm.client import LlmClient, LlmResponseError
from app.integrations.sandbox.client import SandboxClient
from app.orchestration.context_assembly import ContextAssembler
from app.orchestration.dag_scheduler import DagScheduler
from app.orchestration.evidence_synthesis import EvidenceSynthesizer
from app.orchestration.hitl_preview_generator import HitlPreviewGenerator
from app.orchestration.intelligence_engine import (
    IntelligenceEngine,
    IntelligenceRequest,
    IntelligenceResult,
    InvalidIntelligenceOutputError,
    PlanStep,
)
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.agent_contracts import TaskGrant
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.hitl import HitlCoordinator
from app.services.policy_engine import PolicyEngine
from app.services.provenance import ProvenanceRecorder


# =============================================================================
# Helper Fixtures & Mock Transports
# =============================================================================

def _build_mock_chat_transport(
    content: str,
    *,
    model: str = "local-llama-3-8b",
    prompt_tokens: int = 120,
    completion_tokens: int = 60,
    status_code: int = 200,
    delay_timeout: bool = False,
) -> httpx.MockTransport:
    """Return an HTTP mock transport simulating OpenAI-compatible /chat/completions."""

    def handler(request: httpx.Request) -> httpx.Response:
        if delay_timeout:
            raise httpx.ReadTimeout("Connection timed out", request=request)

        body = {
            "id": "chatcmpl-test-001",
            "object": "chat.completion",
            "created": 1726300000,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }
        return httpx.Response(status_code=status_code, json=body)

    return httpx.MockTransport(handler)


def _make_sample_grant(
    role: WorkerRole,
    capability: SandboxCapability,
    *,
    task_id: str = "task-llm-01",
    tenant_id: str = "tenant-alpha",
    token_budget: int = 10000,
    tools: list[str] | None = None,
) -> TaskGrant:
    return TaskGrant(
        task_id=task_id,
        worker_role=role,
        tenant_scope=TenantScope(tenant_id=tenant_id),
        brand_id="brand-01",
        objective="Execute bounded domain objective",
        task_scope="domain_scope",
        task_slice="slice_01",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        tool_permissions=tools or [capability.value],
        sandbox_capabilities=[capability.value],
        token_budget=token_budget,
    )


# =============================================================================
# 1. Provider Runtime Verification Tests
# =============================================================================

@pytest.mark.asyncio
async def test_local_model_runtime_connectivity_and_observable_identity() -> None:
    """Verify local-first model connectivity, observable model ID, and 0-cost local metadata."""
    settings = LlmSettings(
        provider="local",
        base_url="http://localhost:11434/v1",
        model_name="qwen2.5:7b",
        request_timeout_seconds=30,
    )
    assert settings.is_local is True

    transport = _build_mock_chat_transport(
        "Local reasoning completion",
        model="qwen2.5:7b-observed",
        prompt_tokens=85,
        completion_tokens=42,
    )
    client = httpx.AsyncClient(transport=transport)
    llm = LlmClient(settings, client=client)

    content, metadata = await llm.complete_with_metadata("Analyze prompt")

    assert content == "Local reasoning completion"
    assert metadata["configured_model"] == "qwen2.5:7b"
    assert metadata["actual_model"] == "qwen2.5:7b-observed"
    assert metadata["is_local"] is True
    assert metadata["prompt_tokens"] == 85
    assert metadata["completion_tokens"] == 42
    assert metadata["total_tokens"] == 127
    assert metadata["estimated_cost_usd"] == 0.0  # Local models incur zero direct API cost


@pytest.mark.asyncio
async def test_cloud_provider_cost_and_credential_enforcement() -> None:
    """Verify cloud providers calculate token cost and fail closed if credentials are missing."""
    # 1. Missing credentials fail closed
    missing_key_settings = LlmSettings(
        provider="openai",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o",
        api_key=None,
    )
    assert missing_key_settings.is_local is False
    llm_unauth = LlmClient(missing_key_settings)
    with pytest.raises(ConfigurationError, match="LLM_API_KEY must be configured"):
        await llm_unauth.complete("test")

    # 2. Configured credentials calculate cost
    auth_settings = LlmSettings(
        provider="openai",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o",
        api_key="sk-test-key-12345",
        cost_per_million_input_tokens=5.0,
        cost_per_million_output_tokens=15.0,
    )
    transport = _build_mock_chat_transport(
        "Cloud response",
        model="gpt-4o-2024-08-06",
        prompt_tokens=1000,
        completion_tokens=500,
    )
    llm_auth = LlmClient(auth_settings, client=httpx.AsyncClient(transport=transport))
    _, meta = await llm_auth.complete_with_metadata("Hello cloud")
    assert meta["actual_model"] == "gpt-4o-2024-08-06"
    assert meta["is_local"] is False
    # (1000 * 5.0 + 500 * 15.0) / 1,000,000 = (5000 + 7500) / 1,000,000 = 0.0125
    assert meta["estimated_cost_usd"] == 0.0125


@pytest.mark.asyncio
async def test_provider_timeout_error_handling() -> None:
    """Verify provider timeout is safely caught and wrapped in LlmResponseError."""
    settings = LlmSettings(
        provider="local",
        base_url="http://localhost:11434/v1",
        model_name="deepseek-r1",
        request_timeout_seconds=5,
    )
    transport = _build_mock_chat_transport("", delay_timeout=True)
    llm = LlmClient(settings, client=httpx.AsyncClient(transport=transport))

    with pytest.raises(LlmResponseError, match="timed out"):
        await llm.complete("Will timeout")


@pytest.mark.asyncio
async def test_invalid_json_response_handling() -> None:
    """Verify malformed JSON or schema violation fails closed with LlmResponseError."""
    settings = LlmSettings(
        provider="local",
        base_url="http://localhost:11434/v1",
        model_name="qwen2.5:7b",
    )
    # Non-JSON content
    transport_bad_json = _build_mock_chat_transport("This is not JSON at all")
    llm_bad = LlmClient(settings, client=httpx.AsyncClient(transport=transport_bad_json))

    class DemoModel(BaseModel):
        target: str

    with pytest.raises(LlmResponseError, match="not valid JSON"):
        await llm_bad.generate_structured(
            system_prompt="sys", user_prompt="usr", response_model=DemoModel
        )


# =============================================================================
# 2. Intelligence Engine Inference & Planning Tests
# =============================================================================

@pytest.mark.asyncio
async def test_intelligence_engine_plan_directive_decomposition() -> None:
    """Verify IE uses model output for bounded directive decomposition & worker recommendations."""
    plan_json = json.dumps({
        "objective_interpretation": "Launch new organic campaign across Instagram and Web",
        "intent": "multi_channel_launch",
        "plan": [
            {
                "step_id": "step-1",
                "description": "Develop landing page schema and layouts",
                "recommended_worker": "W_DEV",
                "dependencies": [],
                "expected_output": "CMS template schema",
            },
            {
                "step_id": "step-2",
                "description": "Draft high-converting ad and page copy",
                "recommended_worker": "W_CREAT",
                "dependencies": ["step-1"],
                "expected_output": "Approved marketing copy package",
            },
        ],
        "rationale_summary": "Development sets the technical foundation before creative copy placement.",
        "confidence": 0.92,
        "assumptions": ["CMS endpoints are staging-ready"],
        "context_requests": [],
    })

    settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="qwen2.5")
    llm = LlmClient(settings, client=httpx.AsyncClient(transport=_build_mock_chat_transport(plan_json)))

    # Dummy collaborators for IE initialization
    ie = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(PolicyEngine()),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(RagQueryDispatcher(None)),  # type: ignore[arg-type]
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=None,  # type: ignore[arg-type]
        workers={},
        llm_client=llm,
    )

    directive = Directive(
        directive_id="dir-e2e-01",
        tenant_id="tenant-alpha",
        objective="Launch Q3 promotional campaign",
        risk_ceiling=RiskLevel.LOW,
        budget_cap=5000.0,
        scope=TenantScope(tenant_id="tenant-alpha", brand_ids=["brand-01"]),
    )

    result = await ie.plan_directive(
        directive,
        available_workers=[WorkerRole.DEVELOPMENT, WorkerRole.CREATIVE_CONTENT],
    )

    assert isinstance(result, IntelligenceResult)
    assert len(result.plan) == 2
    assert result.plan[0].step_id == "step-1"
    assert result.plan[0].recommended_worker == WorkerRole.DEVELOPMENT
    assert result.plan[1].dependencies == ["step-1"]
    assert result.confidence == 0.92
    assert "Development sets the technical foundation" in result.rationale_summary


@pytest.mark.asyncio
async def test_intelligence_engine_rejects_unlisted_worker() -> None:
    """Verify IE fails closed if model recommends a worker not supplied in available_workers."""
    invalid_worker_json = json.dumps({
        "objective_interpretation": "Test objective",
        "intent": "test",
        "plan": [
            {
                "step_id": "step-1",
                "description": "Run untrusted scrape",
                "recommended_worker": "W_COMP",  # Not in available_workers
                "dependencies": [],
                "expected_output": "intel",
            }
        ],
        "rationale_summary": "Recommends competitor intel",
        "confidence": 0.8,
        "assumptions": [],
        "context_requests": [],
    })

    settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="qwen2.5")
    llm = LlmClient(settings, client=httpx.AsyncClient(transport=_build_mock_chat_transport(invalid_worker_json)))

    ie = IntelligenceEngine(
        policy_evaluator=PolicyEvaluator(PolicyEngine()),
        dag_scheduler=DagScheduler(),
        task_state_machine=TaskStateMachine(),
        context_assembler=ContextAssembler(RagQueryDispatcher(None)),  # type: ignore[arg-type]
        evidence_synthesizer=EvidenceSynthesizer(),
        hitl_preview_generator=HitlPreviewGenerator(),
        hitl_coordinator=HitlCoordinator(),
        mcp_host=None,  # type: ignore[arg-type]
        provenance_recorder=None,  # type: ignore[arg-type]
        workers={},
        llm_client=llm,
    )

    with pytest.raises(InvalidIntelligenceOutputError, match="not supplied in available_workers"):
        await ie.plan(
            objective="Analyze",
            available_workers=[WorkerRole.STRATEGY],  # Only STRATEGY allowed
        )


# =============================================================================
# 3. All Seven Worker Agents Bounded Domain Reasoning Tests
# =============================================================================

@pytest.mark.parametrize(
    ("agent_class", "role", "capability"),
    [
        (DevelopmentAgent, WorkerRole.DEVELOPMENT, SandboxCapability.CODE),
        (StrategyAgent, WorkerRole.STRATEGY, SandboxCapability.ALLOC),
        (CreativeContentAgent, WorkerRole.CREATIVE_CONTENT, SandboxCapability.COPY),
        (ProductEvidenceAgent, WorkerRole.PRODUCT_EVIDENCE, SandboxCapability.VAL),
        (CompetitorIntelAgent, WorkerRole.COMPETITOR_INTEL, SandboxCapability.SCRAPE),
        (CustomerVoiceAgent, WorkerRole.CUSTOMER_VOICE, SandboxCapability.PARSE),
        (LearningPerformanceAgent, WorkerRole.LEARNING_PERFORMANCE, SandboxCapability.ATTR),
    ],
)
@pytest.mark.asyncio
async def test_all_seven_workers_bounded_llm_inference(
    agent_class: type[BoundedWorkerAgent],
    role: WorkerRole,
    capability: SandboxCapability,
) -> None:
    """Verify all 7 worker agents perform LLM domain reasoning and record model provenance."""
    worker_reasoning_json = json.dumps({
        "domain_interpretation": f"Bounded interpretation for {role.value}",
        "requires_specialist_execution": True,
        "selected_tools": [capability.value],
        "suggested_parameters": {"operation": "default"},
        "preliminary_findings": [f"Finding from {role.value} cognitive step"],
        "identified_risks": [],
        "rationale_summary": f"Standard domain reasoning for {role.value}",
        "estimated_confidence": 0.85,
    })

    settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="local-qwen")
    llm = LlmClient(
        settings,
        client=httpx.AsyncClient(
            transport=_build_mock_chat_transport(
                worker_reasoning_json,
                model="local-qwen-7b",
                prompt_tokens=150,
                completion_tokens=60,
            )
        ),
    )

    # Sandbox client mock
    class DummySandboxClient(SandboxClient):
        def __init__(self) -> None:
            pass

        async def invoke(self, mandate: Any) -> Any:
            class DummyResult:
                success = True
                error = None
                sanitized_output = {"result_key": "sanitized_value", "operation": "default"}
                execution_id = "exec-test-123"
                status = TaskStatus.COMPLETED
                generated_artifacts: list[str] = []
                provenance = {"sandbox": "dummy"}
            return DummyResult()

    if getattr(agent_class, "capability", None) is None:
        agent = agent_class(llm_client=llm)
        grant = _make_sample_grant(role, capability)
        context = {
            "claims_dossier": {"tenant_id": "tenant-alpha", "claims": [{"claim_id": "c1", "text": "Valid", "validation_status": "SUPPORTED"}]},
            "strategy_plan": {"tenant_id": "tenant-alpha", "channels": ["meta"]},
            "items": [{"item_id": "item-1", "tenant_id": "tenant-alpha", "text": "Customer feedback text"}],
        }
        envelope = await agent.run(grant, context)
        assert envelope.worker_role == role
        assert envelope.provenance["agent"] == role.value
        assert envelope.provenance["capability"] == "NONE"
        return

    agent = agent_class(DummySandboxClient(), llm_client=llm)
    grant = _make_sample_grant(role, capability)
    context: dict[str, Any] = {"staged_cms_models": [{"model_id": "m1"}], "tenant_id": "tenant-alpha"}

    envelope = await agent.run(grant, context)

    assert envelope.worker_role == role
    assert any(f"Finding from {role.value} cognitive step" in line for line in envelope.findings)
    assert envelope.provenance["llm_reasoning_used"] == "true"
    assert envelope.provenance["llm_model"] == "local-qwen-7b"
    assert envelope.provenance["is_local_model"] == "true"
    assert envelope.provenance["total_tokens"] == "210"
    assert envelope.provenance["governed_tools_authorized"] == capability.value


# =============================================================================
# 4. Governed Tool Calling & Boundary Enforcement Tests
# =============================================================================

@pytest.mark.asyncio
async def test_worker_denies_unauthorized_tool_request() -> None:
    """Verify governed tool calling fails closed if model requests an unauthorized tool."""
    malicious_tool_json = json.dumps({
        "domain_interpretation": "Attempting unauthorized tool execution",
        "requires_specialist_execution": True,
        "selected_tools": ["mcp_data:write_record", "arbitrary_os_exec"],  # Not authorized in grant
        "suggested_parameters": {},
        "preliminary_findings": [],
        "identified_risks": [],
        "rationale_summary": "Tries to bypass PAB",
        "estimated_confidence": 0.5,
    })

    settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="local-qwen")
    llm = LlmClient(settings, client=httpx.AsyncClient(transport=_build_mock_chat_transport(malicious_tool_json)))

    agent = DevelopmentAgent(SandboxClient(None), llm_client=llm)  # type: ignore[arg-type]
    grant = _make_sample_grant(
        WorkerRole.DEVELOPMENT,
        SandboxCapability.CODE,
        tools=["code_sandbox"],  # Only code_sandbox permitted
    )

    with pytest.raises(PolicyViolationError, match="attempted unauthorized tool execution"):
        await agent.run(grant, {})


@pytest.mark.asyncio
async def test_worker_denies_cross_tenant_access() -> None:
    """Verify worker fails closed if model reasoning suggests cross-tenant parameter access."""
    cross_tenant_json = json.dumps({
        "domain_interpretation": "Attempting cross tenant query",
        "requires_specialist_execution": True,
        "selected_tools": [SandboxCapability.CODE.value],
        "suggested_parameters": {"tenant_id": "tenant-bravo-victim"},  # Target tenant mismatch
        "preliminary_findings": [],
        "identified_risks": [],
        "rationale_summary": "Access cross tenant data",
        "estimated_confidence": 0.5,
    })

    settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="local-qwen")
    llm = LlmClient(settings, client=httpx.AsyncClient(transport=_build_mock_chat_transport(cross_tenant_json)))

    agent = DevelopmentAgent(SandboxClient(None), llm_client=llm)  # type: ignore[arg-type]
    grant = _make_sample_grant(
        WorkerRole.DEVELOPMENT,
        SandboxCapability.CODE,
        tenant_id="tenant-alpha-bound",
        tools=[SandboxCapability.CODE.value],
    )

    with pytest.raises(PolicyViolationError, match="attempted cross-tenant access"):
        await agent.run(grant, {})


@pytest.mark.asyncio
async def test_worker_denies_excessive_token_budget() -> None:
    """Verify worker fails closed if model token usage exceeds grant token budget."""
    reasoning_json = json.dumps({
        "domain_interpretation": "Reasoning with excessive token usage",
        "requires_specialist_execution": True,
        "selected_tools": [SandboxCapability.CODE.value],
        "suggested_parameters": {},
        "preliminary_findings": [],
        "identified_risks": [],
        "rationale_summary": "Exceeds budget",
        "estimated_confidence": 0.5,
    })

    # Return total_tokens = 5000 from provider
    settings = LlmSettings(provider="local", base_url="http://localhost:11434/v1", model_name="local-qwen")
    llm = LlmClient(
        settings,
        client=httpx.AsyncClient(
            transport=_build_mock_chat_transport(
                reasoning_json, prompt_tokens=3000, completion_tokens=2000
            )
        ),
    )

    agent = DevelopmentAgent(SandboxClient(None), llm_client=llm)  # type: ignore[arg-type]
    # Grant only permits budget of 1000 tokens
    grant = _make_sample_grant(
        WorkerRole.DEVELOPMENT,
        SandboxCapability.CODE,
        token_budget=1000,
        tools=[SandboxCapability.CODE.value],
    )

    with pytest.raises(PolicyViolationError, match="exceeded token budget"):
        await agent.run(grant, {})
