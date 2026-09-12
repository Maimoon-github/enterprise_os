"""Comprehensive negative security boundary tests.

Verifies strict enforcement of all architectural security perimeters:
1. Worker isolation: No direct persistence or RAG imports/access (AST & interface isolation).
2. Model-A brokering: Unbrokered / cross-tenant data requests are rejected fail-closed.
3. Cross-tenant isolation across RAG, CMS, institutional memory, and artifacts.
4. Sandbox capability allowlisting: Unauthorized capabilities are rejected.
5. HITL governance: Outbound actuation without approved HITL decision is denied.
6. Cryptographic verification: Tampered payloads or forged signatures are rejected.
7. Risk ceiling attenuation: Delegations exceeding directive risk ceiling or scope are denied.
8. Task state transitions: Illegal lifecycle transitions are denied fail-closed.
9. Freshness policy: Stale or malformed retrieved documents are rejected.
"""

from __future__ import annotations

import ast
import importlib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.core.exceptions import (
    ApprovalRequiredError,
    AuthorizationError,
    InvalidTransitionError,
    PolicyViolationError,
    RetrievalGovernanceError,
    SignatureVerificationError,
)
from app.integrations.ads.base import AdsAdapter
from app.integrations.sandbox.client import SandboxClient
from app.mcp.data_gateway import DataGateway
from app.mcp.host import McpHost
from app.mcp.outbound_gateway import OutboundGateway, canonical_dispatch_bytes
from app.services.hitl import HitlCoordinator
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import ActionPreview, ActionPreviewKind
from app.schemas.agent_contracts import TaskGrant
from app.schemas.dispatch import DispatchDirective
from app.schemas.governance import Directive, RiskLevel, TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.security.scope_evaluator import ScopeEvaluator
from app.services.rag.freshness import FreshnessPolicy
from tests.conftest import (
    FakeProvenanceRepository,
    FakeSandboxClient,
    FakeVectorRepository,
)


# ---------------------------------------------------------------------------
# 1. Static AST and Structural Boundary Tests
# ---------------------------------------------------------------------------

_ALL_WORKER_MODULES = [
    "app.agents.development",
    "app.agents.strategy",
    "app.agents.creative_content",
    "app.agents.product_evidence",
    "app.agents.competitor_intel",
    "app.agents.customer_voice",
    "app.agents.learning_performance",
]

_RESTRICTED_IMPORT_PREFIXES = (
    "app.persistence",
    "app.services.rag",
    "app.mcp",
    "app.security",
    "app.integrations.cms",
    "app.integrations.ads",
    "app.integrations.social",
    "sqlalchemy",
    "psycopg2",
    "asyncpg",
)


def _get_imports(module_name: str) -> list[str]:
    module = importlib.import_module(module_name)
    assert module.__file__ is not None
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


@pytest.mark.parametrize("mod", _ALL_WORKER_MODULES)
def test_worker_cannot_import_persistence_or_direct_adapters(mod: str) -> None:
    """Workers must never import persistence, direct adapters, or MCP host."""
    imports = _get_imports(mod)
    for imp in imports:
        for restricted in _RESTRICTED_IMPORT_PREFIXES:
            assert not imp.startswith(restricted), (
                f"Security Violation: {mod} imports '{imp}', breaching the worker boundary."
            )


# ---------------------------------------------------------------------------
# 2. Cross-Tenant Isolation Tests (DataGateway fail-closed)
# ---------------------------------------------------------------------------

class FakeCmsAdapter:
    async def get_content(self, tenant_id: str, content_id: str) -> dict[str, Any]:
        return {"tenant_id": tenant_id, "content_id": content_id, "body": "cms content"}


class FakeMemoryRepo:
    async def list_by_tenant(self, tenant_id: str, category: str | None = None):
        return [{"tenant_id": tenant_id, "insight": "memory"}]


class FakeArtifactRepo:
    async def get(self, artifact_id: str):
        return {"artifact_id": artifact_id, "content": "artifact data"}


