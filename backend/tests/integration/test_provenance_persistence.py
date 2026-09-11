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