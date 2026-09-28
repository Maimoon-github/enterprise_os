"""Tests for Strategy Engine Pydantic-v2 domain contracts (T2).

Validates AllocationConstraint, ChannelSpendProposal, StrategyDirective,
and StrategyResultEnvelope including boundaries, invariants, serialization,
and bidirectional compatibility with TaskGrant/EvidenceEnvelope.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import (
    ChannelAllocation,
    ConfidenceInterval,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    TaskGrant,
)
from app.schemas.governance import Directive, TenantScope, WorkerRole
from app.schemas.sandbox import (
    SandboxExecutionReceipt,
    SandboxExecutionStatus,
    SandboxTeardownReceipt,
)
from app.schemas.strategy import (
    AllocationConstraint,
    ChannelSpendProposal,
    SAllocDomainStatus,
    SAllocMandate,
    SAllocResult,
    StrategyDirective,
    StrategyResultEnvelope,
    canonical_json_dumps,
    compute_canonical_sha256,
    parse_canonical_json_strictly,
)



# =============================================================================
# 1. AllocationConstraint Tests
# =============================================================================


def test_allocation_constraint_valid() -> None:
    """Valid constraints normalize channel and preserve valid bounds."""
    c = AllocationConstraint(
        channel="  META ",
        min_spend=1000.0,
        max_spend=5000.0,
        min_share=0.1,
        max_share=0.5,
    )
    assert c.channel == "meta"
    assert c.min_spend == 1000.0
    assert c.max_spend == 5000.0
    assert c.min_share == 0.1
    assert c.max_share == 0.5


def test_allocation_constraint_invalid_bounds() -> None:
    """AllocationConstraint rejects min_spend > max_spend or min_share > max_share."""
    with pytest.raises(ValidationError, match="min_spend .* cannot exceed max_spend"):
        AllocationConstraint(channel="meta", min_spend=5000.0, max_spend=1000.0)

    with pytest.raises(ValidationError, match="min_share .* cannot exceed max_share"):
        AllocationConstraint(channel="google", min_share=0.6, max_share=0.3)


def test_allocation_constraint_empty_channel_and_extra_fields() -> None:
    """AllocationConstraint rejects empty channel and extra fields."""
    with pytest.raises(ValidationError):
        AllocationConstraint(channel="   ")

    with pytest.raises(ValidationError):
        AllocationConstraint(channel="meta", extra_prop="disallowed")  # type: ignore[call-arg]


# =============================================================================
# 2. ChannelSpendProposal Tests
# =============================================================================


def test_channel_spend_proposal_valid_and_aliases() -> None:
    """ChannelSpendProposal normalizes channel and supports spend/percentage aliases."""
    prop = ChannelSpendProposal(
        channel="Google",
        allocated_amount=12000.0,
        percentage_of_total=40.0,
        role="Intent Capture",
        primary_kpi="CAC / ROAS",
        prior_roas=3.8,
        target_roas_range=(3.2, 4.4),
        constraints=["target_cac_lt_60"],
    )
    assert prop.channel == "google"
    assert prop.spend == 12000.0
    assert prop.percentage == 40.0
    assert prop.role == "Intent Capture"
    assert prop.prior_roas == 3.8

    # Alias construction
    prop_alias = ChannelSpendProposal(
        channel="meta",
        spend=8000.0,
        percentage=26.67,
    )
    assert prop_alias.allocated_amount == 8000.0
    assert prop_alias.percentage_of_total == 26.67


def test_channel_spend_proposal_to_channel_allocation() -> None:
    """Conversion to canonical agent_contracts.ChannelAllocation."""
    prop = ChannelSpendProposal(
        channel="tiktok",
        spend=5000.0,
        percentage=16.67,
        role="Awareness",
        primary_kpi="CPM / Reach",
    )
    ca = prop.to_channel_allocation()
    assert isinstance(ca, ChannelAllocation)
    assert ca.channel == "tiktok"
    assert ca.allocated_amount == 5000.0
    assert ca.percentage_of_total == 16.67


def test_channel_spend_proposal_invalid() -> None:
    """Negative spend or invalid percentage triggers validation errors."""
    with pytest.raises(ValidationError):
        ChannelSpendProposal(channel="meta", allocated_amount=-500.0, percentage_of_total=20.0)

    with pytest.raises(ValidationError):
        ChannelSpendProposal(channel="meta", allocated_amount=500.0, percentage_of_total=120.0)


# =============================================================================
# 3. StrategyDirective Tests
# =============================================================================


def test_strategy_directive_construction_and_bounds() -> None:
    """StrategyDirective enforces budget ceiling, channel authorization, and serialization."""
    d = StrategyDirective(
        task_id="task-strat-01",
        tenant_id="tenant-alpha",
        brand_id="brand-glow",
        objective="Drive qualified acquisition",
        budget_ceiling=50000.0,
        authorized_channels=["meta", "google", "tiktok"],
        allocation_constraints=[
            AllocationConstraint(channel="meta", min_spend=5000.0, max_spend=25000.0)
        ],
        prior_roas={"meta": 4.0, "google": 3.5},
    )
    assert d.budget_ceiling == 50000.0
    assert "tiktok" in d.authorized_channels

    # Serialization round-trip
    dumped = d.model_dump(mode="json")
    loaded = StrategyDirective.model_validate(dumped)
    assert loaded == d


def test_strategy_directive_unauthorized_channel_rejected() -> None:
    """Constraints or priors referencing unauthorized channels raise ValueError."""
    with pytest.raises(ValidationError, match="unauthorized channel"):
        StrategyDirective(
            task_id="task-strat-bad",
            tenant_id="tenant-alpha",
            brand_id="brand-glow",
            objective="acquisition",
            budget_ceiling=10000.0,
            authorized_channels=["meta"],
            allocation_constraints=[AllocationConstraint(channel="unauthorized_network")],
        )

    with pytest.raises(ValidationError, match="unauthorized channel"):
        StrategyDirective(
            task_id="task-strat-bad-roas",
            tenant_id="tenant-alpha",
            brand_id="brand-glow",
            objective="acquisition",
            budget_ceiling=10000.0,
            authorized_channels=["meta"],
            prior_roas={"unauthorized_channel": 2.5},
        )


def test_strategy_directive_negative_budget_rejected() -> None:
    """Negative budget ceiling is rejected."""
    with pytest.raises(ValidationError):
        StrategyDirective(
            task_id="task-neg-budget",
            tenant_id="tenant-alpha",
            brand_id="brand-glow",
            objective="acquisition",
            budget_ceiling=-1000.0,
            authorized_channels=["meta"],
        )


def test_strategy_directive_from_grant_compatibility() -> None:
    """StrategyDirective derives cleanly from IE TaskGrant and context."""
    grant = TaskGrant(
        task_id="task-grant-strat",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant-beta", allowed_channels=["meta", "google"]),
        brand_id="brand-beta",
        objective="propose allocation",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        cts_state={"budget_cap": 20000.0},
    )
    context = {
        "budget": 25000.0,  # Must be clamped by cts_state budget_cap (20000.0)
        "channels": ["meta", "google", "disallowed_ch"],
        "prior_roas_meta": 4.5,
    }
    directive = StrategyDirective.from_grant(grant, context)
    assert directive.task_id == "task-grant-strat"
    assert directive.tenant_id == "tenant-beta"
    assert directive.budget_ceiling == 20000.0
    assert directive.authorized_channels == ["meta", "google"]
    assert directive.prior_roas.get("meta") == 4.5


# =============================================================================
# 4. StrategyResultEnvelope Tests
# =============================================================================


def test_strategy_result_envelope_valid() -> None:
    """StrategyResultEnvelope valid construction and downcast to EvidenceEnvelope."""
    plan = OmnichannelStrategyPlan(
        plan_id="plan-valid-01",
        tenant_id="tenant-alpha",
        brand_id="brand-glow",
        total_allocated=15000.0,
        budget_ceiling=20000.0,
        expected_blended_roas=3.6,
        confidence_score=0.82,
        primary_channel="meta",
        channel_allocations=[
            ChannelAllocation(channel="meta", allocated_amount=10000.0, percentage_of_total=66.7),
            ChannelAllocation(channel="google", allocated_amount=5000.0, percentage_of_total=33.3),
        ],
    )
    envelope = StrategyResultEnvelope(
        task_id="task-res-01",
        worker_role=WorkerRole.STRATEGY,
        confidence=ConfidenceInterval(point_estimate=0.82, lower_bound=0.70, upper_bound=0.92),
        evidence=["Blended ROAS: 3.6x"],
        findings=["Optimal media mix identified"],
        strategy_plan=plan,
        channel_proposals=[
            ChannelSpendProposal(channel="meta", spend=10000.0, percentage=66.7),  # type: ignore[call-arg]
            ChannelSpendProposal(channel="google", spend=5000.0, percentage=33.3),  # type: ignore[call-arg]
        ],
    )
    assert envelope.worker_role == WorkerRole.STRATEGY
    assert envelope.strategy_plan is not None
    assert envelope.strategy_plan.total_allocated == 15000.0

    # Downcast to base EvidenceEnvelope
    base_env = envelope.to_evidence_envelope()
    assert isinstance(base_env, EvidenceEnvelope)
    assert base_env.task_id == "task-res-01"


def test_strategy_result_envelope_budget_exceeded_rejected() -> None:
    """Total allocation exceeding budget ceiling raises ValidationError."""
    plan = OmnichannelStrategyPlan(
        plan_id="plan-bad-01",
        tenant_id="tenant-alpha",
        brand_id="brand-glow",
        total_allocated=25000.0,
        budget_ceiling=20000.0,  # Exceeded!
        expected_blended_roas=3.0,
        confidence_score=0.8,
        primary_channel="meta",
        channel_allocations=[
            ChannelAllocation(channel="meta", allocated_amount=25000.0, percentage_of_total=100.0),
        ],
    )
    with pytest.raises(ValidationError, match="exceeds budget_ceiling"):
        StrategyResultEnvelope(
            task_id="task-res-bad",
            worker_role=WorkerRole.STRATEGY,
            confidence=ConfidenceInterval(point_estimate=0.8, lower_bound=0.6, upper_bound=0.9),
            strategy_plan=plan,
        )


def test_strategy_result_envelope_invalid_confidence_rejected() -> None:
    """Confidence interval ordering violations are rejected."""
    with pytest.raises(ValidationError, match="Invalid confidence interval"):
        StrategyResultEnvelope(
            task_id="task-res-conf-bad",
            worker_role=WorkerRole.STRATEGY,
            confidence=ConfidenceInterval(point_estimate=0.5, lower_bound=0.8, upper_bound=0.9),
        )


# =============================================================================
# 5. SAllocDomainStatus & Independence from Transport Tests
# =============================================================================


def test_s_alloc_domain_statuses_complete_and_independent() -> None:
    """Verify all domain statuses are defined and distinct from transport execution statuses."""
    expected_domain_statuses = {
        "OK",
        "EVIDENCE_GAP",
        "INVALID_INPUT",
        "INFEASIBLE",
        "UNSUPPORTED_MODEL",
        "UNSUPPORTED_CONSTRAINT",
        "SOLVER_FAILED",
    }
    actual_domain_statuses = {s.value for s in SAllocDomainStatus}
    assert actual_domain_statuses == expected_domain_statuses

    # Domain status OK must not be equated with transport completion
    assert SAllocDomainStatus.OK.value != SandboxExecutionStatus.COMPLETED.value
    assert SAllocDomainStatus.INFEASIBLE.value not in [s.value for s in SandboxExecutionStatus]


# =============================================================================
# 6. Canonical JSON Serialization & Hashing Tests
# =============================================================================


def test_canonical_json_determinism_and_key_sorting() -> None:
    """Keys are sorted, whitespace is normalized, and output bytes are identical."""
    dict_1 = {"z_channel": "meta", "a_budget": 5000.0, "sub": {"b": 2, "a": 1}}
    dict_2 = {"sub": {"a": 1, "b": 2}, "a_budget": 5000.0, "z_channel": "meta"}

    bytes_1 = canonical_json_dumps(dict_1)
    bytes_2 = canonical_json_dumps(dict_2)
    assert bytes_1 == bytes_2
    assert b" " not in bytes_1  # minimal separators
    assert compute_canonical_sha256(dict_1) == compute_canonical_sha256(dict_2)


def test_canonical_json_rejects_nan_and_infinity() -> None:
    """NaN, Infinity, and -Infinity are strictly rejected in canonical serialization."""
    with pytest.raises(ValueError, match="Non-finite float value"):
        canonical_json_dumps({"spend": float("nan")})

    with pytest.raises(ValueError, match="Non-finite float value"):
        canonical_json_dumps({"spend": float("inf")})

    with pytest.raises(ValueError, match="Non-finite float value"):
        canonical_json_dumps({"spend": float("-inf")})


def test_strict_json_parser_rejects_duplicate_keys_and_nan() -> None:
    """parse_canonical_json_strictly rejects duplicate keys and literal NaN/Infinity."""
    dup_json = '{"channel": "meta", "budget": 1000, "channel": "google"}'
    with pytest.raises(ValueError, match="Duplicate key detected"):
        parse_canonical_json_strictly(dup_json)

    nan_json = '{"channel": "meta", "spend": NaN}'
    with pytest.raises(ValueError, match="Illegal non-finite constant"):
        parse_canonical_json_strictly(nan_json)

    inf_json = '{"channel": "meta", "spend": Infinity}'
    with pytest.raises(ValueError, match="Illegal non-finite constant"):
        parse_canonical_json_strictly(inf_json)


def test_canonical_digest_excludes_self_referential_fields() -> None:
    """Self-referential digest fields (input_sha256, output_sha256, signature) do not change digest."""
    base = {"task_id": "task-01", "budget_ceiling": 10000.0}
    with_digests = {
        "task_id": "task-01",
        "budget_ceiling": 10000.0,
        "input_sha256": "abcdef1234567890",
        "output_sha256": "fedcba0987654321",
        "signature": "sig-000",
    }
    assert compute_canonical_sha256(base) == compute_canonical_sha256(with_digests)


# =============================================================================
# 7. SAllocMandate Construction, Validation & Invariants
# =============================================================================


def test_s_alloc_mandate_valid_construction() -> None:
    """SAllocMandate constructs cleanly and generates deterministic input hash."""
    mandate = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-001",
        parent_grant_id="grant-001",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        authorized_channels=["meta", "google"],
        budget_ceiling=10000.0,
        currency="USD",
        token_quota=2048,
        time_quota_seconds=60,
    )
    assert mandate.tenant_id == "tenant-alpha"
    assert mandate.currency == "USD"
    assert mandate.budget_ceiling == 10000.0
    assert mandate.token_quota == 2048
    assert mandate.time_quota_seconds == 60

    digest = mandate.compute_input_digest()
    assert len(digest) == 64
    assert mandate.compute_input_digest() == digest


def test_s_alloc_mandate_monetary_zero_preserved_and_negatives_rejected() -> None:
    """Explicit zero budget is preserved; negative and non-finite money is rejected."""
    zero_mandate = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-zero",
        parent_grant_id="grant-001",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        authorized_channels=["meta"],
        budget_ceiling=0.0,
    )
    assert zero_mandate.budget_ceiling == 0.0

    # Negative budget rejected
    with pytest.raises(ValidationError):
        SAllocMandate(
            tenant_id="tenant-alpha",
            task_id="task-neg",
            parent_grant_id="grant-001",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            authorized_channels=["meta"],
            budget_ceiling=-500.0,
        )

    # Non-finite budget rejected
    with pytest.raises(ValidationError):
        SAllocMandate(
            tenant_id="tenant-alpha",
            task_id="task-nan",
            parent_grant_id="grant-001",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            authorized_channels=["meta"],
            budget_ceiling=float("nan"),
        )


def test_s_alloc_mandate_currency_and_channel_normalization() -> None:
    """Currency is normalized to uppercase 3-letters; channels are lowercased and deduplicated."""
    mandate = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-norm",
        parent_grant_id="grant-001",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        authorized_channels=[" Meta ", "google", "meta"],
        currency="usd",
        budget_ceiling=5000.0,
    )
    assert mandate.currency == "USD"
    assert mandate.authorized_channels == ["meta", "google"]

    # Invalid currency length rejected
    with pytest.raises(ValidationError):
        SAllocMandate(
            tenant_id="tenant-alpha",
            task_id="task-bad-curr",
            parent_grant_id="grant-001",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            authorized_channels=["meta"],
            currency="US_DOLLAR",
            budget_ceiling=5000.0,
        )

    # Non-alpha currency code rejected
    with pytest.raises(ValidationError, match="3-letter ISO code"):
        SAllocMandate(
            tenant_id="tenant-alpha",
            task_id="task-bad-curr-num",
            parent_grant_id="grant-001",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            authorized_channels=["meta"],
            currency="123",
            budget_ceiling=5000.0,
        )



def test_s_alloc_mandate_constraint_invariants() -> None:
    """Constraints must bind to authorized channels and not violate budget bounds."""
    # Unauthorized channel constraint
    with pytest.raises(ValidationError, match="unauthorized channel 'tiktok'"):
        SAllocMandate(
            tenant_id="tenant-alpha",
            task_id="task-bad-con",
            parent_grant_id="grant-001",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            authorized_channels=["meta"],
            budget_ceiling=5000.0,
            allocation_constraints=[AllocationConstraint(channel="tiktok", min_spend=100.0)],
        )

    # Min spend exceeds budget ceiling
    with pytest.raises(ValidationError, match="exceeds total budget ceiling"):
        SAllocMandate(
            tenant_id="tenant-alpha",
            task_id="task-min-spend-high",
            parent_grant_id="grant-001",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
            authorized_channels=["meta"],
            budget_ceiling=5000.0,
            allocation_constraints=[AllocationConstraint(channel="meta", min_spend=6000.0)],
        )


# =============================================================================
# 8. Authority Attenuation Verification Tests
# =============================================================================


def test_authority_attenuation_enforced_fail_closed() -> None:
    """Child mandate authority must not exceed parent TaskGrant."""
    now = datetime.now(UTC)
    grant = TaskGrant(
        task_id="task-grant-att",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant-alpha", allowed_channels=["meta", "google"]),
        brand_id="brand-glow",
        objective="propose allocation",
        expires_at=now + timedelta(minutes=30),
        token_budget=4000,
        cts_state={"budget_cap": 10000.0},
    )

    valid_mandate = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-grant-att",
        parent_grant_id=grant.task_id,
        expires_at=now + timedelta(minutes=20),  # Less than grant expiry
        authorized_channels=["meta"],           # Subset of allowed
        budget_ceiling=8000.0,                 # <= 10000.0
        token_quota=2048,                      # <= 4000
    )
    # Valid attenuation passes without error
    valid_mandate.validate_attenuation(grant)

    # 1. Budget expansion fails
    budget_expanded = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-grant-att",
        parent_grant_id=grant.task_id,
        expires_at=now + timedelta(minutes=20),
        authorized_channels=["meta"],
        budget_ceiling=15000.0,  # Exceeds 10000.0
    )
    with pytest.raises(PolicyViolationError, match="exceeds authorized ceiling"):
        budget_expanded.validate_attenuation(grant)

    # 2. Channel expansion fails
    channel_expanded = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-grant-att",
        parent_grant_id=grant.task_id,
        expires_at=now + timedelta(minutes=20),
        authorized_channels=["meta", "tiktok"],  # tiktok not in grant
        budget_ceiling=5000.0,
    )
    with pytest.raises(PolicyViolationError, match="unauthorized channels"):
        channel_expanded.validate_attenuation(grant)

    # 3. Expiry expansion fails
    expiry_expanded = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-grant-att",
        parent_grant_id=grant.task_id,
        expires_at=now + timedelta(hours=2),  # Exceeds grant expiry (30m)
        authorized_channels=["meta"],
        budget_ceiling=5000.0,
    )
    with pytest.raises(PolicyViolationError, match="exceeds parent grant expires_at"):
        expiry_expanded.validate_attenuation(grant)

    # 4. Token quota expansion fails
    token_expanded = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-grant-att",
        parent_grant_id=grant.task_id,
        expires_at=now + timedelta(minutes=20),
        authorized_channels=["meta"],
        budget_ceiling=5000.0,
        token_quota=8000,  # Exceeds 4000
    )
    with pytest.raises(PolicyViolationError, match="exceeds grant token_budget"):
        token_expanded.validate_attenuation(grant)

    # 5. Stale/expired grant fails
    stale_grant = TaskGrant(
        task_id="task-grant-stale",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant-alpha", allowed_channels=["meta"]),
        expires_at=now - timedelta(seconds=10),  # Expired!
    )
    with pytest.raises(PolicyViolationError, match="has expired"):
        valid_mandate.validate_attenuation(stale_grant)


# =============================================================================
# 9. SAllocResult Correlation & Tampering Rejection Tests
# =============================================================================


def test_s_alloc_result_correlation_and_tampering_rejection() -> None:
    """Result correlation validates identities and input SHA-256; rejections are fail-closed."""
    mandate = SAllocMandate(
        tenant_id="tenant-alpha",
        task_id="task-corr-01",
        execution_id="exec-12345",
        stage_attempt_id="att-67890",
        parent_grant_id="grant-001",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        authorized_channels=["meta", "google"],
        budget_ceiling=10000.0,
    )
    input_hash = mandate.compute_input_digest()

    valid_result = SAllocResult(
        execution_id="exec-12345",
        task_id="task-corr-01",
        stage_attempt_id="att-67890",
        tenant_id="tenant-alpha",
        input_sha256=input_hash,
        status=SAllocDomainStatus.OK,
        total_allocated=10000.0,
        budget_residual=0.0,
    )
    # Valid correlation passes
    valid_result.verify_correlation(mandate)

    # Execution ID tampering
    bad_exec = valid_result.model_copy(update={"execution_id": "exec-spoofed"})
    with pytest.raises(ValueError, match="execution_id .* does not match"):
        bad_exec.verify_correlation(mandate)

    # Input hash tampering (replay / modified inputs)
    bad_hash = valid_result.model_copy(update={"input_sha256": "0" * 64})
    with pytest.raises(ValueError, match="input_sha256 .* does not match expected"):
        bad_hash.verify_correlation(mandate)

    # Tenant tampering
    bad_tenant = valid_result.model_copy(update={"tenant_id": "tenant-other"})
    with pytest.raises(ValueError, match="tenant_id .* does not match"):
        bad_tenant.verify_correlation(mandate)


# =============================================================================
# 10. Receipt Integrity & Binding Tests
# =============================================================================


def test_sandbox_receipts_binding_and_digest_immutability() -> None:
    """SandboxExecutionReceipt and SandboxTeardownReceipt bind cleanly without altering result digest."""
    now = datetime.now(UTC)
    exec_receipt = SandboxExecutionReceipt(
        runtime_id="rt-001",
        container_id="c-001",
        image_digest="sha256:11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        runtime_version="1.11.0",
        network_mode="none",
        read_only_root=True,
        effective_cpu_cores=1.0,
        effective_memory_mb=1024,
        effective_pids_limit=1024,
        started_at=now - timedelta(seconds=5),
        terminated_at=now,
        input_digest="a" * 64,
        output_digest="b" * 64,
    )
    teardown_receipt = SandboxTeardownReceipt(
        sandbox_id="sbx-001",
        attempt_id="att-001",
        status="CLEAN",
        workspace_scrubbed=True,
        credentials_revoked=True,
        runtime_destroyed=True,
        destroyed_at=now,
    )

    result_without_receipts = SAllocResult(
        execution_id="exec-rec",
        task_id="task-rec",
        stage_attempt_id="att-rec",
        tenant_id="tenant-alpha",
        input_sha256="c" * 64,
        status=SAllocDomainStatus.OK,
        total_allocated=5000.0,
        budget_residual=0.0,
    )
    digest_before = result_without_receipts.compute_output_digest()

    result_with_receipts = result_without_receipts.model_copy(
        update={
            "execution_receipt": exec_receipt,
            "teardown_receipt": teardown_receipt,
        }
    )
    digest_after = result_with_receipts.compute_output_digest()

    # Digest remains stable because receipts are self-referential / trusted external attestations
    assert digest_before == digest_after
    assert result_with_receipts.execution_receipt is not None
    assert result_with_receipts.teardown_receipt is not None
    assert result_with_receipts.execution_receipt.network_mode == "none"
    assert result_with_receipts.teardown_receipt.status == "CLEAN"


@pytest.mark.asyncio
async def test_invalid_mandate_or_grant_spawns_zero_runtimes() -> None:
    """T01: Invalid mandates or grants fail closed before invoking runtime execution."""
    from unittest.mock import MagicMock
    from app.agents.strategy_engine.strategy import StrategyAgent
    from app.integrations.sandbox.client import SandboxClient
    from app.core.settings import SandboxSettings

    client = SandboxClient(SandboxSettings(endpoint="http://remote-sandbox.internal:8000"))
    mock_sandbox = MagicMock()
    mock_sandbox.shell = MagicMock()
    client._sandbox = mock_sandbox

    w_strat = StrategyAgent(sandbox_client=client)

    # Stale/expired grant
    now = datetime.now(UTC)
    expired_grant = TaskGrant(
        task_id="task-zero-rt-expired",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="tenant-alpha", allowed_channels=["meta"]),
        expires_at=now - timedelta(seconds=30),  # expired!
    )
    with pytest.raises(PolicyViolationError, match="has expired"):
        await w_strat.run(expired_grant, {"budget_ceiling": 5000.0})
    # Sandbox was NEVER contacted -> zero runtimes spawned
    mock_sandbox.shell.exec_command.assert_not_called()

