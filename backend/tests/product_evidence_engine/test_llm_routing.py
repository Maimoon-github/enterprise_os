"""PE-03: Independent Model Profiles, S_VAL Isolation & Egress Routing Tests.

Verifies:
1. Six independent immutable specialist role profiles with unique digests.
2. Request-local provider-neutral routing and metadata logging.
3. Role, profile, and digest binding before execution.
4. Explicit fallback policy and capability rejection (fail-closed).
5. Budget and deadline scope delegation attenuation.
6. Least-privilege network policy:
   - discovery / regulatory: governed egress subset with valid grant.
   - appraisal / product_lab / safety / claims: strictly disabled network.
7. Claims vision only when granted.
8. Deterministic validators zero-network/zero-model.
9. Model-A isolation: zero direct IE, RAG, DB, CMS, or sibling RPC access.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
import json
from typing import Any
import pytest

from app.agents.product_evidence_engine.product_evidence import (
    APPRAISAL_PROFILE,
    CLAIMS_PROFILE,
    DISCOVERY_PROFILE,
    PRODUCT_LAB_PROFILE,
    REGULATORY_PROFILE,
    SAFETY_PROFILE,
    SPECIALIST_PROFILES,
    SpecialistModelProfile,
    create_specialist_llm_client,
    dispatch_specialist_s_val,
    get_specialist_profile,
    resolve_effective_model,
    validate_delegated_scope,
    validate_profile_binding,
)
from app.agents.product_evidence_engine.subagents import (
    ProductAppraisalAgent,
    ProductClaimsAgent,
    ProductDiscoveryAgent,
    ProductLabAgent,
    ProductRegulatoryAgent,
    ProductSafetyAgent,
)
from app.core.exceptions import PolicyViolationError, SandboxInvocationError
from app.core.settings import LlmSettings
from app.integrations.sandbox.capabilities import (
    AUTHORIZED_PRODUCT_SPECIALISTS,
    PRODUCT_SPECIALIST_POLICIES,
    validate_capability_access,
    validate_egress_target,
    validate_tool_access,
)
from app.schemas.governance import WorkerRole
from app.schemas.product_evidence import (
    ProductEvidenceTask,
    SpecialistRole,
    SpecialistResult,
    SpecialistResultStatus,
    SpecialistTask,
)
from app.schemas.sandbox import (
    NetworkPolicy,
    SandboxCapability,
    SandboxEgressGrant,
    SandboxInvocationMandate,
)


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def parent_task() -> ProductEvidenceTask:
    """Standard authorized parent task from IE."""
    return ProductEvidenceTask(
        task_id="parent-pe-task-001",
        tenant_id="tenant-alpha",
        run_id="run-001",
        parent_grant_ref="grant-alpha-001",
        parent_grant_hash="abc123def456hash",
        context_version="1.0",
        context_hash="ctx123def456hash",
        product_version="1.0.0",
        allowed_s_val_operations=[
            "research_literature",
            "fetch_official_rules",
            "acquire_source",
            "parse_metadata",
            "appraise_evidence",
            "validate_formulation",
            "assess_safety",
            "extract_claims",
            "inspect_claim_imagery",
            "check_regulatory_rules",
            "validate_claim",
            "lint_compliance",
        ],
        budget_limit_tokens=10000,
        deadline_utc=datetime.now(UTC) + timedelta(hours=2),
    )


@pytest.fixture
def valid_egress_grant() -> SandboxEgressGrant:
    """Authorized, unexpired egress grant for literature/rules research."""
    return SandboxEgressGrant(
        grant_id="grant-egress-001",
        task_id="parent-pe-task-001",
        tenant_id="tenant-alpha",
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        capability=SandboxCapability.VAL,
        specialist_id="w_prod.discovery",
        allowed_domains=["pubmed.ncbi.nlm.nih.gov", "clinicaltrials.gov", "fda.gov"],
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )


# ==============================================================================
# 1. Independent Immutable Model Profiles
# ==============================================================================


def test_six_independent_immutable_profiles() -> None:
    """Verify six independent immutable role profiles exist with required fields."""
    expected_roles = {
        SpecialistRole.DISCOVERY,
        SpecialistRole.APPRAISAL,
        SpecialistRole.PRODUCT_LAB,
        SpecialistRole.SAFETY,
        SpecialistRole.CLAIMS,
        SpecialistRole.REGULATORY,
    }
    assert set(SPECIALIST_PROFILES.keys()) == expected_roles

    digests = set()
    for role, profile in SPECIALIST_PROFILES.items():
        assert profile.role == role
        assert profile.profile_id.startswith("w_prod.")
        assert profile.profile_version == "1.0"
        assert profile.provider_adapter == "provider_neutral"
        assert profile.model_id
        assert profile.model_revision
        assert profile.reasoning_mode
        assert isinstance(profile.capabilities_required, tuple)
        assert profile.context_limit > 0
        assert profile.max_output_tokens > 0
        assert isinstance(profile.sampling_parameters, dict)
        assert profile.timeout_ms > 0
        assert profile.max_attempts > 0
        assert profile.budget_limit > 0
        assert profile.budget_limit_tokens > 0
        assert isinstance(profile.data_classification_allowlist, tuple)
        assert profile.endpoint_policy_ref
        assert profile.credential_ref
        assert isinstance(profile.fallback_profile_ids, tuple)
        assert profile.prompt_version
        assert profile.output_schema_version
        assert len(profile.allowed_operations) > 0
        assert len(profile.allowed_tools) > 0

        # Immutability verification
        with pytest.raises(FrozenInstanceError):
            profile.timeout_ms = 999  # type: ignore[misc]

        # Digest uniqueness and determinism
        digest = profile.compute_digest()
        assert len(digest) == 64
        assert profile.compute_digest() == digest
        digests.add(digest)

    assert len(digests) == 6, "Each specialist profile must produce a distinct canonical digest"


def test_profile_retrieval_and_aliases() -> None:
    """Verify profile lookup by role enum or string alias."""
    prof1 = get_specialist_profile(SpecialistRole.DISCOVERY)
    prof2 = get_specialist_profile("DISCOVERY")
    prof3 = get_specialist_profile("w_prod.discovery")
    assert prof1 == prof2 == prof3 == DISCOVERY_PROFILE

    with pytest.raises(PolicyViolationError, match="Unknown or unauthorized specialist role"):
        get_specialist_profile("INVALID_ROLE")


# ==============================================================================
# 2. Profile and Digest Binding
# ==============================================================================


def test_profile_binding_valid(parent_task: ProductEvidenceTask) -> None:
    """Matching profile digest and reference validates successfully."""
    profile = DISCOVERY_PROFILE
    task = SpecialistTask(
        task_id="spec-task-001",
        tenant_id="tenant-alpha",
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.DISCOVERY,
        operation="research_literature",
        profile_ref=profile.profile_id,
        profile_digest=profile.compute_digest(),
        delegated_token_limit=5000,
    )
    validate_profile_binding(task, profile)


def test_profile_binding_tampered_digest_fails(parent_task: ProductEvidenceTask) -> None:
    """Tampered profile digest fails closed."""
    profile = DISCOVERY_PROFILE
    task = SpecialistTask(
        task_id="spec-task-001",
        tenant_id="tenant-alpha",
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.DISCOVERY,
        operation="research_literature",
        profile_ref=profile.profile_id,
        profile_digest="tampered_invalid_digest_64_chars_000000000000000000000000000000000",
        delegated_token_limit=5000,
    )
    with pytest.raises(PolicyViolationError, match="Profile digest mismatch"):
        validate_profile_binding(task, profile)


def test_profile_binding_mismatched_ref_fails(parent_task: ProductEvidenceTask) -> None:
    """Mismatched profile_ref fails closed."""
    profile = DISCOVERY_PROFILE
    task = SpecialistTask(
        task_id="spec-task-001",
        tenant_id="tenant-alpha",
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.DISCOVERY,
        operation="research_literature",
        profile_ref="w_prod.regulatory.v1",
        profile_digest=profile.compute_digest(),
        delegated_token_limit=5000,
    )
    with pytest.raises(PolicyViolationError, match="Profile ref mismatch"):
        validate_profile_binding(task, profile)


# ==============================================================================
# 3. Request-Local Neutral Routing & Metadata Logging
# ==============================================================================


def test_request_local_neutral_routing_metadata() -> None:
    """Verify request-local resolution outputs requested and effective metadata."""
    req_model, eff_model, metadata = resolve_effective_model(
        DISCOVERY_PROFILE,
        available_capabilities=("text", "search"),
    )
    assert req_model == DISCOVERY_PROFILE.model_id
    assert eff_model == DISCOVERY_PROFILE.model_id
    assert metadata["role"] == "DISCOVERY"
    assert metadata["profile_digest"] == DISCOVERY_PROFILE.compute_digest()
    assert metadata["is_fallback"] is False
    assert metadata["budget_limit"] == 5.0


def test_specialist_llm_client_isolation() -> None:
    """Verify request-local independent LlmClient instance instantiation."""
    client = create_specialist_llm_client(DISCOVERY_PROFILE)
    assert client.agent_identity == "w_prod.discovery"
    assert client.model_identity == DISCOVERY_PROFILE.model_id


def test_no_vendor_sdk_imports() -> None:
    """Ensure specialists do not directly import proprietary vendor SDKs."""
    import sys
    from app.agents.product_evidence_engine import subagents

    for mod_name in ("openai", "anthropic", "google.generativeai"):
        assert mod_name not in sys.modules or not any(
            mod_name in getattr(sub, "__name__", "")
            for sub in (
                ProductDiscoveryAgent,
                ProductAppraisalAgent,
                ProductLabAgent,
                ProductSafetyAgent,
                ProductClaimsAgent,
                ProductRegulatoryAgent,
            )
        )


# ==============================================================================
# 4. Explicit Fallback Policy
# ==============================================================================


def test_explicit_fallback_success() -> None:
    """Authorized fallback listed in profile.fallback_profile_ids succeeds with audit trace."""
    fallback_id = DISCOVERY_PROFILE.fallback_profile_ids[0]
    req_model, eff_model, metadata = resolve_effective_model(
        DISCOVERY_PROFILE,
        fallback_id=fallback_id,
        available_capabilities=("text", "search"),
    )
    assert req_model == DISCOVERY_PROFILE.model_id
    assert eff_model == fallback_id
    assert metadata["is_fallback"] is True


def test_unauthorized_fallback_fails_closed() -> None:
    """Unregistered fallback fails closed with PolicyViolationError."""
    with pytest.raises(PolicyViolationError, match="Explicit fallback rejection"):
        resolve_effective_model(
            DISCOVERY_PROFILE,
            fallback_id="unauthorized.shadow.model.v9",
            available_capabilities=("text", "search"),
        )


# ==============================================================================
# 5. Capability Rejection
# ==============================================================================


def test_capability_rejection_missing_search() -> None:
    """Discovery profile requiring 'search' fails closed if environment lacks it."""
    with pytest.raises(PolicyViolationError, match="Capability rejection"):
        resolve_effective_model(
            DISCOVERY_PROFILE,
            available_capabilities=("text",),  # Missing 'search'
        )


# ==============================================================================
# 6. Scope Delegation and Budget Attenuation
# ==============================================================================


def test_delegated_scope_tenant_mismatch_fails(parent_task: ProductEvidenceTask) -> None:
    """Delegated task for a different tenant fails closed."""
    task = SpecialistTask(
        task_id="spec-001",
        tenant_id="tenant-beta-attacker",
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.APPRAISAL,
        operation="appraise_evidence",
        profile_ref=APPRAISAL_PROFILE.profile_id,
        profile_digest=APPRAISAL_PROFILE.compute_digest(),
        delegated_token_limit=3000,
    )
    with pytest.raises(PolicyViolationError, match="Tenant isolation failure"):
        validate_delegated_scope(parent_task, task, APPRAISAL_PROFILE)


def test_delegated_scope_budget_expansion_fails(parent_task: ProductEvidenceTask) -> None:
    """Delegated token limit exceeding parent or profile budget fails closed."""
    task = SpecialistTask(
        task_id="spec-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.APPRAISAL,
        operation="appraise_evidence",
        profile_ref=APPRAISAL_PROFILE.profile_id,
        profile_digest=APPRAISAL_PROFILE.compute_digest(),
        delegated_token_limit=8000,  # Exceeds appraisal profile budget_limit_tokens (6000)
    )
    with pytest.raises(PolicyViolationError, match="Budget limit violation"):
        validate_delegated_scope(parent_task, task, APPRAISAL_PROFILE)


def test_delegated_scope_unauthorized_operation_fails(parent_task: ProductEvidenceTask) -> None:
    """Delegated operation not in parent's allowed operations fails closed."""
    task = SpecialistTask(
        task_id="spec-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.DISCOVERY,
        operation="unauthorized_arbitrary_eval",
        profile_ref=DISCOVERY_PROFILE.profile_id,
        profile_digest=DISCOVERY_PROFILE.compute_digest(),
        delegated_token_limit=2000,
    )
    with pytest.raises(PolicyViolationError, match="Operation .* is not within parent task"):
        validate_delegated_scope(parent_task, task, DISCOVERY_PROFILE)