@pytest.fixture
def governed_data_gateway() -> DataGateway:
    boundary = AuthorizationBoundary(ScopeEvaluator())
    vector_repo = FakeVectorRepository()
    vector_repo.seed(tenant_id="tenant-alpha", text="Alpha confidential doc")
    vector_repo.seed(tenant_id="tenant-beta", text="Beta confidential doc")
    return DataGateway(
        vector_repository=vector_repo,
        authorization_boundary=boundary,
        cms_client=FakeCmsAdapter(),  # type: ignore[arg-type]
        memory_repository=FakeMemoryRepo(),  # type: ignore[arg-type]
        artifact_repository=FakeArtifactRepo(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_cross_tenant_rag_query_denied(governed_data_gateway: DataGateway) -> None:
    """A caller with tenant-alpha scope attempting to read tenant-beta RAG data is denied."""
    alpha_caller = CallerIdentity(
        subject="worker-alpha",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.LOW,
    )
    with pytest.raises(AuthorizationError):
        await governed_data_gateway.query(
            alpha_caller,
            tenant_id="tenant-beta",
            query="confidential",
        )


@pytest.mark.asyncio
async def test_cross_tenant_cms_fetch_denied(governed_data_gateway: DataGateway) -> None:
    """A caller with tenant-alpha scope attempting to fetch tenant-beta CMS content is denied."""
    alpha_caller = CallerIdentity(
        subject="worker-alpha",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.LOW,
    )
    with pytest.raises(AuthorizationError):
        await governed_data_gateway.read_cms_staged(
            alpha_caller,
            tenant_id="tenant-beta",
            content_type="blog_post",
        )


@pytest.mark.asyncio
async def test_cross_tenant_memory_query_denied(governed_data_gateway: DataGateway) -> None:
    """A caller with tenant-alpha scope attempting to read tenant-beta memory is denied."""
    alpha_caller = CallerIdentity(
        subject="worker-alpha",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.LOW,
    )
    with pytest.raises(AuthorizationError):
        await governed_data_gateway.query_memory(
            alpha_caller,
            tenant_id="tenant-beta",
        )


@pytest.mark.asyncio
async def test_cross_tenant_artifact_read_denied(governed_data_gateway: DataGateway) -> None:
    """A caller with tenant-alpha scope attempting to read tenant-beta artifact is denied."""
    alpha_caller = CallerIdentity(
        subject="worker-alpha",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.LOW,
    )
    with pytest.raises(AuthorizationError):
        await governed_data_gateway.resolve_artifact(
            alpha_caller,
            tenant_id="tenant-beta",
            artifact_id="art-999",
        )


# ---------------------------------------------------------------------------
# 3. Sandbox Capability Allowlisting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sandbox_client_denies_unauthorized_capability() -> None:
    """SandboxClient must deny execution if capability is not in the allowlist."""
    from pydantic import ValidationError
    from app.core.exceptions import SandboxInvocationError

    # Level 1: Contract-level validation rejection
    with pytest.raises(ValidationError):
        SandboxInvocationMandate(
            task_id="task-exploit",
            capability="UNAUTHORIZED_ROOT_SHELL",  # type: ignore[arg-type]
            payload={"command": "rm -rf /"},
        )

    # Level 2: Runtime allowlist check inside SandboxClient
    client = SandboxClient()
    unauthorized_mandate = SandboxInvocationMandate.model_construct(
        task_id="task-exploit",
        capability="UNAUTHORIZED_ROOT_SHELL",
        payload={"command": "rm -rf /"},
    )
    with pytest.raises(SandboxInvocationError) as exc_info:
        await client.invoke(unauthorized_mandate)
    assert "Unauthorized or invalid sandbox capability" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Outbound Actuation Governance (HITL Approval Required)
# ---------------------------------------------------------------------------

class _FakeAds(AdsAdapter):
    channel = "meta"

    def __init__(self) -> None:
        super().__init__(access_token="test-token")

    async def apply_action(self, payload: dict[str, str]) -> dict[str, str]:
        return {"status": "ok"}


@pytest.mark.asyncio
async def test_outbound_actuation_fails_without_hitl_approval(ed25519_keypair) -> None:
    """OutboundGateway must reject execution if HITL preview has not been approved."""
    _, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    crypto_val = CryptographicValidator(public_pem)
    outbound = OutboundGateway(hitl, crypto_val, ads_adapters={"meta": _FakeAds()})

    preview = ActionPreview(
        preview_id="prev-unapproved",
        task_id="task-1",
        kind=ActionPreviewKind.SPEND,
        summary="Spend $500",
        spend_amount=500.0,
        risk_level=RiskLevel.HIGH,
    )
    hitl.submit_for_approval(preview)
    # Note: Not calling hitl.decide(...)

    dispatch = DispatchDirective(
        dispatch_id="disp-1",
        task_id="task-1",
        action_preview_id="prev-unapproved",
        signature="dummy",
        approved_by="none",
        approved_at=datetime.now(UTC),
        channel="meta",
        payload={"spend": "500"},
    )

    with pytest.raises(ApprovalRequiredError):
        await outbound.execute(dispatch)


# ---------------------------------------------------------------------------
# 5. Cryptographic Signature Verification & Tamper Resistance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outbound_actuation_fails_with_tampered_payload(ed25519_keypair) -> None:
    """Payload modified after signing must be rejected immediately."""
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    crypto_val = CryptographicValidator(public_pem)
    outbound = OutboundGateway(hitl, crypto_val, ads_adapters={"meta": _FakeAds()})

    preview = ActionPreview(
        preview_id="prev-valid",
        task_id="task-1",
        kind=ActionPreviewKind.SPEND,
        summary="Spend $100",
        spend_amount=100.0,
        risk_level=RiskLevel.MEDIUM,
    )
    hitl.submit_for_approval(preview)
    hitl.decide("prev-valid", approved=True, approver="[email protected]")

    original_dispatch = DispatchDirective(
        dispatch_id="disp-orig",
        task_id="task-1",
        action_preview_id="prev-valid",
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="meta",
        payload={"spend": "100"},
    )
    # Sign original dispatch
    valid_sig = sign_payload(canonical_dispatch_bytes(original_dispatch), private_key)

    # Attacker tampers payload to spend $10,000 using valid signature of original dispatch
    tampered_dispatch = original_dispatch.model_copy(
        update={"signature": valid_sig, "payload": {"spend": "10000"}}
    )

    with pytest.raises(SignatureVerificationError):
        await outbound.execute(tampered_dispatch)


# ---------------------------------------------------------------------------
# 6. Monotonic Attenuation & Risk Ceiling Denial
# ---------------------------------------------------------------------------

def test_policy_evaluator_rejects_risk_exceeding_directive_ceiling() -> None:
    """A task requesting a risk level higher than the parent directive is rejected."""
    evaluator = PolicyEvaluator()
    directive = Directive(
        directive_id="dir-low-risk",
        tenant_id="acme",
        objective="Low risk copy tweaks",
        budget_cap=500.0,
        risk_ceiling=RiskLevel.LOW,
        scope=TenantScope(tenant_id="acme"),
    )

    decision = evaluator.evaluate_delegation(
        directive=directive,
        requested_scope=TenantScope(tenant_id="acme"),
        requested_risk=RiskLevel.HIGH,
    )
    assert decision.allowed is False
    assert "exceeds directive ceiling" in decision.reason


def test_policy_evaluator_rejects_scope_exceeding_directive_scope() -> None:
    """A task requesting channels or brands outside directive scope is rejected."""
    evaluator = PolicyEvaluator()
    directive = Directive(
        directive_id="dir-scoped",
        tenant_id="acme",
        objective="Meta only",
        budget_cap=500.0,
        risk_ceiling=RiskLevel.MEDIUM,
        scope=TenantScope(tenant_id="acme", allowed_channels=["meta"]),
    )

    decision = evaluator.evaluate_delegation(
        directive=directive,
        requested_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "tiktok"]),
        requested_risk=RiskLevel.LOW,
    )
    assert decision.allowed is False
    assert "Requested scope exceeds" in decision.reason


