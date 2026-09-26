"""Verifies required control-plane and execution audit lineage."""

from __future__ import annotations

import pytest

from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository


@pytest.mark.asyncio
async def test_provenance_chain_is_hash_linked_in_order() -> None:
    recorder = ProvenanceRecorder(FakeProvenanceRepository())

    await recorder.record(
        tenant_id="acme", entity_id="directive-1", activity="directive_accepted", agent="api"
    )
    await recorder.record(
        tenant_id="acme", entity_id="task-1", activity="worker_execution", agent="W_LEARN"
    )
    await recorder.record(
        tenant_id="acme", entity_id="dispatch-1", activity="actuation", agent="mcp_host"
    )

    chain = await recorder.audit_chain("acme")
    assert len(chain) == 3
    assert chain[0].prev_record_hash is None
    assert chain[1].prev_record_hash == chain[0].record_hash
    assert chain[2].prev_record_hash == chain[1].record_hash


@pytest.mark.asyncio
async def test_provenance_chain_verification_succeeds_when_intact() -> None:
    recorder = ProvenanceRecorder(FakeProvenanceRepository())
    await recorder.record(tenant_id="acme", entity_id="e1", activity="a1", agent="agent1")
    await recorder.record(tenant_id="acme", entity_id="e2", activity="a2", agent="agent2")

    assert await recorder.verify_chain("acme") is True


@pytest.mark.asyncio
async def test_provenance_chain_verification_fails_when_tampered() -> None:
    repository = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repository)
    await recorder.record(tenant_id="acme", entity_id="e1", activity="a1", agent="agent1")
    await recorder.record(tenant_id="acme", entity_id="e2", activity="a2", agent="agent2")

    chain = await repository.chain("acme")
    tampered = chain[0].model_copy(update={"activity": "tampered_activity"})
    repository._chains["acme"][0] = tampered  # simulate retroactive tampering

    assert repository.verify(await repository.chain("acme")) is False


@pytest.mark.asyncio
async def test_tenants_have_independent_chains() -> None:
    recorder = ProvenanceRecorder(FakeProvenanceRepository())
    await recorder.record(tenant_id="acme", entity_id="e1", activity="a1", agent="agent1")
    await recorder.record(tenant_id="globex", entity_id="e2", activity="a2", agent="agent2")

    acme_chain = await recorder.audit_chain("acme")
    globex_chain = await recorder.audit_chain("globex")

    assert len(acme_chain) == 1
    assert len(globex_chain) == 1
    assert acme_chain[0].prev_record_hash is None
    assert globex_chain[0].prev_record_hash is None


# ---------------------------------------------------------------------------
# Sandbox Execution Audit -> W3C PROV Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sandbox_execution_produces_w3c_prov_audit_events() -> None:
    """Sandbox execution generates compliant W3C PROV records for lifecycle stages."""
    from app.integrations.sandbox.client import SandboxClient
    from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate
    from app.schemas.provenance import ProvRelationType

    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)
    client = SandboxClient(provenance_recorder=recorder)

    mandate = SandboxInvocationMandate(
        execution_id="exec-prov-w3c-1",
        task_id="task-prov-w3c-1",
        worker_role="W_DEV",
        tenant_id="acme",
        capability=SandboxCapability.CODE,
        operation="generate_diff",
        payload={"code": "x = 42"},
    )

    result = await client.invoke(mandate)
    assert result.success is True

    chain = await recorder.audit_chain("acme")
    assert len(chain) == 2  # started and completed stages

    start_rec, complete_rec = chain[0], chain[1]

    # Verify chain integrity
    assert start_rec.prev_record_hash is None
    assert complete_rec.prev_record_hash == start_rec.record_hash
    assert await recorder.verify_chain("acme") is True

    # Verify W3C PROV graph on completed record
    w3c = complete_rec.w3c_prov
    assert len(w3c["activities"]) >= 1
    assert len(w3c["agents"]) >= 3  # Worker, Sandbox Controller, Orchestrator
    assert len(w3c["entities"]) >= 2  # Mandate, Task, Result, etc.
    assert len(w3c["relations"]) >= 4

    rel_types = {r["relation_type"] for r in w3c["relations"]}
    assert ProvRelationType.WAS_ASSOCIATED_WITH.value in rel_types
    assert ProvRelationType.USED.value in rel_types
    assert ProvRelationType.WAS_GENERATED_BY.value in rel_types
    assert ProvRelationType.ACTED_ON_BEHALF_OF.value in rel_types

    # Verify agent identities
    agent_ids = [a["id"] for a in w3c["agents"]]
    assert "urn:enterprise_os:agent:worker:W_DEV" in agent_ids
    assert "urn:enterprise_os:agent:sandbox_controller:aio-sandbox:v1.11.0" in agent_ids