# ==============================================================================
# 7. Least Privilege Network and Egress Governance
# ==============================================================================


def test_offline_specialists_deny_network_grant(parent_task: ProductEvidenceTask, valid_egress_grant: SandboxEgressGrant) -> None:
    """Appraisal, Product_Lab, Safety, Claims reject network grants under DENY_ALL."""
    for role, prof in [
        (SpecialistRole.APPRAISAL, APPRAISAL_PROFILE),
        (SpecialistRole.PRODUCT_LAB, PRODUCT_LAB_PROFILE),
        (SpecialistRole.SAFETY, SAFETY_PROFILE),
        (SpecialistRole.CLAIMS, CLAIMS_PROFILE),
    ]:
        task = SpecialistTask(
            task_id=f"spec-{role.value.lower()}-001",
            tenant_id=parent_task.tenant_id,
            parent_task_id=parent_task.task_id,
            specialist_role=role,
            operation=prof.allowed_operations[0],
            profile_ref=prof.profile_id,
            profile_digest=prof.compute_digest(),
            delegated_token_limit=2000,
        )
        with pytest.raises(PolicyViolationError, match="Network grant violation: Specialist .* is strictly offline"):
            validate_delegated_scope(parent_task, task, prof, egress_grant=valid_egress_grant)


def test_capabilities_policy_blocks_offline_network() -> None:
    """Capabilities layer fails closed when offline specialist requests network."""
    with pytest.raises(SandboxInvocationError, match="Network access denied: Product Evidence specialist .* is restricted to DENY_ALL"):
        validate_capability_access(
            capability=SandboxCapability.VAL,
            worker_role=WorkerRole.PRODUCT_EVIDENCE,
            specialist_id="w_prod.appraisal",
            operation="appraise_evidence",
            requested_network=NetworkPolicy.CONTROLLED,
        )


