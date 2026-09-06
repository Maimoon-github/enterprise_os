# File: audit_provenance.py
"""
Layer 7: Audit & Provenance.

Permanent append-only operational lineage:
- Models provenance using W3C PROV concepts: Entities, Activities, Agents.
- Cryptographically chained audit ledger ensuring tamper-resistance.
- Records state mutations, policy decisions, tool calls, artifact operations, approvals.
- Audit records are strictly immutable and never become working state.
"""

from __future__ import annotations

import copy
import dataclasses
import enum
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("audit_provenance")


class ProvRelationType(str, enum.Enum):
    """W3C PROV core relationship types."""
    USED = "used"
    WAS_GENERATED_BY = "wasGeneratedBy"
    WAS_DERIVED_FROM = "wasDerivedFrom"
    WAS_ATTRIBUTED_TO = "wasAttributedTo"
    WAS_ASSOCIATED_WITH = "wasAssociatedWith"


@dataclasses.dataclass(frozen=True)
class ProvEntity:
    entity_id: str
    entity_type: str
    attributes: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class ProvActivity:
    activity_id: str
    activity_type: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    attributes: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class ProvAgent:
    agent_id: str
    agent_type: str
    attributes: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class ProvStatement:
    statement_id: str
    relation_type: ProvRelationType
    subject_id: str
    object_id: str
    timestamp: datetime
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class AuditRecord:
    record_id: str
    sequence_number: int
    timestamp_iso: str
    actor_id: str
    action_type: str
    payload_hash: str
    details: Dict[str, Any]
    previous_hash: str
    record_hash: str


class ImmutableAuditLedger:
    """
    Append-only, cryptographically chained audit ledger.
    Every record commits to the previous record's hash, forming an immutable chain.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self):
        self._chain: List[AuditRecord] = []
        self._prov_entities: Dict[str, ProvEntity] = {}
        self._prov_activities: Dict[str, ProvActivity] = {}
        self._prov_agents: Dict[str, ProvAgent] = {}
        self._prov_statements: List[ProvStatement] = []

    def record_entity(self, entity_id: str, entity_type: str, attributes: Optional[Dict[str, Any]] = None) -> ProvEntity:
        entity = ProvEntity(entity_id=entity_id, entity_type=entity_type, attributes=attributes or {})
        self._prov_entities[entity_id] = entity
        return entity

    def record_activity(self, activity_id: str, activity_type: str, started_at: datetime,
                        ended_at: Optional[datetime] = None, attributes: Optional[Dict[str, Any]] = None) -> ProvActivity:
        activity = ProvActivity(
            activity_id=activity_id,
            activity_type=activity_type,
            started_at=started_at,
            ended_at=ended_at,
            attributes=attributes or {}
        )
        self._prov_activities[activity_id] = activity
        return activity

    def record_agent(self, agent_id: str, agent_type: str, attributes: Optional[Dict[str, Any]] = None) -> ProvAgent:
        agent = ProvAgent(agent_id=agent_id, agent_type=agent_type, attributes=attributes or {})
        self._prov_agents[agent_id] = agent
        return agent

    def record_prov_statement(self, relation: ProvRelationType, subject_id: str,
                              object_id: str, metadata: Optional[Dict[str, Any]] = None) -> ProvStatement:
        statement = ProvStatement(
            statement_id=f"prov_{uuid.uuid4().hex[:8]}",
            relation_type=relation,
            subject_id=subject_id,
            object_id=object_id,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        self._prov_statements.append(statement)
        return statement

    def append_entry(self, actor_id: str, action_type: str, details: Dict[str, Any]) -> AuditRecord:
        seq = len(self._chain)
        prev_hash = self._chain[-1].record_hash if self._chain else self.GENESIS_HASH
        timestamp_iso = datetime.now(timezone.utc).isoformat()

        payload_serialized = json.dumps(details, sort_keys=True)
        payload_hash = hashlib.sha256(payload_serialized.encode("utf-8")).hexdigest()

        block_content = f"{seq}::{timestamp_iso}::{actor_id}::{action_type}::{payload_hash}::{prev_hash}"
        record_hash = hashlib.sha256(block_content.encode("utf-8")).hexdigest()

        record = AuditRecord(
            record_id=f"rec_{uuid.uuid4().hex[:8]}",
            sequence_number=seq,
            timestamp_iso=timestamp_iso,
            actor_id=actor_id,
            action_type=action_type,
            payload_hash=payload_hash,
            details=copy.deepcopy(details),
            previous_hash=prev_hash,
            record_hash=record_hash
        )
        self._chain.append(record)
        logger.debug("Audit append: seq=%d, action=%s, actor=%s, hash=%s", seq, action_type, actor_id, record_hash[:8])
        return record

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """Verifies hash-chain continuity from genesis to head."""
        for idx, record in enumerate(self._chain):
            expected_prev = self._chain[idx - 1].record_hash if idx > 0 else self.GENESIS_HASH
            if record.previous_hash != expected_prev:
                return False, f"Broken chain linkage at seq {record.sequence_number}: expected {expected_prev}, got {record.previous_hash}"

            payload_serialized = json.dumps(record.details, sort_keys=True)
            recomputed_payload_hash = hashlib.sha256(payload_serialized.encode("utf-8")).hexdigest()
            if record.payload_hash != recomputed_payload_hash:
                return False, f"Payload tampering detected at seq {record.sequence_number}"

            block_content = f"{record.sequence_number}::{record.timestamp_iso}::{record.actor_id}::{record.action_type}::{record.payload_hash}::{record.previous_hash}"
            recomputed_block_hash = hashlib.sha256(block_content.encode("utf-8")).hexdigest()
            if record.record_hash != recomputed_block_hash:
                return False, f"Invalid record hash at seq {record.sequence_number}"

        return True, None

    def get_chain(self) -> List[AuditRecord]:
        return list(self._chain)

    def get_prov_statements(self) -> List[ProvStatement]:
        return list(self._prov_statements)