@pytest.mark.asyncio
async def test_sandbox_audit_captures_failure_and_timeout() -> None:
    """Execution failure and timeout are recorded with exit codes and error metadata."""
    import time
    from unittest.mock import patch
    from app.integrations.sandbox.client import SandboxClient
    from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate

    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)
    client = SandboxClient(provenance_recorder=recorder)

    # 1. Failure Case
    fail_mandate = SandboxInvocationMandate(
        execution_id="exec-fail-audit",
        task_id="task-fail-audit",
        worker_role="W_DEV",
        tenant_id="acme",
        capability=SandboxCapability.CODE,
        operation="generate_diff",
        payload={"code": "crash"},
    )
    with patch.object(client, "_execute_in_isolated_runtime", side_effect=RuntimeError("Syntax Bomb")):
        result = await client.invoke(fail_mandate)
        assert result.success is False

    chain = await recorder.audit_chain("acme")
    fail_record = chain[-1]
    assert fail_record.metadata["lifecycle_stage"] == "failed"
    assert fail_record.metadata["status"] == "failed"
    assert fail_record.metadata["exit_code"] == 1
    assert "Syntax Bomb" in fail_record.metadata["error_details"]

    # 2. Timeout Case
    timeout_mandate = SandboxInvocationMandate(
        execution_id="exec-timeout-audit",
        task_id="task-timeout-audit",
        worker_role="W_DEV",
        tenant_id="acme",
        capability=SandboxCapability.CODE,
        operation="generate_diff",
        payload={"code": "infinite_loop"},
        timeout_seconds=1,
    )

    def slow_exec(*args, **kwargs):
        time.sleep(2)
        return {}

    with patch.object(client, "_execute_in_isolated_runtime", side_effect=slow_exec):
        t_result = await client.invoke(timeout_mandate)
        assert t_result.success is False

    chain = await recorder.audit_chain("acme")
    timeout_record = chain[-1]
    assert timeout_record.metadata["lifecycle_stage"] == "timed_out"
    assert timeout_record.metadata["status"] == "timeout"
    assert timeout_record.metadata["exit_code"] == -1
    assert "timed out" in timeout_record.metadata["error_details"]

    # Entire chain is unbroken
    assert await recorder.verify_chain("acme") is True


@pytest.mark.asyncio
async def test_sandbox_audit_captures_cgroup_and_resource_metrics() -> None:
    """Resource limits and observation metrics are bound in the audit metadata."""
    from app.integrations.sandbox.client import SandboxClient
    from app.schemas.sandbox import ResourceLimits, SandboxCapability, SandboxInvocationMandate
    from tests.conftest import create_mock_remote_sandbox

    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)
    client = create_mock_remote_sandbox(provenance_recorder=recorder)

    mandate = SandboxInvocationMandate(
        execution_id="exec-metrics-audit",
        task_id="task-metrics-audit",
        worker_role="W_STRAT",
        tenant_id="acme",
        capability=SandboxCapability.ALLOC,
        operation="optimize_budget",
        payload={"budget": "5000"},
        resource_limits=ResourceLimits(memory_mb=2048, cpu_cores=2.0, timeout_seconds=180),
    )

    result = await client.invoke(mandate)
    assert result.success is True

    chain = await recorder.audit_chain("acme")
    complete_rec = chain[-1]
    resources = complete_rec.metadata["resources"]
    assert resources["cpu_cores_allocated"] == 2.0
    assert resources["memory_ceiling_mb"] == 2048
    assert resources["timeout_seconds_limit"] == 180