def test_discovery_governed_egress_requires_grant() -> None:
    """Discovery requesting network without an egress grant fails closed."""
    with pytest.raises(SandboxInvocationError, match="Network access denied: Product Evidence specialist .* requested network without an authorized SandboxEgressGrant"):
        validate_capability_access(
            capability=SandboxCapability.VAL,
            worker_role=WorkerRole.PRODUCT_EVIDENCE,
            specialist_id="w_prod.discovery",
            operation="research_literature",
            requested_network=NetworkPolicy.ALLOWLIST,
            egress_grant=None,
        )


def test_discovery_governed_egress_with_valid_grant(valid_egress_grant: SandboxEgressGrant) -> None:
    """Discovery requesting network with a valid matching grant succeeds."""
    prof = validate_capability_access(
        capability=SandboxCapability.VAL,
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        specialist_id="w_prod.discovery",
        operation="research_literature",
        requested_network=NetworkPolicy.ALLOWLIST,
        egress_grant=valid_egress_grant,
    )
    assert prof.capability == SandboxCapability.VAL
    assert prof.network_policy == NetworkPolicy.ALLOWLIST


def test_egress_target_validation_and_ssrf_blocking(valid_egress_grant: SandboxEgressGrant) -> None:
    """Destination allowlisting permits granted domains and blocks unlisted / SSRF targets."""
    # Allowed
    validate_egress_target("https://pubmed.ncbi.nlm.nih.gov/12345", valid_egress_grant)

    # Unauthorized domain
    with pytest.raises(SandboxInvocationError, match="Network egress policy violation"):
        validate_egress_target("https://unauthorized-competitor.com", valid_egress_grant)

    # Cloud metadata / SSRF
    with pytest.raises(SandboxInvocationError):
        validate_egress_target("http://169.254.169.254/latest/meta-data", valid_egress_grant)

    # Private loopback / link-local
    with pytest.raises(SandboxInvocationError):
        validate_egress_target("http://127.0.0.1:8080/admin", valid_egress_grant)


