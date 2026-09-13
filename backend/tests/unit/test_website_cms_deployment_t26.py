"""Unit tests for T26: Deploy Approved Website & CMS Changes (Headless CMS/Web Store + Outbound MCP)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.exceptions import (
    ApprovalRequiredError,
    PolicyViolationError,
    SignatureVerificationError,
)
from app.integrations.cms.client import CmsClient
from app.mcp.outbound_gateway import OutboundGateway, canonical_dispatch_bytes
from app.orchestration.intelligence_engine import IntelligenceEngine
from app.orchestration.task_state_machine import TaskStateMachine
from app.schemas.action_preview import (
    ActionPreview,
    ActionPreviewKind,
    CodeDiffPreviewDetails,
    HumanDecisionType,
    ReviewStatus,
    ReviewerRole,
    SignedApprovalClearance,
)
from app.schemas.dispatch import AudienceToken, DispatchDirective
from app.schemas.governance import RiskLevel, WorkerRole
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.cryptographic_validator import CryptographicValidator, sign_payload
from app.services.hitl import HitlCoordinator, compute_preview_hash
from app.services.provenance import ProvenanceRecorder
from app.services.task_state import TaskStateService
from tests.conftest import FakeProvenanceRepository


class InMemoryTaskStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, CanonicalTaskState] = {}

    async def require(self, task_id: str) -> CanonicalTaskState:
        if task_id not in self.states:
            raise KeyError(f"Task '{task_id}' not found.")
        return self.states[task_id]

    async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
        self.states[state.task_id] = state


def _make_clearance(
    preview_id: str,
    tenant_id: str,
    content_hash: str,
    public_pem: str,
    approved_scope: dict[str, Any] | None = None,
) -> SignedApprovalClearance:
    return SignedApprovalClearance(
        clearance_id=f"clearance-{preview_id}",
        preview_id=preview_id,
        task_id="task-dev-1",
        tenant_id=tenant_id,
        decision=HumanDecisionType.APPROVE,
        approver="[email protected]",
        approver_role="engineering",
        preview_content_hash=content_hash,
        signature="valid-human-signature",
        public_key_pem=public_pem,
        approved_scope=approved_scope or {},
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )



def _make_preview(
    preview_id: str = "prev-diff-1",
    tenant_id: str = "tenant-alpha",
    diff_content: str = "--- a/page.html\n+++ b/page.html\n@@ -1 +1 @@\n-old\n+new",
) -> tuple[ActionPreview, str]:
    preview = ActionPreview(
        preview_id=preview_id,
        task_id="task-dev-1",
        tenant_id=tenant_id,
        kind=ActionPreviewKind.CODE_DIFF,
        summary="Deploy responsive UI updates and CMS models",
        proposed_action="Deploy approved page models and code diffs to headless CMS and live website",
        diff=diff_content,
        risk_level=RiskLevel.MEDIUM,
        requires_approval=True,
        review_status=ReviewStatus.APPROVED,
        code_details=CodeDiffPreviewDetails(
            file_path="pages/landing.html",
            action="modify",
            diff_unified=diff_content,
            target_components=["LandingHero"],
        ),
    )
    content_hash = compute_preview_hash(preview)
    return preview, content_hash



@pytest.mark.asyncio
async def test_t26_successful_website_cms_deployment(ed25519_keypair) -> None:
    """T26 successfully deploys approved schemas, catalog objects, layout models, assets, and code diffs to CMS."""
    private_key, public_pem = ed25519_keypair
    tenant_id = "tenant-alpha"

    # 1. Setup HITL Clearance
    hitl = HitlCoordinator()
    preview, content_hash = _make_preview()
    hitl.submit_for_approval(preview)
    clearance = _make_clearance(
        preview.preview_id,
        tenant_id,
        content_hash,
        public_pem,
        approved_scope={
            "permitted_content_types": ["pages", "products", "schemas", "assets", "code_diffs"],
            "permitted_entries": ["page-landing", "prod-101", "schema-catalog"],
            "permitted_files": ["pages/landing.html"],
        },
    )
    decision = hitl.decide(
        preview.preview_id,
        approved=True,
        approver="[email protected]",
        approver_role=ReviewerRole.ENGINEERING,
        tenant_id=tenant_id,
    )
    decision.clearance = clearance

    # 2. Setup Audience Token
    token = AudienceToken(
        token_id="tok-cms-1",
        target_audience="cms_adapter",
        tenant_id=tenant_id,
        scope="actuation",
        permitted_actions=["publish", "deploy", "update"],
        expires_at=datetime.now(UTC) + timedelta(hours=2),
    )

    # 3. Setup CTS and Task
    repo = InMemoryTaskStateRepository()
    task_service = TaskStateService(repository=repo, state_machine=TaskStateMachine())
    initial_state = CanonicalTaskState(
        task_id="task-dev-1",
        directive_id="dir-1",
        worker_role=WorkerRole.DEVELOPMENT,
        status=TaskStatus.APPROVED,
    )
    await repo.save_state(tenant_id, initial_state)

    # 4. Setup CMS Client and Provenance
    cms_client = CmsClient()
    prov_repo = FakeProvenanceRepository()
    prov_recorder = ProvenanceRecorder(repository=prov_repo)

    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=cms_client,
        provenance_recorder=prov_recorder,
        task_state_service=task_service,
    )

    # 5. Build Deployment Payload
    payload = {
        "version": "v2.0",
        "pages": [{"page_id": "page-landing", "title": "Landing Hero", "slug": "home"}],
        "products": [{"product_id": "prod-101", "sku": "SKU-HERO", "price": 49.99}],
        "code_diffs": [{"file_path": "pages/landing.html", "diff_unified": preview.diff}],
    }

    directive = DispatchDirective(
        dispatch_id="dispatch-cms-1",
        task_id="task-dev-1",
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        tenant_id=tenant_id,
        audience="cms_adapter",
        audience_token=token,
        action_type="publish",
        preview_content_hash=content_hash,
        clearance_id=clearance.clearance_id,
        idempotency_key="idemp-cms-1",
        payload=payload,
    )
    sig = sign_payload(canonical_dispatch_bytes(directive), private_key)
    directive = directive.model_copy(update={"signature": sig})

    # 6. Execute Deployment via MCP_ACT
    result = await gateway.execute(directive)

    # 7. Verify Deployment Result
    assert result["status"] == "published"
    assert result["status_code"] == "200"
    assert result["channel"] == "cms"
    assert result["version"] == "v2.0"
    assert len(result["applied_items"]) == 3

    # 8. Verify CMS live store state
    live_pages = await cms_client.read_published("pages", tenant_id=tenant_id)
    assert len(live_pages) == 1
    assert live_pages[0]["id"] == "page-landing"
    assert live_pages[0]["status"] == "published"

    live_products = await cms_client.read_published("products", tenant_id=tenant_id)
    assert len(live_products) == 1
    assert live_products[0]["id"] == "prod-101"

    # 9. Verify CTS Task Transition to COMPLETED
    updated_state = await task_service.get_state("task-dev-1")
    assert updated_state.status == TaskStatus.COMPLETED
    assert "deployment" in updated_state.cts_state
    assert updated_state.cts_state["deployment"]["status"] == "published"

    # 10. Verify Provenance Recorded
    prov_records = await prov_repo.chain(tenant_id=tenant_id)
    activities = [r.activity for r in prov_records]
    assert "mcp_act_readiness_validation" in activities
    assert "outbound_cms_deployment_executed" in activities


@pytest.mark.asyncio
async def test_t26_fails_closed_without_t25_approval(ed25519_keypair) -> None:
    """T26 fails closed when post-HITL approval clearance is missing or unapproved."""
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    cms_client = CmsClient()
    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=cms_client,
    )

    directive = DispatchDirective(
        dispatch_id="dispatch-unapproved",
        task_id="task-1",
        action_preview_id="prev-diff-unapproved",
        signature="sig",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        payload={"entry_id": "p1"},
    )

    with pytest.raises(ApprovalRequiredError):
        await gateway.execute(directive)


@pytest.mark.asyncio
async def test_t26_fails_closed_on_invalid_or_tampered_signature(ed25519_keypair) -> None:
    """T26 rejects dispatch with forged or corrupted Ed25519 signature."""
    _, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    preview, content_hash = _make_preview()
    hitl.submit_for_approval(preview)
    clearance = _make_clearance(preview.preview_id, "tenant-alpha", content_hash, public_pem)
    decision = hitl.decide(preview.preview_id, approved=True, approver="[email protected]", approver_role=ReviewerRole.ENGINEERING, tenant_id="tenant-alpha")
    decision.clearance = clearance

    cms_client = CmsClient()
    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=cms_client,
    )

    directive = DispatchDirective(
        dispatch_id="dispatch-bad-sig",
        task_id="task-dev-1",
        action_preview_id=preview.preview_id,
        signature="corrupted_signature_payload",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        tenant_id="tenant-alpha",
        preview_content_hash=content_hash,
        payload={"entry_id": "p1"},
    )

    with pytest.raises(SignatureVerificationError):
        await gateway.execute(directive)

    # Verify zero writes reached CMS live store
    assert await cms_client.read_published("pages") == []


@pytest.mark.asyncio
async def test_t26_fails_closed_on_wrong_tenant(ed25519_keypair) -> None:
    """T26 rejects cross-tenant tokens or clearance tenant mismatches."""
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    preview, content_hash = _make_preview(tenant_id="tenant-alpha")
    hitl.submit_for_approval(preview)
    clearance = _make_clearance(preview.preview_id, "tenant-alpha", content_hash, public_pem)
    decision = hitl.decide(preview.preview_id, approved=True, approver="[email protected]", approver_role=ReviewerRole.ENGINEERING, tenant_id="tenant-alpha")
    decision.clearance = clearance

    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=CmsClient(),
    )

    # Attempting to actuate for tenant-beta using tenant-alpha approval
    directive = DispatchDirective(
        dispatch_id="dispatch-cross-tenant",
        task_id="task-dev-1",
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        tenant_id="tenant-beta",  # Mismatch!
        payload={"entry_id": "p1"},
    )
    sig = sign_payload(canonical_dispatch_bytes(directive), private_key)
    directive = directive.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="Tenant authority mismatch"):
        await gateway.execute(directive)


@pytest.mark.asyncio
async def test_t26_fails_closed_on_altered_or_stale_artifact_payload(ed25519_keypair) -> None:
    """T26 rejects payloads whose content hash does not match the approved clearance hash."""
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    preview, content_hash = _make_preview()
    hitl.submit_for_approval(preview)
    clearance = _make_clearance(preview.preview_id, "tenant-alpha", content_hash, public_pem)
    decision = hitl.decide(preview.preview_id, approved=True, approver="[email protected]", approver_role=ReviewerRole.ENGINEERING, tenant_id="tenant-alpha")
    decision.clearance = clearance

    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=CmsClient(),
    )

    # Directive carrying a tampered preview_content_hash
    directive = DispatchDirective(
        dispatch_id="dispatch-tampered",
        task_id="task-dev-1",
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        tenant_id="tenant-alpha",
        preview_content_hash="tampered_hash_value_12345",  # Mismatch!
        payload={"entry_id": "p1"},
    )
    sig = sign_payload(canonical_dispatch_bytes(directive), private_key)
    directive = directive.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="Preview content hash mismatch"):
        await gateway.execute(directive)


@pytest.mark.asyncio
async def test_t26_fails_closed_on_scope_escalation(ed25519_keypair) -> None:
    """T26 rejects deployment items or files exceeding the approved scope."""
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    preview, content_hash = _make_preview()
    hitl.submit_for_approval(preview)
    clearance = _make_clearance(
        preview.preview_id,
        "tenant-alpha",
        content_hash,
        public_pem,
        approved_scope={
            "permitted_content_types": ["pages"],
            "permitted_entries": ["page-landing"],
            "permitted_files": ["pages/landing.html"],
        },
    )
    decision = hitl.decide(preview.preview_id, approved=True, approver="[email protected]", approver_role=ReviewerRole.ENGINEERING, tenant_id="tenant-alpha")
    decision.clearance = clearance

    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=CmsClient(),
    )

    # Payload attempts to modify an unapproved file 'unauthorized.py'
    payload = {
        "code_diffs": [{"file_path": "backend/unauthorized.py", "diff_unified": "+ malicious code"}],
    }
    directive = DispatchDirective(
        dispatch_id="dispatch-scope-escalate",
        task_id="task-dev-1",
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        tenant_id="tenant-alpha",
        preview_content_hash=content_hash,
        payload=payload,
    )
    sig = sign_payload(canonical_dispatch_bytes(directive), private_key)
    directive = directive.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="Payload contains unapproved code diff files"):
        await gateway.execute(directive)


@pytest.mark.asyncio
async def test_t26_idempotent_duplicate_dispatch_safe(ed25519_keypair) -> None:
    """Replaying identical dispatch returns cached deployment result without duplicate writes."""
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    preview, content_hash = _make_preview()
    hitl.submit_for_approval(preview)
    clearance = _make_clearance(preview.preview_id, "tenant-alpha", content_hash, public_pem)
    decision = hitl.decide(preview.preview_id, approved=True, approver="[email protected]", approver_role=ReviewerRole.ENGINEERING, tenant_id="tenant-alpha")
    decision.clearance = clearance

    cms_client = CmsClient()
    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=cms_client,
    )

    payload = {"entry_id": "page-idemp", "content_type": "pages", "title": "Idempotent Page"}
    directive = DispatchDirective(
        dispatch_id="dispatch-idemp",
        task_id="task-dev-1",
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        tenant_id="tenant-alpha",
        preview_content_hash=content_hash,
        idempotency_key="key-idemp-1",
        payload=payload,
    )
    sig = sign_payload(canonical_dispatch_bytes(directive), private_key)
    directive = directive.model_copy(update={"signature": sig})

    # First dispatch
    res1 = await gateway.execute(directive)
    assert res1["status"] == "published"

    # Duplicate identical dispatch
    res2 = await gateway.execute(directive)
    assert res2 == res1

    # Ensure CMS store contains exactly 1 entry
    published = await cms_client.read_published("pages", tenant_id="tenant-alpha")
    assert len(published) == 1


@pytest.mark.asyncio
async def test_t26_handles_cms_adapter_failure_and_marks_cts_failed(ed25519_keypair) -> None:
    """When CMS adapter raises failure, OutboundGateway transitions CTS task to FAILED."""
    private_key, public_pem = ed25519_keypair
    tenant_id = "tenant-alpha"
    hitl = HitlCoordinator()
    preview, content_hash = _make_preview()
    hitl.submit_for_approval(preview)
    clearance = _make_clearance(preview.preview_id, tenant_id, content_hash, public_pem)
    decision = hitl.decide(preview.preview_id, approved=True, approver="[email protected]", approver_role=ReviewerRole.ENGINEERING, tenant_id=tenant_id)
    decision.clearance = clearance

    # Setup CTS
    repo = InMemoryTaskStateRepository()
    task_service = TaskStateService(repository=repo, state_machine=TaskStateMachine())
    await repo.save_state(
        tenant_id,
        CanonicalTaskState(
            task_id="task-fail-1",
            directive_id="dir-fail",
            worker_role=WorkerRole.DEVELOPMENT,
            status=TaskStatus.APPROVED,
        ),
    )

    # Faulty CMS client that raises an exception on deploy
    class FaultyCmsClient(CmsClient):
        async def deploy_payload(self, payload: dict[str, Any], tenant_id: str | None = None) -> dict[str, Any]:
            raise RuntimeError("Headless CMS 503 Service Unavailable")

    prov_repo = FakeProvenanceRepository()
    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=FaultyCmsClient(),
        task_state_service=task_service,
        provenance_recorder=ProvenanceRecorder(repository=prov_repo),
    )

    directive = DispatchDirective(
        dispatch_id="dispatch-failure",
        task_id="task-fail-1",
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        tenant_id=tenant_id,
        preview_content_hash=content_hash,
        payload={"entry_id": "fail-entry"},
    )
    sig = sign_payload(canonical_dispatch_bytes(directive), private_key)
    directive = directive.model_copy(update={"signature": sig})

    with pytest.raises(RuntimeError, match="Headless CMS 503 Service Unavailable"):
        await gateway.execute(directive)

    # Verify CTS transitioned to FAILED
    state = await task_service.get_state("task-fail-1")
    assert state.status == TaskStatus.FAILED

    # Verify failure recorded in provenance
    records = await prov_repo.chain(tenant_id=tenant_id)
    assert any(r.activity == "outbound_cms_deployment_failed" for r in records)


@pytest.mark.asyncio
async def test_t26_rollback_recovery_supported() -> None:
    """CmsClient supports rollback to previous published version in case of recovery need."""
    cms = CmsClient()
    tenant_id = "tenant-alpha"

    # Version 1
    await cms.publish_entry("pages", "hero-page", tenant_id=tenant_id, version="v1.0", payload={"headline": "Initial"})
    assert (await cms.read_published("pages", tenant_id=tenant_id, entry_id="hero-page"))[0]["headline"] == "Initial"

    # Version 2
    await cms.publish_entry("pages", "hero-page", tenant_id=tenant_id, version="v2.0", payload={"headline": "Updated"})
    assert (await cms.read_published("pages", tenant_id=tenant_id, entry_id="hero-page"))[0]["headline"] == "Updated"

    # Rollback to Version 1
    rollback_res = await cms.rollback_entry("pages", "hero-page", tenant_id=tenant_id)
    assert rollback_res["status"] == "rolled_back"
    assert (await cms.read_published("pages", tenant_id=tenant_id, entry_id="hero-page"))[0]["headline"] == "Initial"


@pytest.mark.asyncio
async def test_t26_unsupported_action_or_channel_misuse_blocked(ed25519_keypair) -> None:
    """OutboundGateway blocks unsupported actions (e.g. ad launch or db purge) on the CMS channel."""
    private_key, public_pem = ed25519_keypair
    hitl = HitlCoordinator()
    preview, content_hash = _make_preview()
    hitl.submit_for_approval(preview)
    clearance = _make_clearance(preview.preview_id, "tenant-alpha", content_hash, public_pem)
    decision = hitl.decide(preview.preview_id, approved=True, approver="[email protected]", approver_role=ReviewerRole.ENGINEERING, tenant_id="tenant-alpha")
    decision.clearance = clearance

    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=CmsClient(),
    )

    directive = DispatchDirective(
        dispatch_id="dispatch-unsupported",
        task_id="task-dev-1",
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        action_type="launch_ad_campaign",  # Unsupported action on CMS!
        tenant_id="tenant-alpha",
        preview_content_hash=content_hash,
        payload={"entry_id": "p1"},
    )
    sig = sign_payload(canonical_dispatch_bytes(directive), private_key)
    directive = directive.model_copy(update={"signature": sig})

    with pytest.raises(PolicyViolationError, match="not a permitted website/CMS actuation"):
        await gateway.execute(directive)


def test_t26_direct_write_bypass_blocked_model_a() -> None:
    """Model A architectural invariant: development agent and workers cannot import CmsClient or directly deploy."""
    import inspect
    from app.agents import development

    source = inspect.getsource(development)
    assert "from app.integrations.cms.client import CmsClient" not in source
    assert "CmsClient(" not in source


@pytest.mark.asyncio
async def test_t26_secret_redaction_in_provenance_and_logs(ed25519_keypair) -> None:
    """Passwords, api_keys, and bearer tokens in deployment payload are scrubbed in provenance and logs."""
    private_key, public_pem = ed25519_keypair
    tenant_id = "tenant-alpha"
    hitl = HitlCoordinator()
    preview, content_hash = _make_preview()
    hitl.submit_for_approval(preview)
    clearance = _make_clearance(preview.preview_id, tenant_id, content_hash, public_pem)
    decision = hitl.decide(preview.preview_id, approved=True, approver="[email protected]", approver_role=ReviewerRole.ENGINEERING, tenant_id=tenant_id)
    decision.clearance = clearance

    prov_repo = FakeProvenanceRepository()
    gateway = OutboundGateway(
        hitl=hitl,
        crypto_validator=CryptographicValidator(public_pem),
        cms_client=CmsClient(),
        provenance_recorder=ProvenanceRecorder(repository=prov_repo),
    )

    # Payload with sensitive keys
    payload = {
        "entry_id": "secret-page",
        "api_key": "super-secret-key-12345",
        "nested_auth": {"client_secret": "my-client-secret-999"},
    }
    directive = DispatchDirective(
        dispatch_id="dispatch-secret",
        task_id="task-dev-1",
        action_preview_id=preview.preview_id,
        signature="",
        approved_by="[email protected]",
        approved_at=datetime.now(UTC),
        channel="cms",
        tenant_id=tenant_id,
        preview_content_hash=content_hash,
        payload=payload,
    )
    sig = sign_payload(canonical_dispatch_bytes(directive), private_key)
    directive = directive.model_copy(update={"signature": sig})

    result = await gateway.execute(directive)

    # Check provenance records
    records = await prov_repo.chain(tenant_id=tenant_id)
    dumped_records = json.dumps([r.model_dump() for r in records], default=str)
    assert "super-secret-key-12345" not in dumped_records
    assert "my-client-secret-999" not in dumped_records
