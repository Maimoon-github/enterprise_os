"""Records immutable entity/activity/agent audit lineage with W3C PROV compliance."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from app.persistence.repositories.provenance import ProvenanceRepository
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
        if isinstance(v, str):
            cleaned[k] = _sanitize_text(v)
        elif isinstance(v, dict):
            cleaned[k] = _sanitize_dict(v)
        elif isinstance(v, list):
            cleaned[k] = [_sanitize_text(item) if isinstance(item, str) else item for item in v]
        else:
            cleaned[k] = v
    return cleaned


class ProvenanceRecorder:
    """Service boundary over ``ProvenanceRepository`` for W3C PROV audit capture."""

    def __init__(self, repository: ProvenanceRepository) -> None:
        self._repository = repository

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
    ) -> ProvenanceRecord:
        """Append and return a new hash-chained provenance record."""
        return await self._repository.append(
            tenant_id=tenant_id,
            entity_id=entity_id,
            activity=activity,
            agent=agent,
            record_id=record_id,
            metadata=metadata,
            w3c_prov=w3c_prov,
        )

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