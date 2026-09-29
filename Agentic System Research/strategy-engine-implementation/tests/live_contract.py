"""Contract a deployment-owned integration fixture must implement.

Not supplied: the actual Enterprise OS source, controller, keys and ledger. This
module does not claim to provision or harden them. Do not use tests.support here.
"""
from typing import Protocol, Literal
from app.schemas.strategy import Contract, Digest, EvidenceEnvelope, TaskGrant
from app.agents.strategy_engine.strategy import StrategyEngine


class IsolationReport(Contract):
    runtime: Literal['kata', 'firecracker']
    ipv4_egress_blocked: Literal[True]
    ipv6_egress_blocked: Literal[True]
    dns_blocked: Literal[True]
    metadata_access_blocked: Literal[True]
    internal_services_blocked: Literal[True]
    worker_direct_network_blocked: Literal[True]
    worker_direct_sdk_blocked: Literal[True]
    tmpfs_verified: Literal[True]
    root_read_only_verified: Literal[True]
    restricted_syscalls_blocked: Literal[True]
    cross_instance_memory_inaccessible: Literal[True]
    secrets_absent: Literal[True]
    timeout_teardown_verified: Literal[True]
    cancellation_teardown_verified: Literal[True]
    cgroup_memory_limit_verified: Literal[True]
    trace_hash: Digest


class DurableLedgerReport(Contract):
    replay_deduplicated: Literal[True]
    conflicting_replay_rejected: Literal[True]
    concurrent_append_serialized: Literal[True]
    restart_persistence_verified: Literal[True]
    mutation_denied: Literal[True]
    complete_payload_and_prov_retained: Literal[True]
    trace_hash: Digest


class LiveEnvironment(Protocol):
    worker: StrategyEngine
    grant: TaskGrant
    async def verify_stored_evidence(self, envelope: EvidenceEnvelope) -> bool: ...
    async def probe_isolation(self) -> IsolationReport:
        """Run active probes + inspect host runtime; retain raw audit evidence."""
        ...
    async def verify_durable_ledger(self) -> DurableLedgerReport: ...
    async def close(self) -> None: ...
