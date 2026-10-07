"""Explicit RPO/RTO Targets, Metrics, and Invariants for Enterprise OS Disaster Recovery.

Codifies the formal Disaster Recovery targets for all 8 architectural domains:
1. PostgreSQL (Primary relational & vector state)
2. CTS (Canonical Task State machine)
3. Provenance (W3C PROV cryptographic hash-chained audit ledger)
4. Replay State (Specialist & provisioner execution deduplication)
5. Institutional Memory (Promoted tenant brand knowledge & heuristics)
6. Operational Telemetry (Omnichannel events, receipts, and work items)
7. Provisioner Runtime State (Execution leases, cgroups, and staging scopes)
8. Release Artifacts (Cryptographic digests, SBOM, SLSA builder attestations)

The Governing Invariant:
Failure may delay work, but must never create unauthorized actuation,
duplicate irreversible action, lost audit lineage, cross-tenant leakage,
false terminal CTS state, or silent data loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DRCriticality(StrEnum):
    """Business criticality tier for recovery time and point objectives."""

    CRITICAL = "CRITICAL"  # Zero loss tolerated (RPO = 0s)
    HIGH = "HIGH"          # Sub-second to few-second loss tolerated
    STANDARD = "STANDARD"  # Up to 5s-15s loss tolerated


class SubsystemDomain(StrEnum):
    """Architectural subsystems subject to Disaster Recovery certification."""

    POSTGRESQL = "postgresql"
    CTS = "cts"
    PROVENANCE = "provenance"
    REPLAY_STATE = "replay_state"
    INSTITUTIONAL_MEMORY = "institutional_memory"
    TELEMETRY = "telemetry"
    PROVISIONER_RUNTIME = "provisioner_runtime"
    RELEASE_ARTIFACTS = "release_artifacts"


class RecoveryStatus(StrEnum):
    """Evaluation status for a subsystem recovery."""

    CERTIFIED = "CERTIFIED"
    TARGET_MET = "TARGET_MET"
    TARGET_VIOLATED = "TARGET_VIOLATED"
    INVARIANT_FAILED = "INVARIANT_FAILED"
    FAILED = "FAILED"


class RPOTarget(BaseModel):
    """Target Recovery Point Objective specification."""

    target_seconds: float = Field(ge=0.0)
    loss_tolerance_description: str = ""


class RTOTarget(BaseModel):
    """Target Recovery Time Objective specification."""

    target_seconds: float = Field(ge=0.0)
    readiness_criteria: str = ""


class SubsystemDRPolicy(BaseModel):
    """Formal Disaster Recovery policy specification for a single subsystem."""

    domain: SubsystemDomain
    name: str
    target_rpo_seconds: float = Field(
        ge=0.0,
        description="Maximum tolerable data loss measured in seconds of committed state.",
    )
    target_rto_seconds: float = Field(
        ge=0.0,
        description="Maximum tolerable downtime to restore service and achieve full integrity.",
    )
    criticality: DRCriticality
    invariants: list[str] = Field(default_factory=list)
    description: str = ""


class DomainRecoveryMetric(BaseModel):
    """Measured recovery metrics for an individual domain during a recovery exercise."""

    domain: SubsystemDomain
    target_rpo_seconds: float
    target_rto_seconds: float
    measured_rpo_seconds: float
    measured_rto_seconds: float
    rpo_met: bool
    rto_met: bool
    status: RecoveryStatus
    invariants_satisfied: list[str] = Field(default_factory=list)
    invariants_violated: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class DisasterRecoveryExecutionReceipt(BaseModel):
    """Authoritative audit receipt emitted after a disaster recovery and PITR exercise."""

    recovery_id: str
    backup_id: str
    recovery_target_time: datetime
    recovery_target_name: str | None = None
    recovery_target_lsn: str | None = None
    actual_recovery_point: datetime
    source_host: str
    target_clean_host: str
    started_at: datetime
    completed_at: datetime
    overall_rpo_seconds: float
    overall_rto_seconds: float
    domain_metrics: dict[str, DomainRecoveryMetric] = Field(default_factory=dict)
    all_targets_met: bool = False
    all_invariants_met: bool = False
    governing_invariant_upheld: bool = False
    verdict: RecoveryStatus = RecoveryStatus.CERTIFIED
    summary: str = ""


class DisasterRecoveryTargetRegistry:
    """Authoritative registry defining explicit RPO/RTO targets for Enterprise OS."""

    def __init__(self) -> None:
        self._policies: dict[SubsystemDomain, SubsystemDRPolicy] = {
            SubsystemDomain.POSTGRESQL: SubsystemDRPolicy(
                domain=SubsystemDomain.POSTGRESQL,
                name="PostgreSQL Primary Cluster",
                target_rpo_seconds=1.0,
                target_rto_seconds=15.0,
                criticality=DRCriticality.HIGH,
                invariants=[
                    "ACID consistency across all relational tables",
                    "pgvector extension operational upon recovery",
                    "Migrations 0001-0007 idempotently active",
                    "No silent truncation of WAL segments",
                ],
                description="Primary persistent relational and vector store for Enterprise OS.",
            ),
            SubsystemDomain.CTS: SubsystemDRPolicy(
                domain=SubsystemDomain.CTS,
                name="Canonical Task State (CTS)",
                target_rpo_seconds=0.0,
                target_rto_seconds=5.0,
                criticality=DRCriticality.CRITICAL,
                invariants=[
                    "CTS version numbers remain strictly monotonic",
                    "CAS updates succeed from recovered version",
                    "Zero resurrected terminal tasks",
                    "Task dependency DAG remains acyclic and intact",
                ],
                description="Authoritative task lifecycle and state machine coordination.",
            ),
            SubsystemDomain.PROVENANCE: SubsystemDRPolicy(
                domain=SubsystemDomain.PROVENANCE,
                name="W3C PROV Audit Ledger",
                target_rpo_seconds=0.0,
                target_rto_seconds=5.0,
                criticality=DRCriticality.CRITICAL,
                invariants=[
                    "W3C PROV cryptographic hash chain verifies 100%",
                    "No broken hash links across tenant audit blocks",
                    "Appending post-recovery blocks preserves cryptographic chain",
                    "Zero deleted or retroactively altered provenance records",
                ],
                description="Cryptographic tamper-evident audit ledger chained per tenant.",
            ),
            SubsystemDomain.REPLAY_STATE: SubsystemDRPolicy(
                domain=SubsystemDomain.REPLAY_STATE,
                name="Specialist Replay Protection",
                target_rpo_seconds=0.0,
                target_rto_seconds=2.0,
                criticality=DRCriticality.CRITICAL,
                invariants=[
                    "All pre-recovery execution IDs remain rejected",
                    "Zero duplicate specialist actuation",
                    "Persistent replay manager loads state cleanly",
                    "Fail-closed rejection on re-submitted execution attempt",
                ],
                description="Sandbox and provisioner deduplication and replay defense.",
            ),
            SubsystemDomain.INSTITUTIONAL_MEMORY: SubsystemDRPolicy(
                domain=SubsystemDomain.INSTITUTIONAL_MEMORY,
                name="Promoted Institutional Memory",
                target_rpo_seconds=1.0,
                target_rto_seconds=5.0,
                criticality=DRCriticality.HIGH,
                invariants=[
                    "Promoted memories agree with the recovery point timestamp",
                    "Zero unpromoted or post-cutoff memories leaked into recovered store",
                    "Version progression and supersedes linkage remain intact",
                    "Tenant boundary isolation strictly preserved",
                ],
                description="Promoted brand knowledge, heuristics, and model parameter deltas.",
            ),
            SubsystemDomain.TELEMETRY: SubsystemDRPolicy(
                domain=SubsystemDomain.TELEMETRY,
                name="Omnichannel Operational Telemetry",
                target_rpo_seconds=5.0,
                target_rto_seconds=5.0,
                criticality=DRCriticality.STANDARD,
                invariants=[
                    "Telemetry events agree with the recovery point timestamp",
                    "Admission receipts retain content_hash and schema version",
                    "Work items retain lease fencing state and retry counts",
                    "Zero cross-tenant telemetry query leakage",
                ],
                description="Durable telemetry admission receipts, work items, and collection runs.",
            ),
            SubsystemDomain.PROVISIONER_RUNTIME: SubsystemDRPolicy(
                domain=SubsystemDomain.PROVISIONER_RUNTIME,
                name="Provisioner Runtime & Leases",
                target_rpo_seconds=0.0,
                target_rto_seconds=5.0,
                criticality=DRCriticality.CRITICAL,
                invariants=[
                    "Orphan execution leases cleanly reset or expired",
                    "Zero zombie processes or lingering specialist cgroup scopes",
                    "Unix Domain Socket recreates with strict 0660 permissions",
                    "Peer credential authentication verified on clean host",
                ],
                description="Physical sandbox provisioner daemon and host container boundary.",
            ),
            SubsystemDomain.RELEASE_ARTIFACTS: SubsystemDRPolicy(
                domain=SubsystemDomain.RELEASE_ARTIFACTS,
                name="Release Artifacts & Attestation",
                target_rpo_seconds=0.0,
                target_rto_seconds=10.0,
                criticality=DRCriticality.CRITICAL,
                invariants=[
                    "Release bundle bitwise reproducible across hosts",
                    "Ed25519 signature on release manifest verifies",
                    "SLSA builder attestation trust anchors satisfied",
                    "Clean-room installer succeeds without host workspace dependencies",
                ],
                description="Immutable release packages, SBOM, and cryptographic attestations.",
            ),
        }

    def get_policy(self, domain: SubsystemDomain) -> SubsystemDRPolicy:
        """Return the policy specification for a domain."""
        return self._policies[domain]

    def all_policies(self) -> dict[SubsystemDomain, SubsystemDRPolicy]:
        """Return all registered subsystem policies."""
        return dict(self._policies)

    def evaluate_metric(
        self,
        domain: SubsystemDomain,
        measured_rpo_seconds: float,
        measured_rto_seconds: float,
        invariants_satisfied: list[str],
        invariants_violated: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> DomainRecoveryMetric:
        """Evaluate measured RPO and RTO against the registered subsystem policy."""
        policy = self.get_policy(domain)
        violated = invariants_violated or []
        rpo_met = measured_rpo_seconds <= policy.target_rpo_seconds
        rto_met = measured_rto_seconds <= policy.target_rto_seconds

        if violated:
            status = RecoveryStatus.INVARIANT_FAILED
        elif rpo_met and rto_met:
            status = RecoveryStatus.TARGET_MET
        else:
            status = RecoveryStatus.TARGET_VIOLATED

        return DomainRecoveryMetric(
            domain=domain,
            target_rpo_seconds=policy.target_rpo_seconds,
            target_rto_seconds=policy.target_rto_seconds,
            measured_rpo_seconds=round(measured_rpo_seconds, 4),
            measured_rto_seconds=round(measured_rto_seconds, 4),
            rpo_met=rpo_met,
            rto_met=rto_met,
            status=status,
            invariants_satisfied=invariants_satisfied,
            invariants_violated=violated,
            details=details or {},
        )