# ---------------------------------------------------------------------------
# 7. Task State Machine Transitions (Fail-Closed)
# ---------------------------------------------------------------------------

def test_task_state_machine_rejects_illegal_skip_transitions() -> None:
    """Skipping lifecycle stages directly to COMPLETED is rejected fail-closed."""
    sm = TaskStateMachine()
    task = CanonicalTaskState(
        task_id="task-sm-test",
        directive_id="dir-1",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        status=TaskStatus.PENDING,
    )

    # Illegal transition: PENDING -> COMPLETED directly without GRANTED / IN_PROGRESS
    with pytest.raises(InvalidTransitionError):
        sm.transition(task, TaskStatus.COMPLETED, checkpoint_id="chk-1")

    # Illegal transition: COMPLETED -> IN_PROGRESS
    completed_task = task.model_copy(update={"status": TaskStatus.COMPLETED})
    with pytest.raises(InvalidTransitionError):
        sm.transition(completed_task, TaskStatus.IN_PROGRESS, checkpoint_id="chk-2")


# ---------------------------------------------------------------------------
# 8. Freshness Policy Enforcement
# ---------------------------------------------------------------------------

def test_freshness_policy_rejects_stale_and_malformed_documents() -> None:
    """Documents older than TTL or with unparseable timestamps are rejected."""
    policy = FreshnessPolicy(max_age=timedelta(days=30))

    # Stale document (60 days old)
    stale_doc = {
        "doc_id": "doc-old",
        "retrieved_at": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
    }
    assert policy.is_fresh(stale_doc) is False

    # Malformed timestamp
    corrupt_doc = {
        "doc_id": "doc-corrupt",
        "retrieved_at": "invalid-timestamp-format",
    }
    assert policy.is_fresh(corrupt_doc) is False

    # Fresh document (2 days old)
    fresh_doc = {
        "doc_id": "doc-new",
        "retrieved_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
    }
    assert policy.is_fresh(fresh_doc) is True
