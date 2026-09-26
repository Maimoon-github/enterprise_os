"""Records immutable entity/activity/agent audit lineage with W3C PROV compliance."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from app.persistence.repositories.provenance import ProvenanceRepository
from app.schemas.development.provenance import (
    DevelopmentProvEvent,
    InTotoStatement,
    SlsaBuildDefinition,
    SlsaBuilder,
    SlsaProvenancePredicate,
    SlsaResourceDescriptor,
    SlsaRunDetails,
)
from app.schemas.governance import WorkerRole
from app.schemas.provenance import (
    ProvenanceRecord,
    ProvRelationType,
    SandboxExecutionAuditMetadata,
    W3CProvActivity,
    W3CProvAgent,
    W3CProvBundle,
    W3CProvEntity,
    W3CProvRelation,
)
from app.security.cryptographic_validator import sign_payload
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

_SENSITIVE_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|token|password|auth)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"), r"\1: [REDACTED]"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{8,}"), r"\1[REDACTED]"),
]


def _sanitize_text(text: str) -> str:
    """Redact sensitive credentials, auth tokens, and secrets from audit text."""
    sanitized = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive fields from a metadata dictionary."""
    cleaned: dict[str, Any] = {}
    for k, v in data.items():
        k_lower = k.lower()
        if any(s in k_lower for s in ("secret", "token", "password", "api_key", "hidden_reasoning", "private_key")):
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, str):
            cleaned[k] = _sanitize_text(v)
        elif isinstance(v, dict):
            cleaned[k] = _sanitize_dict(v)
        elif isinstance(v, list):
            cleaned[k] = [_sanitize_text(item) if isinstance(item, str) else item for item in v]
        else:
            cleaned[k] = v
    return cleaned