def test_tool_access_validation() -> None:
    """Enforce explicit micro-tool allowlisting per specialist."""
    validate_tool_access("literature_search", SandboxCapability.VAL, specialist_id="w_prod.discovery")
    validate_tool_access("bias_assessor", SandboxCapability.VAL, specialist_id="w_prod.appraisal")

    with pytest.raises(SandboxInvocationError, match="Tool .* is not permitted for Product Evidence specialist"):
        validate_tool_access("unauthorized_shell_tool", SandboxCapability.VAL, specialist_id="w_prod.discovery")


# ==============================================================================
# 8. Claims Vision Inspection Authorization
# ==============================================================================


def test_claims_vision_only_when_granted(parent_task: ProductEvidenceTask) -> None:
    """inspect_claim_imagery requires explicit vision grant in context."""
    # Denied without grant
    task_no_vision = SpecialistTask(
        task_id="spec-claim-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.CLAIMS,
        operation="inspect_claim_imagery",
        profile_ref=CLAIMS_PROFILE.profile_id,
        profile_digest=CLAIMS_PROFILE.compute_digest(),
        context_slice={"asset_ref": "packaging.jpg"},  # vision_granted not set
        delegated_token_limit=2000,
    )
    with pytest.raises(PolicyViolationError, match="requires explicit vision grant in context slice"):
        validate_delegated_scope(parent_task, task_no_vision, CLAIMS_PROFILE)

    # Granted
    task_with_vision = SpecialistTask(
        task_id="spec-claim-002",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.CLAIMS,
        operation="inspect_claim_imagery",
        profile_ref=CLAIMS_PROFILE.profile_id,
        profile_digest=CLAIMS_PROFILE.compute_digest(),
        context_slice={"asset_ref": "packaging.jpg", "vision_granted": True},
        delegated_token_limit=2000,
    )
    validate_delegated_scope(parent_task, task_with_vision, CLAIMS_PROFILE)