@pytest.mark.asyncio
async def test_sandbox_audit_idempotent_on_duplicate_events() -> None:
    """Duplicate/replayed audit events return existing records and prevent chain corruption."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    rec1 = await recorder.record_sandbox_execution(
        tenant_id="acme",
        task_id="task-idemp",
        execution_id="exec-idemp",
        worker_role="W_DEV",
        capability="S_CODE",
        operation="lint",
        lifecycle_stage="started",
        status="running",
    )

    # Replay identical event
    rec2 = await recorder.record_sandbox_execution(
        tenant_id="acme",
        task_id="task-idemp",
        execution_id="exec-idemp",
        worker_role="W_DEV",
        capability="S_CODE",
        operation="lint",
        lifecycle_stage="started",
        status="running",
    )

    assert rec1.record_id == rec2.record_id
    assert rec1.record_hash == rec2.record_hash

    chain = await recorder.audit_chain("acme")
    assert len(chain) == 1
    assert await recorder.verify_chain("acme") is True


@pytest.mark.asyncio
async def test_sandbox_audit_tamper_evident_verification() -> None:
    """Modifying metadata or W3C PROV graph retroactively invalidates hash chain verification."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    await recorder.record_sandbox_execution(
        tenant_id="acme",
        task_id="task-tamper",
        execution_id="exec-tamper",
        worker_role="W_DEV",
        capability="S_CODE",
        operation="lint",
        lifecycle_stage="started",
        status="running",
    )
    await recorder.record_sandbox_execution(
        tenant_id="acme",
        task_id="task-tamper",
        execution_id="exec-tamper",
        worker_role="W_DEV",
        capability="S_CODE",
        operation="lint",
        lifecycle_stage="completed",
        status="completed",
    )

    assert await recorder.verify_chain("acme") is True

    # Tamper with metadata inside first record
    chain = await repo.chain("acme")
    chain[0].metadata["status"] = "tampered_status"
    assert repo.verify(chain) is False


@pytest.mark.asyncio
async def test_sandbox_audit_fail_closed_on_persistence_failure() -> None:
    """When audit persistence fails, execution fails closed immediately."""
    from unittest.mock import patch
    from app.core.exceptions import SandboxInvocationError
    from app.integrations.sandbox.client import SandboxClient
    from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate

    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)
    client = SandboxClient(provenance_recorder=recorder)

    mandate = SandboxInvocationMandate(
        execution_id="exec-persist-fail",
        task_id="task-persist-fail",
        worker_role="W_DEV",
        tenant_id="acme",
        capability=SandboxCapability.CODE,
        operation="generate_diff",
        payload={"code": "pass"},
    )

    with patch.object(repo, "append", side_effect=IOError("Disk storage corrupted")):
        with pytest.raises(SandboxInvocationError, match="Audit persistence failure"):
            await client.invoke(mandate)


@pytest.mark.asyncio
async def test_sandbox_audit_redacts_secrets() -> None:
    """Sensitive keys, tokens, and bearer credentials are redacted from audit metadata."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    rec = await recorder.record_sandbox_execution(
        tenant_id="acme",
        task_id="task-redact",
        execution_id="exec-redact",
        worker_role="W_DEV",
        capability="S_CODE",
        operation="execute",
        lifecycle_stage="completed",
        status="completed",
        command="curl -H 'Authorization: Bearer supersecrettoken999'",
        error_details="Failed with api_key=secretkey123456 in trace",
        output_summary={"debug": "password=mypassword999"},
    )

    meta = rec.metadata
    assert "supersecrettoken999" not in meta["command"]
    assert "[REDACTED]" in meta["command"]
    assert "secretkey123456" not in meta["error_details"]
    assert "[REDACTED]" in meta["error_details"]


@pytest.mark.asyncio
async def test_end_to_end_lineage_reconstruction() -> None:
    """A sandbox execution can be reconstructed end-to-end from provenance records alone."""
    from app.integrations.sandbox.client import SandboxClient
    from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate

    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)
    client = SandboxClient(provenance_recorder=recorder)

    mandate = SandboxInvocationMandate(
        execution_id="exec-reconstruct-1",
        task_id="task-reconstruct-1",
        worker_role="W_DEV",
        tenant_id="acme",
        capability=SandboxCapability.CODE,
        operation="generate_diff",
        payload={"code": "return 1"},
    )

    result = await client.invoke(mandate)
    assert result.success is True

    lineage = await recorder.reconstruct_lineage("acme", "exec-reconstruct-1")
    assert lineage["execution_id"] == "exec-reconstruct-1"
    assert lineage["task_id"] == "task-reconstruct-1"
    assert lineage["worker_role"] == "W_DEV"
    assert lineage["capability"] == "S_CODE"
    assert lineage["operation"] == "generate_diff"
    assert lineage["status"] == "completed"
    assert lineage["lifecycle_stages"] == ["started", "completed"]
    assert lineage["is_chain_verified"] is True
    assert "urn:enterprise_os:activity:sandbox_execution:exec-reconstruct-1:completed" in lineage["w3c_prov"]["activities"][0]["id"]