def compute_canonical_sha256(data: Any) -> str:
    """Compute deterministic SHA-256 digest using canonical JSON serialization.

    Applies model_dump(mode='json') for Pydantic models, redacts sensitive patterns,
    sorts dictionary keys, and UTF-8 encodes. Never hashes unstable repr() output.
    """
    if data is None:
        return hashlib.sha256(b"null").hexdigest()
    if hasattr(data, "model_dump"):
        dumped = data.model_dump(mode="json")
    elif isinstance(data, dict):
        dumped = data
    elif isinstance(data, (list, tuple)):
        dumped = [
            item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            for item in data
        ]
    else:
        dumped = data

    if isinstance(dumped, dict):
        cleaned = _sanitize_dict(dumped)
    elif isinstance(dumped, list):
        cleaned = [
            _sanitize_dict(i) if isinstance(i, dict) else i
            for i in dumped
        ]
    else:
        cleaned = dumped

    serialized = json.dumps(cleaned, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ProvenanceRecorder:
    """Service boundary over ``ProvenanceRepository`` for W3C PROV audit capture."""

    def __init__(
        self,
        repository: ProvenanceRepository,
        *,
        control_plane_key: Ed25519PrivateKey | None = None,
        signing_key_id: str = "control-plane-ed25519-v1",
    ) -> None:
        self._repository = repository
        self._signing_key_id = signing_key_id
        if control_plane_key is not None:
            self._control_plane_key = control_plane_key
        else:
            self._control_plane_key = Ed25519PrivateKey.generate()
        self._control_plane_public_key_pem = self._control_plane_key.public_key().public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    @property
    def control_plane_public_key_pem(self) -> str:
        """Return PEM-encoded control plane public key used for audit signatures."""
        return self._control_plane_public_key_pem

    @property
    def signing_key_id(self) -> str:
        """Return key ID of active control plane signing key."""
        return self._signing_key_id

    @property
    def repository(self) -> ProvenanceRepository:
        """Return the underlying provenance repository."""
        return self._repository

    async def record(
        self,
        *,
        tenant_id: str,
        entity_id: str,
        activity: str,
        agent: str,
        metadata: dict[str, Any] | None = None,
        w3c_prov: dict[str, Any] | None = None,
        record_id: str | None = None,
        session: Any = None,
    ) -> ProvenanceRecord:
        """Append and return a new hash-chained provenance record."""
        if session is not None:
            try:
                return await self._repository.append(
                    tenant_id=tenant_id,
                    entity_id=entity_id,
                    activity=activity,
                    agent=agent,
                    record_id=record_id,
                    metadata=metadata,
                    w3c_prov=w3c_prov,
                    session=session,
                )
            except TypeError:
                pass
        return await self._repository.append(
            tenant_id=tenant_id,
            entity_id=entity_id,
            activity=activity,
            agent=agent,
            record_id=record_id,
            metadata=metadata,
            w3c_prov=w3c_prov,
        )

    async def verify_chain(self, tenant_id: str) -> bool:
        """Verify unbroken hash chain for ``tenant_id``."""
        if hasattr(self._repository, "verify_chain"):
            return await self._repository.verify_chain(tenant_id)
        records = await self._repository.chain(tenant_id)
        if not records:
            return True
        return self._repository.verify(records)

    def build_sandbox_w3c_prov(
        self,
        *,
        tenant_id: str,
        task_id: str,
        execution_id: str,
        worker_role: str,
        capability: str,
        operation: str,
        lifecycle_stage: str,
        status: str,
        input_payload: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        artifacts: list[str] | None = None,
        egress_grant_id: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
    ) -> W3CProvBundle:
        """Construct full W3C PROV bundle mapping Entity, Activity, Agent, and relations."""
        activity_id = f"urn:enterprise_os:activity:sandbox_execution:{execution_id}:{lifecycle_stage}"
        worker_agent_id = f"urn:enterprise_os:agent:worker:{worker_role}"
        sandbox_agent_id = "urn:enterprise_os:agent:sandbox_controller:aio-sandbox:v1.11.0"
        orchestrator_agent_id = f"urn:enterprise_os:agent:orchestrator:{tenant_id}"

        mandate_entity_id = f"urn:enterprise_os:entity:mandate:{execution_id}"
        task_entity_id = f"urn:enterprise_os:entity:task:{task_id}"

        # 1. Activities
        activities = [
            W3CProvActivity(
                id=activity_id,
                label=f"Sandbox Execution: {operation} ({capability}) [{lifecycle_stage}]",
                started_at=started_at or datetime.now(UTC),
                ended_at=ended_at or datetime.now(UTC),
                attributes={
                    "operation": operation,
                    "capability": capability,
                    "lifecycle_stage": lifecycle_stage,
                    "status": status,
                },
            )
        ]

        # 2. Agents
        agents = [
            W3CProvAgent(
                id=worker_agent_id,
                label=f"Bounded Worker Agent ({worker_role})",
                role=worker_role,
            ),
            W3CProvAgent(
                id=sandbox_agent_id,
                label="AIO Sandbox Execution Controller",
                role="sandbox_runtime",
            ),
            W3CProvAgent(
                id=orchestrator_agent_id,
                label=f"Tenant Orchestration Authority ({tenant_id})",
                role="delegator",
            ),
        ]

        # 3. Entities
        entities = [
            W3CProvEntity(
                id=mandate_entity_id,
                label=f"Sandbox Invocation Mandate ({execution_id})",
                attributes={"capability": capability, "task_id": task_id},
            ),
            W3CProvEntity(
                id=task_entity_id,
                label=f"Governed Task ({task_id})",
                attributes={"tenant_id": tenant_id},
            ),
        ]

        # Input payload hash entity
        if input_payload:
            payload_bytes = json.dumps(input_payload, sort_keys=True, default=str).encode("utf-8")
            payload_hash = hashlib.sha256(payload_bytes).hexdigest()
            input_entity_id = f"urn:enterprise_os:entity:input_payload:{execution_id}"
            entities.append(
                W3CProvEntity(
                    id=input_entity_id,
                    label=f"Input Payload Hash ({payload_hash[:12]})",
                    value_hash=payload_hash,
                )
            )

        # Output result entity
        result_entity_id = None
        if output_summary:
            out_bytes = json.dumps(output_summary, sort_keys=True, default=str).encode("utf-8")
            out_hash = hashlib.sha256(out_bytes).hexdigest()
            result_entity_id = f"urn:enterprise_os:entity:result:{execution_id}"
            entities.append(
                W3CProvEntity(
                    id=result_entity_id,
                    label=f"Sanitized Result ({out_hash[:12]})",
                    value_hash=out_hash,
                    attributes={"fields_count": len(output_summary)},
                )
            )

        # Artifact entities
        artifact_entity_ids = []
        if artifacts:
            for art in artifacts:
                art_id = f"urn:enterprise_os:entity:artifact:{art}"
                artifact_entity_ids.append(art_id)
                entities.append(
                    W3CProvEntity(
                        id=art_id,
                        label=f"Exported Artifact: {art}",
                        attributes={"artifact_name": art},
                    )
                )

        # Egress grant entity
        egress_entity_id = None
        if egress_grant_id:
            egress_entity_id = f"urn:enterprise_os:entity:egress_grant:{egress_grant_id}"
            entities.append(
                W3CProvEntity(
                    id=egress_entity_id,
                    label=f"Authorized Egress Grant ({egress_grant_id})",
                )
            )

        # 4. Relations
        relations = [
            # prov:wasAssociatedWith
            W3CProvRelation(
                relation_type=ProvRelationType.WAS_ASSOCIATED_WITH,
                source_id=activity_id,
                target_id=worker_agent_id,
            ),
            W3CProvRelation(
                relation_type=ProvRelationType.WAS_ASSOCIATED_WITH,
                source_id=activity_id,
                target_id=sandbox_agent_id,
            ),
            # prov:actedOnBehalfOf
            W3CProvRelation(
                relation_type=ProvRelationType.ACTED_ON_BEHALF_OF,
                source_id=worker_agent_id,
                target_id=orchestrator_agent_id,
            ),
            # prov:used
            W3CProvRelation(
                relation_type=ProvRelationType.USED,
                source_id=activity_id,
                target_id=mandate_entity_id,
            ),
        ]

        if input_payload:
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.USED,
                    source_id=activity_id,
                    target_id=f"urn:enterprise_os:entity:input_payload:{execution_id}",
                )
            )

        if egress_entity_id:
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.USED,
                    source_id=activity_id,
                    target_id=egress_entity_id,
                )
            )

        # prov:wasGeneratedBy
        if result_entity_id:
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_GENERATED_BY,
                    source_id=result_entity_id,
                    target_id=activity_id,
                )
            )
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_ATTRIBUTED_TO,
                    source_id=result_entity_id,
                    target_id=worker_agent_id,
                )
            )
            if input_payload:
                relations.append(
                    W3CProvRelation(
                        relation_type=ProvRelationType.WAS_DERIVED_FROM,
                        source_id=result_entity_id,
                        target_id=f"urn:enterprise_os:entity:input_payload:{execution_id}",
                    )
                )

        for art_id in artifact_entity_ids:
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_GENERATED_BY,
                    source_id=art_id,
                    target_id=activity_id,
                )
            )

        return W3CProvBundle(
            activities=activities,
            agents=agents,
            entities=entities,
            relations=relations,
        )

    async def record_sandbox_execution(
        self,
        *,
        tenant_id: str,
        task_id: str,
        execution_id: str,
        worker_role: str,
        capability: str,
        operation: str,
        lifecycle_stage: str,
        status: str,
        exit_code: int | None = None,
        duration_ms: float = 0.0,
        command: str | None = None,
        resources: dict[str, Any] | None = None,
        input_payload: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        artifacts: list[str] | None = None,
        error_details: str | None = None,
        egress_grant_id: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
    ) -> ProvenanceRecord:
        """Capture, normalize, and append an immutable W3C PROV sandbox execution audit record."""
        # Sanitize sensitive text in error details and commands
        cleaned_error = _sanitize_text(error_details) if error_details else None
        cleaned_command = _sanitize_text(command) if command else None
        cleaned_resources = _sanitize_dict(resources or {})

        # Compute output metadata summary without storing large bloated payloads
        sanitized_output_summary = _sanitize_dict(output_summary or {})
        out_bytes = json.dumps(sanitized_output_summary, sort_keys=True, default=str).encode("utf-8")
        output_meta = {
            "fields_count": len(sanitized_output_summary),
            "output_hash": hashlib.sha256(out_bytes).hexdigest() if sanitized_output_summary else None,
            "artifact_references": artifacts or [],
        }

        metadata = SandboxExecutionAuditMetadata(
            execution_id=execution_id,
            task_id=task_id,
            worker_role=worker_role,
            capability=capability,
            operation=operation,
            lifecycle_stage=lifecycle_stage,
            status=status,
            exit_code=exit_code,
            duration_ms=round(duration_ms, 2),
            command=cleaned_command,
            egress_grant_id=egress_grant_id,
            resources=cleaned_resources,
            output_summary=output_meta,
            artifacts=artifacts or [],
            error_details=cleaned_error,
        ).model_dump(mode="json")

        w3c_bundle = self.build_sandbox_w3c_prov(
            tenant_id=tenant_id,
            task_id=task_id,
            execution_id=execution_id,
            worker_role=worker_role,
            capability=capability,
            operation=operation,
            lifecycle_stage=lifecycle_stage,
            status=status,
            input_payload=input_payload,
            output_summary=sanitized_output_summary,
            artifacts=artifacts,
            egress_grant_id=egress_grant_id,
            started_at=started_at,
            ended_at=ended_at,
        ).model_dump(mode="json")

        # Stable event ID for idempotency: tenant + execution + lifecycle_stage
        stable_event_id = f"prov-sb-{tenant_id}-{execution_id}-{lifecycle_stage}"
        activity_tag = f"sandbox_execution:{operation}:{lifecycle_stage}"

        return await self._repository.append(
            tenant_id=tenant_id,
            entity_id=f"mandate:{execution_id}",
            activity=activity_tag,
            agent=f"worker:{worker_role}",
            record_id=stable_event_id,
            metadata=metadata,
            w3c_prov=w3c_bundle,
        )

    def build_worker_w3c_prov(
        self,
        *,
        tenant_id: str,
        task_id: str,
        worker_role: str | WorkerRole,
        lifecycle_stage: str,
        input_data: Any | None = None,
        output_data: Any | None = None,
        sandbox_execution_id: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> W3CProvBundle:
        """Construct W3C PROV bundle mapping Entity, Activity, Agent, and relations for worker execution."""
        worker_role_str = worker_role.value if hasattr(worker_role, "value") else str(worker_role)
        activity_id = f"urn:enterprise_os:activity:worker_execution:{task_id}:{lifecycle_stage}"
        worker_agent_id = f"urn:enterprise_os:agent:worker:{worker_role_str}"
        orchestrator_agent_id = f"urn:enterprise_os:agent:orchestrator:{tenant_id}"
        task_entity_id = f"urn:enterprise_os:entity:task:{task_id}"

        act_attrs: dict[str, Any] = {
            "worker_role": worker_role_str,
            "lifecycle_stage": lifecycle_stage,
            **(attributes or {}),
        }
        if sandbox_execution_id:
            act_attrs["sandbox_execution_id"] = sandbox_execution_id

        activities = [
            W3CProvActivity(
                id=activity_id,
                label=f"Worker Execution: {worker_role_str} [{lifecycle_stage}]",
                started_at=started_at or datetime.now(UTC),
                ended_at=ended_at or datetime.now(UTC),
                attributes=act_attrs,
            )
        ]

        agents = [
            W3CProvAgent(
                id=worker_agent_id,
                label=f"Bounded Worker Agent ({worker_role_str})",
                role=worker_role_str,
            ),
            W3CProvAgent(
                id=orchestrator_agent_id,
                label=f"Tenant Orchestration Authority ({tenant_id})",
                role="delegator",
            ),
        ]

        entities = [
            W3CProvEntity(
                id=task_entity_id,
                label=f"Governed Task ({task_id})",
                attributes={"tenant_id": tenant_id},
            )
        ]

        relations = [
            W3CProvRelation(
                relation_type=ProvRelationType.WAS_ASSOCIATED_WITH,
                source_id=activity_id,
                target_id=worker_agent_id,
            ),
            W3CProvRelation(
                relation_type=ProvRelationType.ACTED_ON_BEHALF_OF,
                source_id=worker_agent_id,
                target_id=orchestrator_agent_id,
            ),
            W3CProvRelation(
                relation_type=ProvRelationType.USED,
                source_id=activity_id,
                target_id=task_entity_id,
            ),
        ]

        input_entity_id: str | None = None
        if input_data is not None:
            input_hash = compute_canonical_sha256(input_data)
            input_entity_id = f"urn:enterprise_os:entity:task_grant:{task_id}"
            entities.append(
                W3CProvEntity(
                    id=input_entity_id,
                    label=f"Task Grant Input ({input_hash[:12]})",
                    value_hash=input_hash,
                    attributes={"tenant_id": tenant_id, "task_id": task_id, "digest": input_hash},
                )
            )
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.USED,
                    source_id=activity_id,
                    target_id=input_entity_id,
                )
            )

        if output_data is not None:
            output_hash = compute_canonical_sha256(output_data)
            output_entity_id = f"urn:enterprise_os:entity:worker_result:{task_id}:{lifecycle_stage}"
            out_attrs: dict[str, Any] = {"lifecycle_stage": lifecycle_stage, "digest": output_hash}
            if sandbox_execution_id:
                out_attrs["sandbox_execution_id"] = sandbox_execution_id
            entities.append(
                W3CProvEntity(
                    id=output_entity_id,
                    label=f"Worker Result ({output_hash[:12]}) [{lifecycle_stage}]",
                    value_hash=output_hash,
                    attributes=out_attrs,
                )
            )
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_GENERATED_BY,
                    source_id=output_entity_id,
                    target_id=activity_id,
                )
            )
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_ATTRIBUTED_TO,
                    source_id=output_entity_id,
                    target_id=worker_agent_id,
                )
            )
            if input_entity_id:
                relations.append(
                    W3CProvRelation(
                        relation_type=ProvRelationType.WAS_DERIVED_FROM,
                        source_id=output_entity_id,
                        target_id=input_entity_id,
                    )
                )

        return W3CProvBundle(
            activities=activities,
            agents=agents,
            entities=entities,
            relations=relations,
        )

    async def record_worker_execution(
        self,
        *,
        tenant_id: str,
        task_id: str,
        worker_role: str | WorkerRole,
        lifecycle_stage: str,
        input_data: Any | None = None,
        output_data: Any | None = None,
        sandbox_execution_id: str | None = None,
        duration_ms: float = 0.0,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        session: Any = None,
    ) -> ProvenanceRecord:
        """Append worker-level W3C PROV audit record for started, completed, or failed executions."""
        worker_role_str = worker_role.value if hasattr(worker_role, "value") else str(worker_role)

        w3c_bundle = self.build_worker_w3c_prov(
            tenant_id=tenant_id,
            task_id=task_id,
            worker_role=worker_role_str,
            lifecycle_stage=lifecycle_stage,
            input_data=input_data,
            output_data=output_data,
            sandbox_execution_id=sandbox_execution_id,
            started_at=started_at,
            ended_at=ended_at,
            attributes=metadata,
        ).model_dump(mode="json")

        meta: dict[str, Any] = {
            "task_id": task_id,
            "worker_role": worker_role_str,
            "lifecycle_stage": lifecycle_stage,
            "duration_ms": duration_ms,
            **(metadata or {}),
        }
        if input_data is not None:
            meta["input_sha256"] = compute_canonical_sha256(input_data)
        if output_data is not None:
            meta["output_sha256"] = compute_canonical_sha256(output_data)
        if sandbox_execution_id:
            meta["sandbox_execution_id"] = sandbox_execution_id

        stable_record_id = f"prov-worker-{tenant_id}-{task_id}-{lifecycle_stage}"
        activity_tag = "worker_execution" if lifecycle_stage in ("completed", "failed") else f"worker_execution_{lifecycle_stage}"

        if session is not None:
            try:
                return await self._repository.append(
                    tenant_id=tenant_id,
                    entity_id=task_id,
                    activity=activity_tag,
                    agent=worker_role_str,
                    record_id=stable_record_id,
                    metadata=meta,
                    w3c_prov=w3c_bundle,
                    session=session,
                )
            except TypeError:
                pass

        return await self._repository.append(
            tenant_id=tenant_id,
            entity_id=task_id,
            activity=activity_tag,
            agent=worker_role_str,
            record_id=stable_record_id,
            metadata=meta,
            w3c_prov=w3c_bundle,
        )

    def build_governed_execution_w3c_prov(
        self,
        *,
        tenant_id: str,
        activity_id: str,
        activity_type: str,
        agent_id: str,
        agent_role: str,
        entity_id: str,
        entity_type: str,
        used_entity_ids: list[str] | None = None,
        generated_entity_ids: list[str] | None = None,
        derived_from_entity_ids: list[str] | None = None,
        delegated_from_agent_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> W3CProvBundle:
        """Construct full W3C PROV bundle mapping Entity, Activity, Agent, and relations for governed control-plane flow."""
        act = W3CProvActivity(
            id=activity_id,
            label=f"Governed Activity: {activity_type}",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            attributes={"activity_type": activity_type, **(attributes or {})},
        )
        ag = W3CProvAgent(
            id=agent_id,
            label=f"Governed Agent ({agent_role})",
            role=agent_role,
        )
        primary_entity = W3CProvEntity(
            id=entity_id,
            label=f"Governed Entity ({entity_type})",
            attributes={"entity_type": entity_type, "tenant_id": tenant_id},
        )

        activities = [act]
        agents = [ag]
        entities = [primary_entity]
        relations = [
            W3CProvRelation(
                relation_type=ProvRelationType.WAS_ASSOCIATED_WITH,
                source_id=activity_id,
                target_id=agent_id,
            )
        ]

        if delegated_from_agent_id:
            delegator_agent = W3CProvAgent(
                id=delegated_from_agent_id,
                label=f"Delegating Authority ({delegated_from_agent_id})",
                role="delegator",
            )
            agents.append(delegator_agent)
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.ACTED_ON_BEHALF_OF,
                    source_id=agent_id,
                    target_id=delegated_from_agent_id,
                )
            )

        for u_id in used_entity_ids or []:
            entities.append(
                W3CProvEntity(
                    id=u_id,
                    label=f"Used Entity ({u_id})",
                )
            )
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.USED,
                    source_id=activity_id,
                    target_id=u_id,
                )
            )

        for g_id in generated_entity_ids or []:
            if g_id != entity_id:
                entities.append(
                    W3CProvEntity(
                        id=g_id,
                        label=f"Generated Entity ({g_id})",
                    )
                )
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_GENERATED_BY,
                    source_id=g_id,
                    target_id=activity_id,
                )
            )
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_ATTRIBUTED_TO,
                    source_id=g_id,
                    target_id=agent_id,
                )
            )

        for d_id in derived_from_entity_ids or []:
            for g_id in (generated_entity_ids or [entity_id]):
                relations.append(
                    W3CProvRelation(
                        relation_type=ProvRelationType.WAS_DERIVED_FROM,
                        source_id=g_id,
                        target_id=d_id,
                    )
                )

        return W3CProvBundle(
            activities=activities,
            agents=agents,
            entities=entities,
            relations=relations,
        )

    async def record_governed_event(
        self,
        *,
        tenant_id: str,
        activity_type: str,
        agent_id: str,
        agent_role: str,
        entity_id: str,
        entity_type: str,
        used_entity_ids: list[str] | None = None,
        generated_entity_ids: list[str] | None = None,
        derived_from_entity_ids: list[str] | None = None,
        delegated_from_agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProvenanceRecord:
        """Capture and record a governed control-plane activity with full W3C PROV lineage bundle."""
        act_id = f"urn:enterprise_os:activity:{activity_type}:{entity_id}"
        w3c_bundle = self.build_governed_execution_w3c_prov(
            tenant_id=tenant_id,
            activity_id=act_id,
            activity_type=activity_type,
            agent_id=agent_id,
            agent_role=agent_role,
            entity_id=entity_id,
            entity_type=entity_type,
            used_entity_ids=used_entity_ids,
            generated_entity_ids=generated_entity_ids,
            derived_from_entity_ids=derived_from_entity_ids,
            delegated_from_agent_id=delegated_from_agent_id,
            attributes=metadata,
        )
        return await self._repository.append(
            tenant_id=tenant_id,
            entity_id=entity_id,
            activity=activity_type,
            agent=agent_id,
            metadata=metadata or {},
            w3c_prov=w3c_bundle.model_dump(mode="json"),
        )

    async def audit_chain(self, tenant_id: str) -> list[ProvenanceRecord]:
        """Return the full provenance chain for ``tenant_id``."""
        return await self._repository.chain(tenant_id)

    async def verify_chain(self, tenant_id: str) -> bool:
        """Return True if the persisted chain for ``tenant_id`` is intact."""
        chain = await self._repository.chain(tenant_id)
        return self._repository.verify(chain)

    async def reconstruct_lineage(self, tenant_id: str, execution_id: str) -> dict[str, Any]:
        """Reconstruct the end-to-end W3C PROV lineage for a specific sandbox execution."""
        chain = await self.audit_chain(tenant_id)
        execution_records = [
            rec
            for rec in chain
            if rec.metadata.get("execution_id") == execution_id
            or rec.entity_id == f"mandate:{execution_id}"
        ]

        if not execution_records:
            return {"execution_id": execution_id, "found": False, "stages": []}

        stages = [rec.metadata.get("lifecycle_stage") for rec in execution_records]
        final_record = execution_records[-1]
        final_meta = final_record.metadata

        return {
            "execution_id": execution_id,
            "task_id": final_meta.get("task_id"),
            "worker_role": final_meta.get("worker_role"),
            "capability": final_meta.get("capability"),
            "operation": final_meta.get("operation"),
            "status": final_meta.get("status"),
            "exit_code": final_meta.get("exit_code"),
            "duration_ms": final_meta.get("duration_ms"),
            "lifecycle_stages": stages,
            "record_count": len(execution_records),
            "artifacts": final_meta.get("artifacts", []),
            "resources": final_meta.get("resources", {}),
            "w3c_prov": final_record.w3c_prov,
            "is_chain_verified": self._repository.verify(chain),
        }

    async def validate_lineage(
        self,
        tenant_id: str,
        *,
        task_states: dict[str, Any],
        caller: Any,
        governing_task_id: str = "task-t33",
        task_state_service: Any = None,
        crypto_validator: Any = None,
    ) -> Any:
        """Validate end-to-end audit lineage, hash chain integrity, and CTS state (T33)."""
        from app.services.audit_validator import AuditLineageValidator

        validator = AuditLineageValidator(
            provenance_repository=self._repository,
            provenance_recorder=self,
            task_state_service=task_state_service,
            crypto_validator=crypto_validator,
        )
        return await validator.validate_lineage_and_integrity(
            tenant_id,
            task_states=task_states,
            caller=caller,
            governing_task_id=governing_task_id,
        )

    def build_development_w3c_prov(
        self,
        *,
        tenant_id: str,
        task_id: str,
        workflow_id: str,
        step_id: str,
        attempt_id: str,
        activity_type: str,
        agent_id: str = "W_DEV",
        worker_role: str = "W_DEV",
        input_snapshot_hash: str,
        output_snapshot_hash: str | None = None,
        artifact_hashes: dict[str, str] | None = None,
        sandbox_id: str | None = None,
        tool_id: str | None = None,
        tool_version: str | None = None,
        policy_version: str = "1.0.0",
        approval_token_id: str | None = None,
        reviewer_id: str | None = None,
        derived_from_attempt_id: str | None = None,
        derived_from_output_hash: str | None = None,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        status: str = "SUCCESS",
    ) -> W3CProvBundle:
        """Construct full W3C PROV bundle mapping Entity, Activity, Agent, and relations for W_DEV."""
        now = datetime.now(UTC)
        start_ts = started_at or now
        end_ts = ended_at or now

        activity_urn = f"urn:enterprise_os:activity:development:{task_id}:{step_id}:{attempt_id}:{activity_type}"
        orchestrator_agent_urn = f"urn:enterprise_os:agent:orchestrator:{tenant_id}"
        w_dev_agent_urn = "urn:enterprise_os:agent:worker:W_DEV"
        subagent_urn = f"urn:enterprise_os:agent:subagent:{agent_id}"

        activities = [
            W3CProvActivity(
                id=activity_urn,
                label=f"Development Activity: {activity_type} [{step_id}:{attempt_id}]",
                started_at=start_ts,
                ended_at=end_ts,
                attributes={
                    "task_id": task_id,
                    "workflow_id": workflow_id,
                    "step_id": step_id,
                    "attempt_id": attempt_id,
                    "activity_type": activity_type,
                    "policy_version": policy_version,
                    "status": status,
                },
            )
        ]

        agents = [
            W3CProvAgent(
                id=orchestrator_agent_urn,
                label=f"Intelligence Engine Orchestrator ({tenant_id})",
                type="prov:Agent",
                attributes={"tenant_id": tenant_id, "role": "orchestrator"},
            ),
            W3CProvAgent(
                id=w_dev_agent_urn,
                label="Development Lead Agent (W_DEV)",
                type="prov:Agent",
                attributes={"role": "worker", "worker_role": "W_DEV"},
            ),
            W3CProvAgent(
                id=subagent_urn,
                label=f"Sub-agent: {agent_id} ({worker_role})",
                type="prov:Agent",
                attributes={"agent_id": agent_id, "worker_role": worker_role},
            ),
        ]

        sandbox_agent_urn: str | None = None
        if sandbox_id:
            sandbox_agent_urn = f"urn:enterprise_os:agent:sandbox_controller:{sandbox_id}"
            agents.append(
                W3CProvAgent(
                    id=sandbox_agent_urn,
                    label=f"Sandbox Controller ({sandbox_id})",
                    type="prov:Agent",
                    attributes={"sandbox_id": sandbox_id},
                )
            )

        reviewer_agent_urn: str | None = None
        if reviewer_id:
            reviewer_agent_urn = f"urn:enterprise_os:agent:human_reviewer:{reviewer_id}"
            agents.append(
                W3CProvAgent(
                    id=reviewer_agent_urn,
                    label=f"Human Reviewer ({reviewer_id})",
                    type="prov:Agent",
                    attributes={"reviewer_id": reviewer_id},
                )
            )

        grant_entity_urn = f"urn:enterprise_os:entity:task_grant:{task_id}:{step_id}"
        input_entity_urn = f"urn:enterprise_os:entity:input_snapshot:{input_snapshot_hash[:16]}"
        entities = [
            W3CProvEntity(
                id=grant_entity_urn,
                label=f"Task Authorization Grant ({task_id}:{step_id})",
                attributes={"task_id": task_id, "step_id": step_id},
            ),
            W3CProvEntity(
                id=input_entity_urn,
                label=f"Input Snapshot ({input_snapshot_hash[:8]})",
                value_hash=input_snapshot_hash,
                attributes={"snapshot_hash": input_snapshot_hash},
            ),
        ]

        candidate_entity_urn: str | None = None
        if output_snapshot_hash:
            candidate_entity_urn = f"urn:enterprise_os:entity:candidate:{step_id}:{attempt_id}:{output_snapshot_hash[:16]}"
            entities.append(
                W3CProvEntity(
                    id=candidate_entity_urn,
                    label=f"Candidate Deliverable ({step_id}:{attempt_id})",
                    value_hash=output_snapshot_hash,
                    attributes={
                        "step_id": step_id,
                        "attempt_id": attempt_id,
                        "output_snapshot_hash": output_snapshot_hash,
                    },
                )
            )

        artifact_urns: list[str] = []
        if artifact_hashes:
            for art_name, art_hash in artifact_hashes.items():
                art_urn = f"urn:enterprise_os:entity:artifact:{art_hash[:16]}"
                artifact_urns.append(art_urn)
                entities.append(
                    W3CProvEntity(
                        id=art_urn,
                        label=f"Artifact: {art_name}",
                        value_hash=art_hash,
                        attributes={"name": art_name, "hash": art_hash},
                    )
                )

        approval_entity_urn: str | None = None
        if approval_token_id:
            approval_entity_urn = f"urn:enterprise_os:entity:approval_token:{approval_token_id}"
            entities.append(
                W3CProvEntity(
                    id=approval_entity_urn,
                    label=f"Approval Token ({approval_token_id})",
                    attributes={"token_id": approval_token_id},
                )
            )

        relations = [
            W3CProvRelation(
                relation_type=ProvRelationType.WAS_ASSOCIATED_WITH,
                source_id=activity_urn,
                target_id=subagent_urn,
            ),
            W3CProvRelation(
                relation_type=ProvRelationType.WAS_ASSOCIATED_WITH,
                source_id=activity_urn,
                target_id=w_dev_agent_urn,
            ),
            W3CProvRelation(
                relation_type=ProvRelationType.ACTED_ON_BEHALF_OF,
                source_id=subagent_urn,
                target_id=w_dev_agent_urn,
            ),
            W3CProvRelation(
                relation_type=ProvRelationType.ACTED_ON_BEHALF_OF,
                source_id=w_dev_agent_urn,
                target_id=orchestrator_agent_urn,
            ),
            W3CProvRelation(
                relation_type=ProvRelationType.USED,
                source_id=activity_urn,
                target_id=grant_entity_urn,
            ),
            W3CProvRelation(
                relation_type=ProvRelationType.USED,
                source_id=activity_urn,
                target_id=input_entity_urn,
            ),
        ]

        if sandbox_agent_urn:
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_ASSOCIATED_WITH,
                    source_id=activity_urn,
                    target_id=sandbox_agent_urn,
                )
            )

        if reviewer_agent_urn:
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_ASSOCIATED_WITH,
                    source_id=activity_urn,
                    target_id=reviewer_agent_urn,
                )
            )

        if approval_entity_urn:
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.USED,
                    source_id=activity_urn,
                    target_id=approval_entity_urn,
                )
            )

        if candidate_entity_urn:
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_GENERATED_BY,
                    source_id=candidate_entity_urn,
                    target_id=activity_urn,
                )
            )
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_ATTRIBUTED_TO,
                    source_id=candidate_entity_urn,
                    target_id=subagent_urn,
                )
            )
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_DERIVED_FROM,
                    source_id=candidate_entity_urn,
                    target_id=input_entity_urn,
                )
            )
            if derived_from_output_hash:
                prior_cand_urn = f"urn:enterprise_os:entity:candidate:{step_id}:{derived_from_attempt_id or 'prior'}:{derived_from_output_hash[:16]}"
                relations.append(
                    W3CProvRelation(
                        relation_type=ProvRelationType.WAS_DERIVED_FROM,
                        source_id=candidate_entity_urn,
                        target_id=prior_cand_urn,
                    )
                )

        for art_urn in artifact_urns:
            relations.append(
                W3CProvRelation(
                    relation_type=ProvRelationType.WAS_GENERATED_BY,
                    source_id=art_urn,
                    target_id=activity_urn,
                )
            )

        return W3CProvBundle(
            activities=activities,
            agents=agents,
            entities=entities,
            relations=relations,
        )

    async def record_development_event(
        self,
        *,
        tenant_id: str,
        task_id: str,
        workflow_id: str,
        step_id: str,
        attempt_id: str,
        activity_type: str,
        agent_id: str = "W_DEV",
        worker_role: str = "W_DEV",
        work_region: str = "default",
        sandbox_id: str | None = None,
        tool_id: str | None = None,
        tool_version: str | None = None,
        policy_version: str = "1.0.0",
        input_snapshot_hash: str,
        output_snapshot_hash: str | None = None,
        artifact_hashes: dict[str, str] | None = None,
        action_digest: str | None = None,
        status: str = "SUCCESS",
        trace_id: str | None = None,
        evidence_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        w3c_prov: dict[str, Any] | W3CProvBundle | None = None,
        occurred_at: datetime | None = None,
        raw_prompt: str | None = None,
        event_id: str | None = None,
    ) -> DevelopmentProvEvent:
        """Capture, cryptographically sign, and append an immutable DevelopmentProvEvent."""
        import uuid

        cleaned_metadata = _sanitize_dict(metadata or {})
        eff_evidence_ref = evidence_ref

        if raw_prompt is not None:
            prompt_hash = hashlib.sha256(raw_prompt.encode("utf-8")).hexdigest()
            eff_evidence_ref = eff_evidence_ref or f"vault://prompts/{task_id}/{step_id}/{attempt_id}/{prompt_hash[:16]}"
            cleaned_metadata["prompt_hash"] = prompt_hash
            cleaned_metadata["prompt_vault_ref"] = eff_evidence_ref
            cleaned_metadata["prompt_classification"] = "CONFIDENTIAL"

        latest = await self._repository._latest(tenant_id)
        prev_hash = latest.record_hash if latest else None

        if w3c_prov is None:
            w3c_bundle = self.build_development_w3c_prov(
                tenant_id=tenant_id,
                task_id=task_id,
                workflow_id=workflow_id,
                step_id=step_id,
                attempt_id=attempt_id,
                activity_type=activity_type,
                agent_id=agent_id,
                worker_role=worker_role,
                input_snapshot_hash=input_snapshot_hash,
                output_snapshot_hash=output_snapshot_hash,
                artifact_hashes=artifact_hashes,
                sandbox_id=sandbox_id,
                tool_id=tool_id,
                tool_version=tool_version,
                policy_version=policy_version,
                approval_token_id=cleaned_metadata.get("token_id"),
                reviewer_id=cleaned_metadata.get("reviewer_id"),
                derived_from_attempt_id=cleaned_metadata.get("derived_from_attempt_id"),
                derived_from_output_hash=cleaned_metadata.get("derived_from_output_hash"),
                started_at=occurred_at,
                ended_at=occurred_at,
                status=status,
            )
            w3c_dict = w3c_bundle.model_dump(mode="json")
        elif isinstance(w3c_prov, W3CProvBundle):
            w3c_dict = w3c_prov.model_dump(mode="json")
        else:
            w3c_dict = w3c_prov

        ev_id = event_id or f"pe-dev-{uuid.uuid4().hex[:12]}"
        now_dt = occurred_at or datetime.now(UTC)

        provisional = DevelopmentProvEvent(
            event_id=ev_id,
            task_id=task_id,
            workflow_id=workflow_id,
            step_id=step_id,
            attempt_id=attempt_id,
            tenant_id=tenant_id,
            work_region=work_region,
            agent_id=agent_id,
            worker_role=worker_role,
            activity_id=activity_type,
            sandbox_id=sandbox_id,
            tool_id=tool_id,
            tool_version=tool_version,
            policy_version=policy_version,
            input_snapshot_hash=input_snapshot_hash,
            output_snapshot_hash=output_snapshot_hash,
            artifact_hashes=artifact_hashes or {},
            action_digest=action_digest,
            occurred_at=now_dt,
            status=status,
            trace_id=trace_id or f"tr-{uuid.uuid4().hex[:16]}",
            previous_event_hash=prev_hash,
            evidence_ref=eff_evidence_ref,
            w3c_prov=w3c_dict,
            metadata=cleaned_metadata,
        )

        computed_event_hash = provisional.compute_event_hash(prev_hash)
        sig = sign_payload(provisional.canonical_bytes(), self._control_plane_key)

        event = provisional.model_copy(update={
            "event_hash": computed_event_hash,
            "control_plane_signature": sig,
        })

        repo_metadata = {
            "development_prov_event": event.model_dump(mode="json"),
            "signing_key_id": self._signing_key_id,
            "control_plane_public_key_pem": self._control_plane_public_key_pem,
            "task_id": task_id,
            "workflow_id": workflow_id,
            "step_id": step_id,
            "attempt_id": attempt_id,
            "input_snapshot_hash": input_snapshot_hash,
            "output_snapshot_hash": output_snapshot_hash,
            "event_hash": computed_event_hash,
            "control_plane_signature": sig,
            **cleaned_metadata,
        }

        await self._repository.append(
            tenant_id=tenant_id,
            entity_id=f"development_task:{task_id}:{step_id}",
            activity=f"development:{activity_type}",
            agent=f"worker:{agent_id}",
            record_id=ev_id,
            metadata=repo_metadata,
            w3c_prov=w3c_dict,
        )

        return event

    def generate_slsa_attestation(
        self,
        *,
        task_id: str,
        step_id: str,
        attempt_id: str,
        builder_id: str = "urn:enterprise_os:builder:W_DEV:v1",
        artifacts: dict[str, str] | None = None,
        resolved_dependencies: list[dict[str, Any]] | None = None,
        build_config: dict[str, Any] | None = None,
        completed_at: datetime | None = None,
    ) -> InTotoStatement:
        """Generate a SLSA v1.0 / in-toto statement attestation for sealed release artifacts."""
        subjects = [
            SlsaResourceDescriptor(
                name=name,
                digest={"sha256": hsh},
                annotations={"step_id": step_id, "attempt_id": attempt_id},
            )
            for name, hsh in (artifacts or {}).items()
        ]

        deps: list[SlsaResourceDescriptor] = []
        if resolved_dependencies:
            for dep in resolved_dependencies:
                deps.append(
                    SlsaResourceDescriptor(
                        name=dep.get("name", "dep"),
                        digest=dep.get("digest", {}),
                        annotations=dep.get("annotations", {}),
                    )
                )

        predicate = SlsaProvenancePredicate(
            buildDefinition=SlsaBuildDefinition(
                buildType="https://enterprise_os.dev/attestations/development_engine/v1",
                externalParameters={
                    "task_id": task_id,
                    "step_id": step_id,
                    "attempt_id": attempt_id,
                    "build_config": build_config or {},
                },
                resolvedDependencies=deps,
            ),
            runDetails=SlsaRunDetails(
                builder=SlsaBuilder(id=builder_id),
                metadata={
                    "task_id": task_id,
                    "step_id": step_id,
                    "attempt_id": attempt_id,
                    "completed_at": (completed_at or datetime.now(UTC)).isoformat(),
                    "signing_key_id": self._signing_key_id,
                },
            ),
        )

        return InTotoStatement(
            subject=subjects,
            predicate=predicate,
        )

    async def reconstruct_development_lineage(
        self,
        tenant_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        """Reconstruct the end-to-end W3C PROV and cryptographic event lineage for a development task."""
        chain = await self._repository.chain(tenant_id)
        matching_records = [
            rec
            for rec in chain
            if rec.metadata.get("task_id") == task_id
            or rec.metadata.get("development_prov_event", {}).get("task_id") == task_id
            or f":{task_id}:" in rec.entity_id
            or rec.entity_id.endswith(f":{task_id}")
        ]

        if not matching_records:
            return {
                "task_id": task_id,
                "found": False,
                "events": [],
                "event_count": 0,
                "is_hash_chain_verified": False,
            }

        events: list[DevelopmentProvEvent] = []
        signatures_valid = True
        for rec in matching_records:
            ev_data = rec.metadata.get("development_prov_event")
            if ev_data and isinstance(ev_data, dict):
                ev = DevelopmentProvEvent.model_validate(ev_data)
                events.append(ev)
                if not ev.verify_signature(public_key_pem=self._control_plane_public_key_pem):
                    signatures_valid = False

        dev_chain_valid = True
        for ev in events:
            expected = ev.compute_event_hash(ev.previous_event_hash)
            if expected != ev.event_hash:
                dev_chain_valid = False

        steps = sorted(list({ev.step_id for ev in events}))
        attempts = sorted(list({ev.attempt_id for ev in events}))
        all_artifacts: dict[str, str] = {}
        for ev in events:
            all_artifacts.update(ev.artifact_hashes)

        return {
            "task_id": task_id,
            "found": True,
            "events": [ev.model_dump(mode="json") for ev in events],
            "event_count": len(events),
            "record_count": len(matching_records),
            "steps": steps,
            "attempts": attempts,
            "artifacts": all_artifacts,
            "signatures_verified": signatures_valid,
            "development_chain_verified": dev_chain_valid,
            "repository_chain_verified": self._repository.verify(chain),
            "w3c_prov_bundles": [rec.w3c_prov for rec in matching_records if rec.w3c_prov],
        }