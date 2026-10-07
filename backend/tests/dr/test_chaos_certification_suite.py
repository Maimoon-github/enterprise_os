"""Track 4 Chaos Certification Test Suite.

Proves the 8-scenario failure injection matrix in exact order:
1. PostgreSQL termination during an active directive.
2. Provisioner termination during a specialist attempt.
3. UDS disconnect mid-request.
4. Specialist termination after work but before receipt sealing.
5. Host reboot with active leases/tasks.
6. WAL/archive storage exhaustion or unavailability.
7. Corrupted/missing WAL segment with mandatory fail-closed recovery.
8. Outbound actuation crash at the acknowledgement boundary.

Governing Track 4 Assertion:
"For every injected failure, Enterprise OS either resumes safely or fails closed.
No failure may cause duplicate external actuation, unauthorized continuation,
incorrect terminal CTS state, lost provenance, cross-tenant leakage, replay acceptance,
stale lease execution, or silent data loss."
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest

from app.disaster_recovery.chaos_engine import (
    GOVERNING_TRACK4_ASSERTION,
    ChaosCertificationSuiteReceipt,
    ChaosScenarioId,
    ChaosScenarioResult,
    EnterpriseOSChaosEngine,
)

PRIMARY_DSN = os.getenv(
    "ENTERPRISE_OS_PRIMARY_DSN",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/governed_backend",
)


@pytest.fixture
def chaos_engine(tmp_path: Path) -> Generator[EnterpriseOSChaosEngine, None, None]:
    engine = EnterpriseOSChaosEngine(primary_dsn=PRIMARY_DSN, work_dir=tmp_path / "chaos_run")
    yield engine
    engine.cleanup()


# =============================================================================
# SCENARIO 1: PostgreSQL termination during an active directive
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_1_postgres_termination(chaos_engine: EnterpriseOSChaosEngine) -> None:
    """Verify PostgreSQL aborts uncommitted directive transactions cleanly without corrupted state."""
    result = await chaos_engine.execute_scenario_1_postgres_termination()
    assert result.passed is True, f"Scenario 1 failed: {result.observed_behavior}"
    assert result.governing_assertion_upheld is True
    assert result.order == 1
    assert result.scenario_id == ChaosScenarioId.SCENARIO_1_POSTGRES_TERMINATION
    assert result.evidence.get("post_reconnect_status") == "PENDING"
    assert result.evidence.get("post_reconnect_version") == 1


# =============================================================================
# SCENARIO 2: Provisioner termination during a specialist attempt
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_2_provisioner_termination(chaos_engine: EnterpriseOSChaosEngine) -> None:
    """Verify sudden provisioner crash cleans up staging dirs and cgroups without orphan processes."""
    result = await chaos_engine.execute_scenario_2_provisioner_termination()
    assert result.passed is True, f"Scenario 2 failed: {result.observed_behavior}"
    assert result.governing_assertion_upheld is True
    assert result.order == 2
    assert result.scenario_id == ChaosScenarioId.SCENARIO_2_PROVISIONER_TERMINATION
    assert result.evidence.get("staging_dir_exists_after_cleanup") is False
    assert result.evidence.get("cgroup_destroyed") is True


# =============================================================================
# SCENARIO 3: UDS disconnect mid-request
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_3_uds_disconnect(chaos_engine: EnterpriseOSChaosEngine) -> None:
    """Verify UDS server handles broken pipe gracefully, enforces 0660 mode, and stays operational."""
    result = await chaos_engine.execute_scenario_3_uds_disconnect()
    assert result.passed is True, f"Scenario 3 failed: {result.observed_behavior}"
    assert result.governing_assertion_upheld is True
    assert result.order == 3
    assert result.scenario_id == ChaosScenarioId.SCENARIO_3_UDS_DISCONNECT
    assert result.evidence.get("socket_mode_octal") == oct(0o660)


# =============================================================================
# SCENARIO 4: Specialist termination after work but before receipt sealing
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_4_specialist_termination_before_seal(
    chaos_engine: EnterpriseOSChaosEngine,
) -> None:
    """Verify missing receipt prevents false terminal success (COMPLETED); fails closed safely."""
    result = await chaos_engine.execute_scenario_4_specialist_termination_before_seal()
    assert result.passed is True, f"Scenario 4 failed: {result.observed_behavior}"
    assert result.governing_assertion_upheld is True
    assert result.order == 4
    assert result.scenario_id == ChaosScenarioId.SCENARIO_4_SPECIALIST_TERMINATION_BEFORE_SEAL
    assert result.evidence.get("final_task_status") == "FAILED"
    assert result.evidence.get("final_task_status") != "COMPLETED"


# =============================================================================
# SCENARIO 5: Host reboot with active leases/tasks
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_5_host_reboot_active_leases(chaos_engine: EnterpriseOSChaosEngine) -> None:
    """Verify fencing tokens block stale lease execution across host reboot with zero duplication."""
    result = await chaos_engine.execute_scenario_5_host_reboot_active_leases()
    assert result.passed is True, f"Scenario 5 failed: {result.observed_behavior}"
    assert result.governing_assertion_upheld is True
    assert result.order == 5
    assert result.scenario_id == ChaosScenarioId.SCENARIO_5_HOST_REBOOT_ACTIVE_LEASES
    assert result.evidence.get("worker_a_claimed_generation") == 1
    assert result.evidence.get("worker_b_claimed_generation") == 2
    assert "stale_commit_rejection_error" in result.evidence
    assert result.evidence.get("worker_b_final_status") == "done"


# =============================================================================
# SCENARIO 6: WAL/archive storage exhaustion or unavailability
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_6_wal_storage_exhaustion(chaos_engine: EnterpriseOSChaosEngine) -> None:
    """Verify WAL archiving fails closed on storage unavailability; flushes with zero gaps upon recovery."""
    result = await chaos_engine.execute_scenario_6_wal_storage_exhaustion()
    assert result.passed is True, f"Scenario 6 failed: {result.observed_behavior}"
    assert result.governing_assertion_upheld is True
    assert result.order == 6
    assert result.scenario_id == ChaosScenarioId.SCENARIO_6_WAL_STORAGE_EXHAUSTION
    assert result.evidence.get("vault_integrity", {}).get("healthy") is True
    assert result.evidence.get("vault_integrity", {}).get("segments_count") == 2


# =============================================================================
# SCENARIO 7: Corrupted/missing WAL segment with mandatory fail-closed recovery
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_7_corrupt_wal_fail_closed(chaos_engine: EnterpriseOSChaosEngine) -> None:
    """Verify bit-rot tamper and sequence gaps halt recovery immediately; mandatory fail-closed."""
    result = await chaos_engine.execute_scenario_7_corrupt_wal_fail_closed()
    assert result.passed is True, f"Scenario 7 failed: {result.observed_behavior}"
    assert result.governing_assertion_upheld is True
    assert result.order == 7
    assert result.scenario_id == ChaosScenarioId.SCENARIO_7_CORRUPT_WAL_FAIL_CLOSED
    assert "checksum_verification_error" in result.evidence
    assert result.evidence.get("sequence_gap_check", {}).get("status") == "SEGMENT_SEQUENCE_GAP"


# =============================================================================
# SCENARIO 8: Outbound actuation crash at the acknowledgement boundary
# =============================================================================
@pytest.mark.asyncio
async def test_scenario_8_outbound_actuation_ack_boundary(
    chaos_engine: EnterpriseOSChaosEngine,
) -> None:
    """Verify unacknowledged crash at acknowledgement boundary reconciles without duplicate actuation.

    Sequence:
    HITL approved -> signed Outbound MCP request sent -> external provider accepts mutation
    -> backend/proxy dies before acknowledgement is persisted -> system restarts/retries
    -> prove that the system does NOT create the campaign/order/post/change twice.
    """
    result = await chaos_engine.execute_scenario_8_outbound_actuation_ack_boundary()
    assert result.passed is True, f"Scenario 8 failed: {result.observed_behavior}"
    assert result.governing_assertion_upheld is True
    assert result.order == 8
    assert result.scenario_id == ChaosScenarioId.SCENARIO_8_OUTBOUND_ACTUATION_ACK_BOUNDARY

    # Governing distributed-systems invariant: Exactly 1 external mutation
    assert result.evidence.get("total_provider_mutation_calls") == 1, (
        f"Duplicate external actuation detected! Count: {result.evidence.get('total_provider_mutation_calls')}"
    )
    assert result.evidence.get("provider_reconcile_queries", 0) >= 1
    assert result.evidence.get("retry_result_status") == "published"

    # Lineage complete
    activities = result.evidence.get("provenance_activities", [])
    assert "outbound_dispatch_intent_persisted" in activities
    assert "outbound_meta_ack_boundary_crash" in activities
    assert "outbound_meta_reconciliation_succeeded" in activities
    assert "outbound_meta_deployment_executed" in activities


# =============================================================================
# SUITE TEST: Complete 8-Scenario Sequential Chaos Certification
# =============================================================================
@pytest.mark.asyncio
async def test_full_unified_chaos_certification_suite(
    chaos_engine: EnterpriseOSChaosEngine,
) -> None:
    """Execute the full 8-scenario Chaos Certification Suite end-to-end and certify governing invariant."""
    receipt: ChaosCertificationSuiteReceipt = await chaos_engine.run_full_certification_suite()

    assert receipt.total_scenarios == 8
    assert receipt.passed_scenarios == 8
    assert receipt.verdict == "CERTIFIED"
    assert receipt.governing_assertion_upheld is True
    assert receipt.governing_assertion == GOVERNING_TRACK4_ASSERTION

    # Verify all 8 scenarios executed in precise order 1 to 8
    for idx, scen_res in enumerate(receipt.scenario_results, start=1):
        assert scen_res.order == idx
        assert scen_res.passed is True
        assert scen_res.governing_assertion_upheld is True
