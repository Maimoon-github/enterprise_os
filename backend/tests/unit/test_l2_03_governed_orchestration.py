"""Unit and integration tests for L2-03: Governed IE Orchestration, HITL, Outbound Dispatch, and Provenance Integration."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.core.exceptions import (
    ApprovalRequiredError,
    AuthorizationError,
    PolicyViolationError,
    SignatureVerificationError,
)
from app.integrations.ads.base import AdsAdapter
from app.mcp.data_gateway import DataGateway
from app.mcp.outbound_gateway import OutboundGateway, canonical_dispatch_bytes
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewKind,
    HumanDecisionType,
    ReviewStatus,
    ReviewerRole,
    compute_preview_hash,
)
from app.schemas.dispatch import AudienceToken, DispatchDirective
from app.schemas.governance import RiskLevel, TenantScope, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import HitlCoordinator, canonical_decision_bytes
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository, FakeVectorRepository


class InMemoryTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task '{task_id}' not found.")
        return self.states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state


def _make_keypair() -> tuple[Ed25519PrivateKey, str]:
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_key, public_pem


class ReconcilableAdsAdapter(AdsAdapter):
    channel = "meta"

    def __init__(self, timeout_on_apply: bool = False) -> None:
        self.timeout_on_apply = timeout_on_apply
        self.applied_calls: list[dict] = []
        self.reconcile_calls: list[str] = []
        self.reconcile_result: dict | None = None

    async def apply_action(self, payload: dict) -> dict:
        self.applied_calls.append(payload)
        if self.timeout_on_apply:
            raise TimeoutError("Simulated upstream network timeout during ad execution")
        return {"status_code": "200", "channel": self.channel, "ad_id": "meta-ad-123"}

    async def reconcile(self, idempotency_key: str) -> dict | None:
        self.reconcile_calls.append(idempotency_key)
        return self.reconcile_result


def _create_approved_preview(
    preview_id: str,
    task_id: str,
    tenant_id: str,
    priv_key: Ed25519PrivateKey,
    pub_pem: str,
    hitl: HitlCoordinator,
    policy_version: str = "1.0.0",
    expires_at: datetime | None = None,
    spend_amount: float = 1000.0,
) -> tuple[ActionPreview, Any]:
    preview = ActionPreview(
        preview_id=preview_id,
        task_id=task_id,
        tenant_id=tenant_id,
        kind=ActionPreviewKind.SPEND,
        summary="Spend action",
        risk_level=RiskLevel.MEDIUM,
        spend_amount=spend_amount,
        currency="USD",
    )
    hitl.submit_for_approval(preview)

    now_dt = datetime.now(UTC)
    content_hash = compute_preview_hash(preview)
    canon_bytes = canonical_decision_bytes(
        preview_id=preview_id,
        decision="APPROVE",
        approver="[email protected]",
        tenant_id=tenant_id,
        preview_content_hash=content_hash,
        decided_at=now_dt.isoformat(),
    )
    sig = sign_payload(canon_bytes, priv_key)

    decision = hitl.decide(
        preview_id,
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role=ReviewerRole.FINANCE,
        tenant_id=tenant_id,
        signature=sig,
        public_key_pem=pub_pem,
        preview_content_hash=content_hash,
        decided_at=now_dt,
        policy_version=policy_version,
        expires_at=expires_at,
    )
    return preview, decision


def _make_dispatch(
    preview: ActionPreview,
    decision: Any,
    priv_key: Ed25519PrivateKey,
    *,
    payload: dict | None = None,
    channel: str = "meta",
    policy_version: str | None = "1.0.0",
    preview_content_hash: str | None = None,
    expires_at: datetime | None = None,
) -> DispatchDirective:
    disp = DispatchDirective(
        dispatch_id=f"disp-{preview.preview_id}",
        task_id=preview.task_id,
        action_preview_id=preview.preview_id,
        signature="",
        approved_by=decision.approver,
        approved_at=decision.decided_at,
        channel=channel,
        tenant_id=preview.tenant_id,
        clearance_id=decision.clearance.clearance_id if decision.clearance else None,
        preview_content_hash=preview_content_hash or (decision.clearance.preview_content_hash if decision.clearance else None),
        policy_version=policy_version,
        expires_at=expires_at,
        payload=payload or {"campaign_id": "meta-1", "spend_amount": 1000.0},
    )
    sig = sign_payload(canonical_dispatch_bytes(disp), priv_key)
    return disp.model_copy(update={"signature": sig})


# ---------------------------------------------------------------------------
# 1. Model A Worker Isolation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_model_a_worker_data_gateway_query_blocked() -> None:
    data_gw = DataGateway(vector_repository=FakeVectorRepository())
    worker_identity = CallerIdentity(
        subject="W_CREAT_01",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
        await data_gw.query(worker_identity, tenant_id="tenant-alpha", query="SELECT 1")


@pytest.mark.asyncio
async def test_model_a_worker_data_gateway_ingest_blocked() -> None:
    data_gw = DataGateway(vector_repository=FakeVectorRepository())
    worker_identity = CallerIdentity(
        subject="W_DEV_01",
        tenant_scope=TenantScope(tenant_id="tenant-alpha"),
        risk_ceiling=RiskLevel.MEDIUM,
    )

    with pytest.raises(PolicyViolationError, match="Direct worker enterprise-store access forbidden"):
        await data_gw.ingest(worker_identity, tenant_id="tenant-alpha", doc_id="doc-1", text="content", source="test")


# ---------------------------------------------------------------------------
# 2. Cross-Tenant Rejection in DataGateway
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cross_tenant_access_rejected_in_data_gateway() -> None:
    data_gw = DataGateway(vector_repository=FakeVectorRepository())
    caller = CallerIdentity(
        subject="intelligence_engine",
        tenant_scope=TenantScope(tenant_id="tenant-beta"),
        risk_ceiling=RiskLevel.HIGH,
    )

    with pytest.raises(AuthorizationError):
        await data_gw.query(caller, tenant_id="tenant-alpha", query="SELECT 1")


# ---------------------------------------------------------------------------
# 3. Cryptographic Binding: Altered Payload, Policy Mismatch, Stale/Expired
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_altered_payload_hash_rejected_at_dispatch() -> None:
    priv_key, pub_pem = _make_keypair()
    validator = CryptographicValidator(pub_pem)
    hitl = HitlCoordinator(validator)

    preview, decision = _create_approved_preview(
        "prev-mod-1", "task-mod-1", "tenant-alpha", priv_key, pub_pem, hitl
    )

    dispatch = _make_dispatch(
        preview,
        decision,
        priv_key,
        payload={"spend_amount": 99999.0},
        preview_content_hash="tampered-hash-value",
    )

    adapter = ReconcilableAdsAdapter()
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)
    gateway = OutboundGateway(hitl, validator, ads_adapters={"meta": adapter}, provenance_recorder=recorder)

    with pytest.raises(PolicyViolationError, match="Preview content hash mismatch"):
        await gateway.validate_readiness(dispatch)


@pytest.mark.asyncio
async def test_policy_version_mismatch_rejected_at_dispatch() -> None:
    priv_key, pub_pem = _make_keypair()
    validator = CryptographicValidator(pub_pem)
    hitl = HitlCoordinator(validator)

    preview, decision = _create_approved_preview(
        "prev-pol-1", "task-pol-1", "tenant-alpha", priv_key, pub_pem, hitl, policy_version="1.0.0"
    )

    dispatch = _make_dispatch(
        preview,
        decision,
        priv_key,
        policy_version="2.0.0",  # Mismatched policy version!
    )

    adapter = ReconcilableAdsAdapter()
    gateway = OutboundGateway(hitl, validator, ads_adapters={"meta": adapter})

    with pytest.raises(PolicyViolationError, match="Policy version mismatch"):
        await gateway.validate_readiness(dispatch)


@pytest.mark.asyncio
async def test_expired_approval_rejected_at_dispatch() -> None:
    priv_key, pub_pem = _make_keypair()
    validator = CryptographicValidator(pub_pem)
    hitl = HitlCoordinator(validator)

    past_time = datetime.now(UTC) - timedelta(hours=2)
    preview, decision = _create_approved_preview(
        "prev-exp-1", "task-exp-1", "tenant-alpha", priv_key, pub_pem, hitl, expires_at=past_time
    )

    dispatch = _make_dispatch(
        preview,
        decision,
        priv_key,
        expires_at=past_time,
    )

    adapter = ReconcilableAdsAdapter()
    gateway = OutboundGateway(hitl, validator, ads_adapters={"meta": adapter})

    with pytest.raises(PolicyViolationError, match="expired"):
        await gateway.validate_readiness(dispatch)


# ---------------------------------------------------------------------------
# 4. CTS Task State Screening (Rejecting HELD/REJECTED/FAILED Tasks)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dispatch_rejected_when_task_state_is_held() -> None:
    priv_key, pub_pem = _make_keypair()
    validator = CryptographicValidator(pub_pem)
    hitl = HitlCoordinator(validator)

    preview, decision = _create_approved_preview(
        "prev-held-1", "task-held-1", "tenant-alpha", priv_key, pub_pem, hitl
    )

    dispatch = _make_dispatch(preview, decision, priv_key)

    state_repo = InMemoryTaskStateRepository()
    state_service = TaskStateService(state_repo)
    task_state = CanonicalTaskState(
        task_id="task-held-1",
        directive_id="dir-held-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
    )
    await state_service.save_state("tenant-alpha", task_state)
    await state_service.hold_task("tenant-alpha", "task-held-1", "Regulatory hold")

    adapter = ReconcilableAdsAdapter()
    gateway = OutboundGateway(hitl, validator, ads_adapters={"meta": adapter}, task_state_service=state_service)

    with pytest.raises(PolicyViolationError, match="non-executable state"):
        await gateway.execute(dispatch)


# ---------------------------------------------------------------------------
# 5. Outbound Timeout Reconciliation Without Blind Duplicate Actuation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_outbound_timeout_reconciliation_flow() -> None:
    priv_key, pub_pem = _make_keypair()
    validator = CryptographicValidator(pub_pem)
    hitl = HitlCoordinator(validator)

    preview, decision = _create_approved_preview(
        "prev-rec-1", "task-rec-1", "tenant-alpha", priv_key, pub_pem, hitl
    )

    dispatch = _make_dispatch(preview, decision, priv_key)

    adapter = ReconcilableAdsAdapter(timeout_on_apply=True)
    # Configure reconcile to confirm upstream actually succeeded
    adapter.reconcile_result = {"status_code": "200", "reconciled": True, "ad_id": "meta-rec-999"}

    state_repo = InMemoryTaskStateRepository()
    state_service = TaskStateService(state_repo)
    task_state = CanonicalTaskState(
        task_id="task-rec-1",
        directive_id="dir-rec-1",
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.APPROVED,
    )
    await state_service.save_state("tenant-alpha", task_state)

    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)

    gateway = OutboundGateway(
        hitl,
        validator,
        ads_adapters={"meta": adapter},
        task_state_service=state_service,
        provenance_recorder=recorder,
    )

    result = await gateway.execute(dispatch)

    assert result["reconciled"] is True
    assert len(adapter.applied_calls) == 1  # Only 1 attempt, NO blind retry
    assert len(adapter.reconcile_calls) == 1  # Reconciled via idempotency identity

    # Verify task state transitioned to COMPLETED
    updated_state = await state_service.get_state("task-rec-1")
    assert updated_state.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# 6. Provenance W3C Lineage Completeness
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_provenance_w3c_prov_structure() -> None:
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)

    rec = await recorder.record_governed_event(
        tenant_id="tenant-alpha",
        activity_type="outbound_dispatch",
        agent_id="system",
        agent_role="orchestrator",
        entity_id="disp-prov-1",
        entity_type="dispatch_directive",
        used_entity_ids=["prev-1", "clr-1"],
        generated_entity_ids=["receipt-1"],
        metadata={"channel": "meta", "policy_version": "1.0.0"},
    )

    assert rec.w3c_prov is not None
    prov_dict = rec.w3c_prov if isinstance(rec.w3c_prov, dict) else rec.w3c_prov.model_dump()
    assert "entities" in prov_dict
    assert "activities" in prov_dict
    assert "agents" in prov_dict
    assert "relations" in prov_dict

    # Check relation keys
    rel_types = {rel["relation_type"] for rel in prov_dict["relations"]}
    assert "prov:wasAssociatedWith" in rel_types
    assert "prov:used" in rel_types
    assert "prov:wasGeneratedBy" in rel_types
