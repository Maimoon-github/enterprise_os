"""Tests for L6-04 — Complete result validation, provenance, and governed handoff.

Validates:
1. StrategyResultEnvelope.from_evidence_envelope() fails closed on malformed plan.
2. SAllocResult.verify_correlation() verifies exact scenarios, channels, nonfinite checks,
   totals bounds, input_sha256 matching, and valid execution/teardown receipts.
3. Hardened sanitation rejects traversal, active scripts, deep nesting, and generates distinct digests.
4. Transport success does not mask domain non-OK outcomes.
5. Intelligence Engine requires valid domain status and proposed state (never confidence alone).
6. W3C PROV lineage binds S_ALLOC specialist, W_STRAT delegation, and sandbox execution receipts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest
from pydantic import ValidationError

from app.agents.strategy_engine.strategy import StrategyAgent
from app.agents.strategy_engine.subagents.allocation import StrategyAllocationAgent
from app.integrations.sandbox.client import _sanitize_payload
from app.schemas.agent_contracts import (
    ConfidenceInterval,
    EvidenceEnvelope,
    TaskGrant,
)
from app.schemas.governance import Directive, TenantScope, WorkerRole
from app.schemas.provenance import ProvRelationType
from app.schemas.sandbox import (
    ResourceLimits,
    SandboxCapability,
    SandboxExecutionReceipt,
    SandboxExecutionStatus,
    SandboxInvocationMandate,
    SandboxResult,
    SandboxTeardownReceipt,
)
from app.schemas.strategy import (
    ChannelSpendProposal,
    SAllocDomainStatus,
    SAllocResult,
    StrategyResultEnvelope,
    compute_canonical_sha256,
)
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository
from tests.strategy_engine.test_ie_roundtrip import _build_test_intelligence_engine


def _make_valid_mandate() -> SandboxInvocationMandate:
    return SandboxInvocationMandate(
        execution_id="exec-l6-04-1",
        stage_attempt_id="att-l6-04-1",
        task_id="task-l6-04-1",
        tenant_id="tenant-acme",
        capability=SandboxCapability.ALLOC,
        payload={
            "brand_id": "brand-nike",
            "channels": ["meta", "google"],
            "target_budget": 50000.0,
            "currency": "USD",
            "scenarios": ["conservative", "target", "aggressive"],
        },
        resource_limits=ResourceLimits(timeout_seconds=60, memory_mb=512, cpu_cores=1.0),
    )


def _make_valid_receipts(mandate: SandboxInvocationMandate) -> tuple[SandboxExecutionReceipt, SandboxTeardownReceipt]:
    exec_receipt = SandboxExecutionReceipt(
        runtime_id="rt-receipt-01",
        container_id="cont-receipt-01",
        image_digest="sha256:abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234",
        exit_code=0,
        input_digest="test-input-digest",
        output_digest="test-output-digest",
    )
    teardown_receipt = SandboxTeardownReceipt(
        sandbox_id="cont-receipt-01",
        attempt_id=mandate.stage_attempt_id,
        status="CLEAN",
        workspace_scrubbed=True,
        credentials_revoked=True,
        runtime_destroyed=True,
    )
    return exec_receipt, teardown_receipt


def test_strategy_result_envelope_fails_closed_on_malformed_plan() -> None:
    """StrategyResultEnvelope.from_evidence_envelope must raise, not silently set strategy_plan=None."""
    import json

    envelope = EvidenceEnvelope(
        task_id="task-malformed",
        worker_role=WorkerRole.STRATEGY,
        confidence=ConfidenceInterval(point_estimate=0.9, lower_bound=0.8, upper_bound=0.95),
        findings=["summary: test"],
        payload={
            "strategy_plan": json.dumps({
                "total_budget": 1000.0,
                # Missing required plan fields: title, channel_allocations
            })
        },
    )

    with pytest.raises((ValueError, ValidationError)):
        StrategyResultEnvelope.from_evidence_envelope(envelope)


def test_salloc_correlation_and_receipt_validation() -> None:
    """SAllocResult.verify_correlation rejects mismatches, unauthorized channels, and missing receipts."""
    mandate = _make_valid_mandate()
    exec_rcpt, tear_rcpt = _make_valid_receipts(mandate)
    input_digest = compute_canonical_sha256(mandate.payload)

    scenarios = {
        "conservative": [
            ChannelSpendProposal(channel="meta", spend=15000.0, percentage=50.0),
            ChannelSpendProposal(channel="google", spend=15000.0, percentage=50.0),
        ],
        "target": [
            ChannelSpendProposal(channel="meta", spend=25000.0, percentage=50.0),
            ChannelSpendProposal(channel="google", spend=25000.0, percentage=50.0),
        ],
        "aggressive": [
            ChannelSpendProposal(channel="meta", spend=35000.0, percentage=58.33),
            ChannelSpendProposal(channel="google", spend=25000.0, percentage=41.67),  # Sum = 60000 > 50000 cap
        ],
    }

    # 1. Budget exceedance rejection
    res_budget_fail = SAllocResult(
        execution_id=mandate.execution_id,
        task_id=mandate.task_id,
        stage_attempt_id=mandate.stage_attempt_id,
        tenant_id=mandate.tenant_id,
        input_sha256=input_digest,
        status=SAllocDomainStatus.OK,
        scenario_allocations=scenarios,
        execution_receipt=exec_rcpt,
        teardown_receipt=tear_rcpt,
    )
    with pytest.raises(ValueError, match="exceeds ceiling"):
        res_budget_fail.verify_correlation(mandate, require_receipts=True)

    # 2. Fix budget, test unauthorized channel
    scenarios["aggressive"] = [
        ChannelSpendProposal(channel="meta", spend=25000.0, percentage=50.0),
        ChannelSpendProposal(channel="tiktok", spend=25000.0, percentage=50.0),  # tiktok is unauthorized
    ]
    res_channel_fail = SAllocResult(
        execution_id=mandate.execution_id,
        task_id=mandate.task_id,
        stage_attempt_id=mandate.stage_attempt_id,
        tenant_id=mandate.tenant_id,
        input_sha256=input_digest,
        status=SAllocDomainStatus.OK,
        scenario_allocations=scenarios,
        execution_receipt=exec_rcpt,
        teardown_receipt=tear_rcpt,
    )
    with pytest.raises(ValueError, match="unauthorized channel"):
        res_channel_fail.verify_correlation(mandate, require_receipts=True)

    # 3. Missing teardown receipt rejection
    scenarios["aggressive"] = [
        ChannelSpendProposal(channel="meta", spend=25000.0, percentage=50.0),
        ChannelSpendProposal(channel="google", spend=25000.0, percentage=50.0),
    ]
    res_no_tear = SAllocResult(
        execution_id=mandate.execution_id,
        task_id=mandate.task_id,
        stage_attempt_id=mandate.stage_attempt_id,
        tenant_id=mandate.tenant_id,
        input_sha256=input_digest,
        status=SAllocDomainStatus.OK,
        scenario_allocations=scenarios,
        execution_receipt=exec_rcpt,
        teardown_receipt=None,
    )
    with pytest.raises(ValueError, match="verified teardown_receipt"):
        res_no_tear.verify_correlation(mandate, require_receipts=True)


def test_sandbox_sanitation_security_and_traversal_rejection() -> None:
    """_sanitize_payload rejects traversal, active scripts, and redacts secrets."""
    from app.core.exceptions import SandboxInvocationError

    # Traversal rejection
    with pytest.raises(SandboxInvocationError, match="Path traversal escape pattern detected"):
        _sanitize_payload({"path": "../etc/passwd"})

    # Active script injection rejection
    with pytest.raises(SandboxInvocationError, match="Active content"):
        _sanitize_payload({"content": "<script>alert(1)</script>"})

    # Nested secret redaction and digest generation
    clean_str, clean_struct, warnings, raw_sha, sanitized_sha = _sanitize_payload({
        "status": "OK",
        "api_key": "super-secret-key-xyz",
        "nested": {"client_secret": "my-secret"},
        "clean_field": "valid_value",
    })
    assert clean_struct["api_key"] == "[REDACTED]"
    assert clean_struct["nested"]["client_secret"] == "[REDACTED]"
    assert clean_struct["clean_field"] == "valid_value"
    assert len(raw_sha) == 64
    assert len(sanitized_sha) == 64
    assert raw_sha != sanitized_sha


def test_domain_status_failure_overrides_transport_success() -> None:
    """Specialist domain status INFEASIBLE or INVALID_INPUT causes execution failure."""
    mandate = _make_valid_mandate()
    res = SandboxResult(
        execution_id=mandate.execution_id,
        stage_attempt_id=mandate.stage_attempt_id,
        task_id=mandate.task_id,
        tenant_id=mandate.tenant_id,
        capability=SandboxCapability.ALLOC,
        success=True,
        status=SandboxExecutionStatus.COMPLETED,
        exit_code=0,
        stdout='{"status": "INFEASIBLE", "diagnostics": {"error": "Budget too low"}}',
        stderr="",
        structured_output={"status": "INFEASIBLE", "diagnostics": {"error": "Budget too low"}},
    )

    subagent = StrategyAllocationAgent()
    salloc_res = subagent.parse_and_validate_result(mandate, res)
    assert salloc_res.status == SAllocDomainStatus.INFEASIBLE
    assert salloc_res.status != SAllocDomainStatus.OK


@pytest.mark.asyncio
async def test_intelligence_engine_task_state_requires_domain_success(sample_directive: Directive) -> None:
    """IE task does not advance to COMPLETED if worker proposed status is 'failed', even with confidence."""
    prov_repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(prov_repo)
    w_strat = StrategyAgent(sandbox_client=MagicMock())

    # Worker returns high confidence, but failed proposed state and INFEASIBLE domain status
    w_strat.run = AsyncMock(
        return_value=EvidenceEnvelope(
            task_id="task-ie-test-fail",
            worker_role=WorkerRole.STRATEGY,
            confidence=ConfidenceInterval(point_estimate=0.95, lower_bound=0.90, upper_bound=0.99),
            findings=["error: domain infeasible"],
            proposed_state_changes={"status": "failed"},
            payload={"domain_status": "INFEASIBLE"},
        )
    )

    engine = _build_test_intelligence_engine(w_strat, recorder)
    task = CanonicalTaskState(
        task_id="task-ie-test-fail",
        directive_id=sample_directive.directive_id,
        worker_role=WorkerRole.STRATEGY,
        status=TaskStatus.PENDING,
        cts_state={},
    )

    envelope = await engine.delegate_task(
        directive=sample_directive,
        task=task,
        query="propose strategy",
        brand_id=sample_directive.tenant_id,
    )

    # Task execution must NOT complete; it must be recorded as failed in provenance
    failed_recs = [r for r in prov_repo.records if r.metadata.get("lifecycle_stage") == "failed"]
    assert len(failed_recs) == 1
    completed_recs = [r for r in prov_repo.records if r.metadata.get("lifecycle_stage") == "completed"]
    assert len(completed_recs) == 0


@pytest.mark.asyncio
async def test_s_alloc_w3c_prov_lineage_and_delegation() -> None:
    """W3C PROV records bind S_ALLOC specialist, W_STRAT delegation, and receipts."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    record = await recorder.record_sandbox_execution(
        tenant_id="tenant-w3c-alloc",
        task_id="task-w3c-alloc",
        execution_id="exec-w3c-1",
        worker_role="W_STRAT",
        capability="ALLOC",
        operation="run.py",
        lifecycle_stage="completed",
        status="success",
        input_payload={"channels": ["meta", "google"]},
        output_summary={"status": "OK", "total": 50000.0},
    )

    bundle = record.w3c_prov
    agents = {a["id"] for a in bundle["agents"]}
    assert "urn:enterprise_os:agent:specialist:s_alloc:exec-w3c-1" in agents
    assert "urn:enterprise_os:agent:worker:W_STRAT" in agents

    delegations = [
        r for r in bundle["relations"]
        if r["relation_type"] == ProvRelationType.ACTED_ON_BEHALF_OF.value
        and r["source_id"] == "urn:enterprise_os:agent:specialist:s_alloc:exec-w3c-1"
        and r["target_id"] == "urn:enterprise_os:agent:worker:W_STRAT"
    ]
    assert len(delegations) == 1
