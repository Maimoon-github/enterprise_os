"""Tests for Strategy-specific W3C PROV audit lineage (T5).

Verifies W_STRAT activity/agent/entities, prov:used, prov:wasAssociatedWith,
prov:wasGeneratedBy, canonical SHA-256 digests, sandbox execution linkage,
append-only hash chain integrity, idempotency, and absence of raw secrets.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.agent_contracts import ConfidenceInterval, EvidenceEnvelope, TaskGrant
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.provenance import ProvRelationType
from app.schemas.strategy import ChannelSpendProposal, StrategyResultEnvelope
from app.services.provenance import ProvenanceRecorder, compute_canonical_sha256
from tests.conftest import FakeProvenanceRepository


# =============================================================================
# 1. Canonical SHA-256 Determinism & Secret Sanitization
# =============================================================================


def test_canonical_sha256_determinism_and_sorting() -> None:
    """compute_canonical_sha256 produces identical digests irrespective of key order."""
    dict_a = {"task_id": "t-1", "budget": 10000.0, "channels": ["meta", "google"]}
    dict_b = {"channels": ["meta", "google"], "budget": 10000.0, "task_id": "t-1"}

    hash_a = compute_canonical_sha256(dict_a)
    hash_b = compute_canonical_sha256(dict_b)
    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_canonical_sha256_redacts_secrets_and_hidden_reasoning() -> None:
    """Credentials, tokens, and hidden reasoning are redacted before hashing."""
    data_with_secret = {
        "task_id": "t-sec",
        "api_key": "sk-live-secret-key-12345678",
        "hidden_reasoning": "do not expose internal CoT",
        "budget": 5000.0,
    }
    digest = compute_canonical_sha256(data_with_secret)
    assert digest is not None

    data_already_redacted = {
        "task_id": "t-sec",
        "api_key": "[REDACTED]",
        "hidden_reasoning": "[REDACTED]",
        "budget": 5000.0,
    }
    assert digest == compute_canonical_sha256(data_already_redacted)


# =============================================================================
# 2. Strategy Worker W3C PROV Bundle Relations & Digests
# =============================================================================


@pytest.mark.asyncio
async def test_strategy_worker_w3c_prov_bundle_relations() -> None:
    """build_worker_w3c_prov for W_STRAT generates all required W3C entities and relations."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    grant = TaskGrant(
        task_id="task-strat-prov-01",
        worker_role=WorkerRole.STRATEGY,
        tenant_scope=TenantScope(tenant_id="acme", allowed_channels=["meta", "google"]),
        brand_id="brand-acme",
        objective="propose allocation",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    envelope = StrategyResultEnvelope(
        task_id="task-strat-prov-01",
        worker_role=WorkerRole.STRATEGY,
        confidence=ConfidenceInterval(point_estimate=0.85, lower_bound=0.70, upper_bound=0.95),
        evidence=["Blended ROAS: 4.0x"],
        findings=["Optimal media plan"],
        provenance={"sandbox_execution_id": "sb-exec-999"},
    )

    record = await recorder.record_worker_execution(
        tenant_id="acme",
        task_id=grant.task_id,
        worker_role=WorkerRole.STRATEGY,
        lifecycle_stage="completed",
        input_data=grant,
        output_data=envelope,
        sandbox_execution_id="sb-exec-999",
        duration_ms=125.0,
    )

    assert record.activity == "worker_execution"
    assert record.agent == "W_STRAT"
    assert record.entity_id == grant.task_id

    bundle = record.w3c_prov
    assert bundle is not None

    # Verify entities
    entities_by_id = {e["id"]: e for e in bundle["entities"]}
    input_entity_id = f"urn:enterprise_os:entity:task_grant:{grant.task_id}"
    output_entity_id = f"urn:enterprise_os:entity:worker_result:{grant.task_id}:completed"
    task_entity_id = f"urn:enterprise_os:entity:task:{grant.task_id}"

    assert input_entity_id in entities_by_id
    assert output_entity_id in entities_by_id
    assert task_entity_id in entities_by_id

    # Verify SHA-256 hashes
    assert entities_by_id[input_entity_id]["value_hash"] == compute_canonical_sha256(grant)
    assert entities_by_id[output_entity_id]["value_hash"] == compute_canonical_sha256(envelope)

    # Verify relations
    relation_types = [r["relation_type"] for r in bundle["relations"]]
    assert ProvRelationType.WAS_ASSOCIATED_WITH.value in relation_types
    assert ProvRelationType.USED.value in relation_types
    assert ProvRelationType.WAS_GENERATED_BY.value in relation_types
    assert ProvRelationType.WAS_ATTRIBUTED_TO.value in relation_types
    assert ProvRelationType.WAS_DERIVED_FROM.value in relation_types

    # Linkage to sandbox execution ID
    assert record.metadata.get("sandbox_execution_id") == "sb-exec-999"
    act = bundle["activities"][0]
    assert act["attributes"].get("sandbox_execution_id") == "sb-exec-999"


# =============================================================================
# 3. Hash-Chain Integrity, Idempotency & Failure Lifecycle
# =============================================================================


@pytest.mark.asyncio
async def test_strategy_provenance_idempotency_and_chain_verification() -> None:
    """Appending duplicate worker record is idempotent; verify_chain remains unbroken."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    rec1 = await recorder.record_worker_execution(
        tenant_id="tenant_x",
        task_id="task-idem-1",
        worker_role=WorkerRole.STRATEGY,
        lifecycle_stage="completed",
        output_data={"result": "ok"},
    )
    assert len(repo.records) == 1

    # Idempotent re-append
    rec2 = await recorder.record_worker_execution(
        tenant_id="tenant_x",
        task_id="task-idem-1",
        worker_role=WorkerRole.STRATEGY,
        lifecycle_stage="completed",
        output_data={"result": "ok"},
    )
    assert rec2.record_id == rec1.record_id
    assert len(repo.records) == 1
    assert await recorder.verify_chain("tenant_x") is True


@pytest.mark.asyncio
async def test_strategy_failure_lifecycle_never_emits_completed() -> None:
    """Failed execution records lifecycle_stage='failed' and never 'completed'."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    rec = await recorder.record_worker_execution(
        tenant_id="tenant_fail",
        task_id="task-fail-01",
        worker_role=WorkerRole.STRATEGY,
        lifecycle_stage="failed",
        output_data={"error": "Sandbox timed out after 120s"},
    )
    assert rec.metadata["lifecycle_stage"] == "failed"
    assert rec.activity == "worker_execution"

    completed_recs = [
        r for r in repo.records if r.metadata.get("lifecycle_stage") == "completed"
    ]
    assert len(completed_recs) == 0