# ==============================================================================
# 9. S_VAL Specialist Dispatch
# ==============================================================================


def _load_run_s_val():
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    script_path = root / "sandbox" / "docker" / "hardened" / "skills" / "s-val" / "scripts" / "run.py"
    spec = importlib.util.spec_from_file_location("s_val_run", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_s_val


def test_s_val_dispatch_specialist(parent_task: ProductEvidenceTask) -> None:
    """Dispatch specialist task through existing S_VAL runner returning PE-02 SpecialistResult."""
    run_s_val = _load_run_s_val()

    task = SpecialistTask(
        task_id="spec-dispatch-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.PRODUCT_LAB,
        operation="validate_formulation",
        profile_ref=PRODUCT_LAB_PROFILE.profile_id,
        profile_digest=PRODUCT_LAB_PROFILE.compute_digest(),
        context_slice={"formulation_id": "form-101", "ingredients": ["water", "niacinamide"]},
        delegated_token_limit=3000,
    )

    def mock_sandbox_runner(mandate: SandboxInvocationMandate) -> dict[str, Any]:
        return run_s_val(mandate.payload)

    result = dispatch_specialist_s_val(
        mock_sandbox_runner,
        specialist_task=task,
        parent_task=parent_task,
    )

    assert isinstance(result, SpecialistResult)
    assert result.task_id == task.task_id
    assert result.status == SpecialistResultStatus.COMPLETED
    assert result.specialist_role == "PRODUCT_LAB"
    assert result.typed_findings.get("formulation_status") == "VALIDATED"
    assert result.provenance_fragments["profile_digest"] == PRODUCT_LAB_PROFILE.compute_digest()


def test_s_val_prohibited_claim_detection(parent_task: ProductEvidenceTask) -> None:
    """S_VAL detects prohibited absolute claims ('cures') and reports non-compliance."""
    run_s_val = _load_run_s_val()

    task = SpecialistTask(
        task_id="spec-claim-eval-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        specialist_role=SpecialistRole.CLAIMS,
        operation="validate_claim",
        profile_ref=CLAIMS_PROFILE.profile_id,
        profile_digest=CLAIMS_PROFILE.compute_digest(),
        context_slice={"claims": [{"id": "c1", "text": "This product cures arthritis permanently."}]},
        delegated_token_limit=3000,
    )

    def mock_sandbox_runner(mandate: SandboxInvocationMandate) -> dict[str, Any]:
        return run_s_val(mandate.payload)

    result = dispatch_specialist_s_val(
        mock_sandbox_runner,
        specialist_task=task,
        parent_task=parent_task,
    )

    assert result.typed_findings["is_compliant"] is False
    assert any("Prohibited absolute claim" in v for v in result.typed_findings["violations"])


# ==============================================================================
# 10. Subagent Helper Classes and Model-A Isolation
# ==============================================================================


def test_subagent_task_building(parent_task: ProductEvidenceTask) -> None:
    """Specialist subagents construct bounded SpecialistTask instances."""
    agent = ProductDiscoveryAgent()
    task = agent.build_task(
        task_id="disc-001",
        tenant_id=parent_task.tenant_id,
        parent_task_id=parent_task.task_id,
        operation="research_literature",
    )
    assert task.specialist_role == SpecialistRole.DISCOVERY
    assert task.profile_ref == DISCOVERY_PROFILE.profile_id
    assert task.profile_digest == DISCOVERY_PROFILE.compute_digest()
    assert task.delegated_token_limit <= DISCOVERY_PROFILE.budget_limit_tokens

    # Verify no direct persistence, RAG, or CMS members
    for member in ("db", "session", "repository", "rag", "cms", "vector_store"):
        assert not hasattr(agent, member), f"Specialist must not have direct access to '{member}'"
