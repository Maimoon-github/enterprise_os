"""Validates end-to-end W3C PROV audit lineage, ledger integrity, and CTS state reconciliation."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from app.core.exceptions import PolicyViolationError
from app.persistence.repositories.provenance import (
    _compute_hash,
    _compute_metadata_hash,
)
from app.schemas.governance import WorkerRole
from app.schemas.provenance import (
    AuditLineageStage,
    AuditValidationFinding,
    AuditValidationReport,
    ProvenanceRecord,
)
from app.schemas.task_state import CanonicalTaskState, TaskStatus
from app.security.authorization_boundary import CallerIdentity
from app.security.cryptographic_validator import CryptographicValidator

if TYPE_CHECKING:
    from app.persistence.repositories.provenance import ProvenanceRepository
    from app.services.provenance import ProvenanceRecorder
    from app.services.task_state import TaskStateService

logger = logging.getLogger(__name__)


class AuditLineageValidator:
    """Orchestrator-level validator for end-to-end audit lineage, hash chain integrity, and CTS reconciliation (T33)."""

    def __init__(
        self,
        provenance_repository: ProvenanceRepository,
        *,
        provenance_recorder: ProvenanceRecorder | None = None,
        task_state_service: TaskStateService | None = None,
        crypto_validator: CryptographicValidator | None = None,
    ) -> None:
        self._provenance_repository = provenance_repository
        self._provenance_recorder = provenance_recorder
        self._task_state_service = task_state_service
        self._crypto_validator = crypto_validator

    async def validate_lineage_and_integrity(
        self,
        tenant_id: str,
        *,
        task_states: dict[str, CanonicalTaskState],
        caller: CallerIdentity,
        governing_task_id: str = "task-t33",
        record_audit_event: bool = True,
    ) -> AuditValidationReport:
        """Perform full end-to-end audit lineage, hash chain, cryptographic, and CTS validation."""
        validation_id = f"val-t33-{uuid.uuid4().hex[:8]}"
        findings: list[AuditValidationFinding] = []
        detected_gaps: list[str] = []
        stages_verified: set[str] = set()

        # -------------------------------------------------------------------
        # 1. Verify Caller Authority (Model A: No Worker/Specialist Execution)
        # -------------------------------------------------------------------
        subj_lower = caller.subject.lower()
        if (
            caller.subject.startswith("W_")
            or caller.subject.startswith("S_")
            or "worker" in subj_lower
            or "specialist" in subj_lower
        ):
            raise PolicyViolationError(
                "Direct worker execution of T33 audit lineage validation forbidden; must be executed by orchestrator or auditor"
            )

        if caller.tenant_scope.tenant_id != tenant_id and caller.tenant_scope.tenant_id != "*":
            raise ValueError(
                f"Caller tenant scope '{caller.tenant_scope.tenant_id}' does not match validation tenant '{tenant_id}'"
            )

        # -------------------------------------------------------------------
        # 2. Verify Authoritative T30 and T31 Dependencies
        # -------------------------------------------------------------------
        t30_task = task_states.get("task-t30")
        t30_status = "MISSING"
        if not t30_task:
            detected_gaps.append("Missing prerequisite task-t30 (live operational telemetry ingestion)")
            findings.append(
                AuditValidationFinding(
                    stage=AuditLineageStage.TELEMETRY_T30.value,
                    entity_id="task-t30",
                    status="GAP",
                    details="Prerequisite task-t30 not found in CTS",
                )
            )
        elif t30_task.status != TaskStatus.COMPLETED or not t30_task.governance_approved:
            t30_status = str(t30_task.status)
            detected_gaps.append(
                f"Prerequisite task-t30 is not authoritatively accepted (status={t30_task.status}, approved={t30_task.governance_approved})"
            )
            findings.append(
                AuditValidationFinding(
                    stage=AuditLineageStage.TELEMETRY_T30.value,
                    entity_id="task-t30",
                    status="GAP",
                    details=f"task-t30 status={t30_task.status}, approved={t30_task.governance_approved}",
                )
            )
        else:
            t30_status = "ACCEPTED"
            stages_verified.add(AuditLineageStage.TELEMETRY_T30.value)

        t31_task = task_states.get("task-t31")
        t31_status = "MISSING"
        if not t31_task:
            detected_gaps.append("Missing prerequisite task-t31 (attribution, decay & ROAS modeling)")
            findings.append(
                AuditValidationFinding(
                    stage=AuditLineageStage.LEARNING_T31.value,
                    entity_id="task-t31",
                    status="GAP",
                    details="Prerequisite task-t31 not found in CTS",
                )
            )
        elif t31_task.status != TaskStatus.COMPLETED or not t31_task.governance_approved:
            t31_status = str(t31_task.status)
            detected_gaps.append(
                f"Prerequisite task-t31 is not authoritatively accepted (status={t31_task.status}, approved={t31_task.governance_approved})"
            )
            findings.append(
                AuditValidationFinding(
                    stage=AuditLineageStage.LEARNING_T31.value,
                    entity_id="task-t31",
                    status="GAP",
                    details=f"task-t31 status={t31_task.status}, approved={t31_task.governance_approved}",
                )
            )
        else:
            t31_status = "ACCEPTED"
            stages_verified.add(AuditLineageStage.LEARNING_T31.value)

        # -------------------------------------------------------------------
        # 3. Assemble Audit Scope & Fetch Provenance Chain
        # -------------------------------------------------------------------
        chain = await self._provenance_repository.chain(tenant_id)
        if not chain:
            detected_gaps.append(f"Provenance chain for tenant '{tenant_id}' is empty")

        # -------------------------------------------------------------------
        # 4. Ledger Integrity: Sequence, Hashes, and Previous-Hash Continuity
        # -------------------------------------------------------------------
        hash_chain_verified = True
        prev_hash: str | None = None
        seen_record_ids: set[str] = set()

        for idx, rec in enumerate(chain):
            # Check for duplicate record IDs
            if rec.record_id in seen_record_ids:
                hash_chain_verified = False
                detected_gaps.append(f"Duplicate record ID '{rec.record_id}' detected at chain index {idx}")
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="TAMPERED",
                        details=f"Duplicate record ID {rec.record_id}",
                    )
                )
            seen_record_ids.add(rec.record_id)

            # Check tenant isolation
            if rec.tenant_id != tenant_id:
                hash_chain_verified = False
                detected_gaps.append(
                    f"Cross-tenant record leak detected: record '{rec.record_id}' belongs to tenant '{rec.tenant_id}', expected '{tenant_id}'"
                )
                findings.append(
                    AuditValidationFinding(
                        stage="tenant_isolation",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="MISMATCH",
                        details=f"Cross-tenant leak: record tenant '{rec.tenant_id}' != '{tenant_id}'",
                    )
                )

            # Recompute metadata hash
            recomputed_meta_hash = _compute_metadata_hash(rec.metadata, rec.w3c_prov)
            if rec.metadata_hash != recomputed_meta_hash:
                hash_chain_verified = False
                detected_gaps.append(
                    f"Metadata/payload hash mismatch for record '{rec.record_id}' (tampered payload)"
                )
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="TAMPERED",
                        details="Metadata hash does not match payload",
                    )
                )

            # Verify previous-hash continuity
            if rec.prev_record_hash != prev_hash:
                hash_chain_verified = False
                detected_gaps.append(
                    f"Broken previous-hash continuity at record '{rec.record_id}': expected '{prev_hash}', got '{rec.prev_record_hash}'"
                )
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="TAMPERED",
                        details=f"Broken previous-hash: expected {prev_hash}, got {rec.prev_record_hash}",
                    )
                )

            # Recompute record hash
            expected_record_hash = _compute_hash(
                prev_hash,
                rec.entity_id,
                rec.activity,
                rec.agent,
                rec.occurred_at,
                recomputed_meta_hash,
            )
            if rec.record_hash != expected_record_hash:
                hash_chain_verified = False
                detected_gaps.append(
                    f"Record hash mismatch for record '{rec.record_id}' (tampered header/hash)"
                )
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="TAMPERED",
                        details="Record hash recomputation failed",
                    )
                )

            # Check chronological sequence
            if idx > 0 and rec.occurred_at < chain[idx - 1].occurred_at:
                hash_chain_verified = False
                detected_gaps.append(
                    f"Reordered records detected: record '{rec.record_id}' occurred before preceding record"
                )
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="TAMPERED",
                        details="Out-of-order timestamp sequence",
                    )
                )

            prev_hash = rec.record_hash

        # -------------------------------------------------------------------
        # 5. W3C PROV Graph Validation: Entity-Activity-Agent Relationships
        # -------------------------------------------------------------------
        prov_graph_valid = True
        for rec in chain:
            if not rec.w3c_prov:
                continue

            bundle = rec.w3c_prov
            activities = {a.get("id") for a in bundle.get("activities", []) if isinstance(a, dict)}
            agents = {ag.get("id") for ag in bundle.get("agents", []) if isinstance(ag, dict)}
            entities = {e.get("id") for e in bundle.get("entities", []) if isinstance(e, dict)}
            known_nodes = activities | agents | entities

            for rel in bundle.get("relations", []):
                if not isinstance(rel, dict):
                    continue
                src = rel.get("source_id")
                tgt = rel.get("target_id")
                rel_type = rel.get("relation_type")

                # Verify source and target resolve within bundle or global urns
                if src and src not in known_nodes and not src.startswith("urn:enterprise_os:"):
                    prov_graph_valid = False
                    detected_gaps.append(f"Orphan relation source '{src}' in record '{rec.record_id}'")
                    findings.append(
                        AuditValidationFinding(
                            stage="w3c_prov",
                            entity_id=rec.entity_id,
                            activity=rec.activity,
                            status="GAP",
                            details=f"Orphan relation source: {src}",
                        )
                    )

                if tgt and tgt not in known_nodes and not tgt.startswith("urn:enterprise_os:"):
                    prov_graph_valid = False
                    detected_gaps.append(f"Orphan relation target '{tgt}' in record '{rec.record_id}'")
                    findings.append(
                        AuditValidationFinding(
                            stage="w3c_prov",
                            entity_id=rec.entity_id,
                            activity=rec.activity,
                            status="GAP",
                            details=f"Orphan relation target: {tgt}",
                        )
                    )

                # Verify cross-tenant isolation in entities / agents attributes
                for node in bundle.get("entities", []) + bundle.get("agents", []):
                    if isinstance(node, dict):
                        attrs = node.get("attributes", {})
                        if "tenant_id" in attrs and attrs["tenant_id"] != tenant_id:
                            prov_graph_valid = False
                            detected_gaps.append(
                                f"Cross-tenant node attribute '{attrs['tenant_id']}' in record '{rec.record_id}'"
                            )
                            findings.append(
                                AuditValidationFinding(
                                    stage="w3c_prov",
                                    entity_id=rec.entity_id,
                                    activity=rec.activity,
                                    status="MISMATCH",
                                    details=f"Cross-tenant node attribute: {attrs['tenant_id']}",
                                )
                            )

        # -------------------------------------------------------------------
        # 6. Cryptographic Signatures Validation
        # -------------------------------------------------------------------
        signatures_verified = True
        # Inspect task states for clearance or dispatch signatures
        for tid, task in task_states.items():
            cts = task.cts_state
            # Check clearances in CTS
            clearances = cts.get("clearances", [])
            if isinstance(clearances, list):
                for cl in clearances:
                    if isinstance(cl, dict) and "signature" in cl and "public_key_pem" in cl:
                        sig = cl["signature"]
                        pub_pem = cl["public_key_pem"]
                        canon_bytes = cl.get("canonical_bytes")
                        if not sig or not pub_pem:
                            signatures_verified = False
                            detected_gaps.append(f"Missing signature/public key in clearance for task '{tid}'")
                        elif canon_bytes:
                            # Re-verify
                            validator = self._crypto_validator or CryptographicValidator(public_key_pem=pub_pem)
                            try:
                                b_payload = canon_bytes.encode("utf-8") if isinstance(canon_bytes, str) else bytes(canon_bytes)
                                if not validator.verify(b_payload, sig):
                                    signatures_verified = False
                                    detected_gaps.append(f"Cryptographic signature verification failed for task '{tid}'")
                                    findings.append(
                                        AuditValidationFinding(
                                            stage=AuditLineageStage.HITL_APPROVAL.value,
                                            entity_id=tid,
                                            status="INVALID_SIGNATURE",
                                            details=f"Invalid signature on clearance for task {tid}",
                                        )
                                    )
                            except Exception as exc:
                                signatures_verified = False
                                detected_gaps.append(f"Signature evaluation error for task '{tid}': {exc}")

        # -------------------------------------------------------------------
        # 7. Cross-Check CTS Reconciliation
        # -------------------------------------------------------------------
        cts_reconciled = True
        activity_set = {r.activity.lower() for r in chain}
        agent_set = {r.agent.lower() for r in chain}
        entity_set = {r.entity_id for r in chain}

        # Verify completed tasks have corresponding provenance trail
        for tid, task in task_states.items():
            if task.status == TaskStatus.COMPLETED:
                # Check if task ID or associated entity appears in provenance
                task_in_entities = any(tid in e for e in entity_set)
                task_in_metadata = any(
                    r.metadata.get("task_id") == tid or r.metadata.get("source_task_id") == tid for r in chain
                )
                if not task_in_entities and not task_in_metadata:
                    cts_reconciled = False
                    detected_gaps.append(
                        f"CTS reconciliation gap: completed task '{tid}' has no corresponding audit records in provenance chain"
                    )
                    findings.append(
                        AuditValidationFinding(
                            stage="cts_reconciliation",
                            entity_id=tid,
                            status="MISMATCH",
                            details=f"Completed task {tid} has no provenance record",
                        )
                    )

        # Classify stages verified from provenance chain
        for act in activity_set:
            if "directive" in act or "policy" in act:
                stages_verified.add(AuditLineageStage.GOVERNANCE.value)
            if "grant" in act or "plan" in act or "context" in act:
                stages_verified.add(AuditLineageStage.ORCHESTRATION.value)
            if "vector" in act or "rag" in act:
                stages_verified.add(AuditLineageStage.RAG.value)
            if "sandbox" in act or "worker" in act:
                stages_verified.add(AuditLineageStage.WORKER_SANDBOX.value)
            if "hitl" in act or "approval" in act:
                stages_verified.add(AuditLineageStage.HITL_APPROVAL.value)
            if "dispatch" in act or "actuation" in act:
                stages_verified.add(AuditLineageStage.MCP_ACTUATION.value)
            if "telemetry" in act:
                stages_verified.add(AuditLineageStage.TELEMETRY_T30.value)
            if "attribution" in act or "decay" in act:
                stages_verified.add(AuditLineageStage.LEARNING_T31.value)
            if "development" in act or "dev_" in act or "w_dev" in act:
                stages_verified.add(AuditLineageStage.DEVELOPMENT_ENGINE.value)

        # -------------------------------------------------------------------
        # 8. Determine Overall Validation Status
        # -------------------------------------------------------------------
        is_valid = (
            t30_status == "ACCEPTED"
            and t31_status == "ACCEPTED"
            and hash_chain_verified
            and prov_graph_valid
            and signatures_verified
            and cts_reconciled
            and len(chain) > 0
            and len(detected_gaps) == 0
        )

        report = AuditValidationReport(
            validation_id=validation_id,
            tenant_id=tenant_id,
            is_valid=is_valid,
            t30_status=t30_status,
            t31_status=t31_status,
            chain_length=len(chain),
            hash_chain_verified=hash_chain_verified,
            signatures_verified=signatures_verified,
            cts_reconciled=cts_reconciled,
            prov_graph_valid=prov_graph_valid,
            stages_verified=sorted(list(stages_verified)),
            detected_gaps=detected_gaps,
            findings=findings,
            t34_audit_eligible=is_valid,
        )

        # -------------------------------------------------------------------
        # 9. Record T33 Result (Auditable Record Without History Rewriting)
        # -------------------------------------------------------------------
        if record_audit_event and self._provenance_recorder is not None:
            try:
                act = "audit_lineage_validated" if is_valid else "audit_lineage_validation_failed"
                await self._provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=f"audit_validation:{validation_id}",
                    activity=act,
                    agent="W3C_PROV_AUDITOR",
                    metadata={
                        "validation_id": validation_id,
                        "is_valid": is_valid,
                        "chain_length": len(chain),
                        "t30_status": t30_status,
                        "t31_status": t31_status,
                        "t34_eligible": is_valid,
                        "gaps_count": len(detected_gaps),
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record T33 audit event: %s", exc)

        # -------------------------------------------------------------------
        # 10. Update CTS State for Task-33
        # -------------------------------------------------------------------
        if governing_task_id in task_states:
            t33_task = task_states[governing_task_id]
            t33_task.status = TaskStatus.COMPLETED if is_valid else TaskStatus.FAILED
            t33_task.cts_state["audit_validation_id"] = validation_id
            t33_task.cts_state["is_valid"] = is_valid
            t33_task.cts_state["t34_ready"] = is_valid
            t33_task.cts_state["stages_verified"] = list(stages_verified)
            if self._task_state_service is not None:
                try:
                    await self._task_state_service.save_state(tenant_id, t33_task)
                except Exception as exc:
                    logger.warning("Failed to save CTS state for %s: %s", governing_task_id, exc)

        return report

    async def validate_development_lineage(
        self,
        tenant_id: str,
        task_id: str,
        *,
        caller: CallerIdentity | None = None,
        expected_deliverable_hash: str | None = None,
    ) -> AuditValidationReport:
        """Validate end-to-end W3C PROV lineage, hash chain, and Ed25519 signatures for W_DEV."""
        validation_id = f"val-dev-{uuid.uuid4().hex[:8]}"
        findings: list[AuditValidationFinding] = []
        detected_gaps: list[str] = []
        stages_verified: set[str] = set()

        if caller is not None:
            if caller.tenant_scope.tenant_id != tenant_id and caller.tenant_scope.tenant_id != "*":
                raise ValueError(
                    f"Caller tenant scope '{caller.tenant_scope.tenant_id}' does not match validation tenant '{tenant_id}'"
                )

        chain = await self._provenance_repository.chain(tenant_id)
        if not chain:
            detected_gaps.append(f"Provenance chain for tenant '{tenant_id}' is empty")

        hash_chain_verified = True
        prev_hash: str | None = None
        seen_record_ids: set[str] = set()

        for idx, rec in enumerate(chain):
            if rec.record_id in seen_record_ids:
                hash_chain_verified = False
                detected_gaps.append(f"Duplicate record ID '{rec.record_id}' detected at chain index {idx}")
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="TAMPERED",
                        details=f"Duplicate record ID {rec.record_id}",
                    )
                )
            seen_record_ids.add(rec.record_id)

            if rec.tenant_id != tenant_id:
                hash_chain_verified = False
                detected_gaps.append(f"Cross-tenant record leak: '{rec.tenant_id}' != '{tenant_id}'")
                findings.append(
                    AuditValidationFinding(
                        stage="tenant_isolation",
                        entity_id=rec.entity_id,
                        status="MISMATCH",
                        details=f"Record tenant '{rec.tenant_id}' != '{tenant_id}'",
                    )
                )

            recomputed_meta_hash = _compute_metadata_hash(rec.metadata, rec.w3c_prov)
            if rec.metadata_hash != recomputed_meta_hash:
                hash_chain_verified = False
                detected_gaps.append(f"Metadata hash mismatch for record '{rec.record_id}'")
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="TAMPERED",
                        details="Metadata hash does not match payload",
                    )
                )

            if rec.prev_record_hash != prev_hash:
                hash_chain_verified = False
                detected_gaps.append(f"Broken previous-hash continuity at record '{rec.record_id}'")
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="TAMPERED",
                        details=f"Broken previous-hash: expected {prev_hash}, got {rec.prev_record_hash}",
                    )
                )

            expected_record_hash = _compute_hash(
                prev_hash,
                rec.entity_id,
                rec.activity,
                rec.agent,
                rec.occurred_at,
                recomputed_meta_hash,
            )
            if rec.record_hash != expected_record_hash:
                hash_chain_verified = False
                detected_gaps.append(f"Record hash mismatch for record '{rec.record_id}'")
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        activity=rec.activity,
                        status="TAMPERED",
                        details="Record hash recomputation failed",
                    )
                )

            if idx > 0 and rec.occurred_at < chain[idx - 1].occurred_at:
                hash_chain_verified = False
                detected_gaps.append(f"Out-of-order timestamp sequence at record '{rec.record_id}'")
                findings.append(
                    AuditValidationFinding(
                        stage="ledger_integrity",
                        entity_id=rec.entity_id,
                        status="TAMPERED",
                        details="Out-of-order timestamp sequence",
                    )
                )

            prev_hash = rec.record_hash

        # Filter records relevant to this development task
        dev_records = [
            rec
            for rec in chain
            if rec.metadata.get("task_id") == task_id
            or rec.metadata.get("development_prov_event", {}).get("task_id") == task_id
            or f":{task_id}:" in rec.entity_id
            or rec.entity_id.endswith(f":{task_id}")
        ]

        if not dev_records:
            detected_gaps.append(f"No development provenance records found for task '{task_id}'")

        signatures_verified = True
        prov_graph_valid = True
        deliverable_found = False

        from app.schemas.development.provenance import DevelopmentProvEvent

        for rec in dev_records:
            stages_verified.add(AuditLineageStage.DEVELOPMENT_ENGINE.value)
            dev_ev_dict = rec.metadata.get("development_prov_event")
            if dev_ev_dict and isinstance(dev_ev_dict, dict):
                try:
                    dev_ev = DevelopmentProvEvent.model_validate(dev_ev_dict)
                    pub_pem = rec.metadata.get("control_plane_public_key_pem")

                    # Check event hash
                    expected_ev_hash = dev_ev.compute_event_hash(dev_ev.previous_event_hash)
                    if dev_ev.event_hash != expected_ev_hash:
                        hash_chain_verified = False
                        detected_gaps.append(f"Development event hash mismatch on event '{dev_ev.event_id}'")
                        findings.append(
                            AuditValidationFinding(
                                stage=AuditLineageStage.DEVELOPMENT_ENGINE.value,
                                entity_id=dev_ev.event_id,
                                status="TAMPERED",
                                details="Computed event hash does not match stored event_hash",
                            )
                        )

                    # Check signature
                    if not dev_ev.control_plane_signature:
                        signatures_verified = False
                        detected_gaps.append(f"Missing control-plane signature on event '{dev_ev.event_id}'")
                        findings.append(
                            AuditValidationFinding(
                                stage=AuditLineageStage.DEVELOPMENT_ENGINE.value,
                                entity_id=dev_ev.event_id,
                                status="INVALID_SIGNATURE",
                                details="Missing control-plane signature",
                            )
                        )
                    elif not dev_ev.verify_signature(public_key_pem=pub_pem, validator=self._crypto_validator):
                        signatures_verified = False
                        detected_gaps.append(f"Cryptographic signature verification failed for event '{dev_ev.event_id}'")
                        findings.append(
                            AuditValidationFinding(
                                stage=AuditLineageStage.DEVELOPMENT_ENGINE.value,
                                entity_id=dev_ev.event_id,
                                status="INVALID_SIGNATURE",
                                details="Ed25519 signature invalid over canonical bytes",
                            )
                        )

                    # Check expected deliverable hash
                    if expected_deliverable_hash and dev_ev.output_snapshot_hash == expected_deliverable_hash:
                        deliverable_found = True

                except Exception as exc:
                    signatures_verified = False
                    detected_gaps.append(f"Failed to validate development event in record '{rec.record_id}': {exc}")

            # Sensitive text & prompt privacy check
            meta_str = str(rec.metadata).lower()
            if "raw_prompt" in rec.metadata or ("bearer " in meta_str and "[redacted]" not in meta_str):
                detected_gaps.append(f"Sensitive unredacted data detected in record '{rec.record_id}'")
                findings.append(
                    AuditValidationFinding(
                        stage=AuditLineageStage.DEVELOPMENT_ENGINE.value,
                        entity_id=rec.record_id,
                        status="TAMPERED",
                        details="Sensitive plaintext prompt or token present in immutable metadata",
                    )
                )

            # W3C PROV graph validation
            if rec.w3c_prov:
                bundle = rec.w3c_prov
                entities = {
                    e.get("id")
                    for e in bundle.get("entities", [])
                    if isinstance(e, dict) and isinstance(e.get("id"), str)
                }
                relations = bundle.get("relations", [])
                has_candidate = any(isinstance(e, str) and ":entity:candidate:" in e for e in entities)
                if has_candidate:
                    # Verify derivation linkage
                    has_derivation = any(
                        r.get("relation_type") == "prov:wasDerivedFrom" for r in relations if isinstance(r, dict)
                    )
                    if not has_derivation:
                        prov_graph_valid = False
                        detected_gaps.append(f"Candidate output missing wasDerivedFrom relation in record '{rec.record_id}'")
                        findings.append(
                            AuditValidationFinding(
                                stage="w3c_prov",
                                entity_id=rec.entity_id,
                                status="GAP",
                                details="Candidate deliverable missing prov:wasDerivedFrom linkage to input snapshot",
                            )
                        )

        if expected_deliverable_hash and not deliverable_found:
            detected_gaps.append(f"Expected deliverable hash '{expected_deliverable_hash}' not found in task provenance")
            findings.append(
                AuditValidationFinding(
                    stage=AuditLineageStage.DEVELOPMENT_ENGINE.value,
                    entity_id=task_id,
                    status="GAP",
                    details=f"Expected deliverable hash {expected_deliverable_hash} missing",
                )
            )

        is_valid = (
            hash_chain_verified
            and prov_graph_valid
            and signatures_verified
            and len(dev_records) > 0
            and len(detected_gaps) == 0
        )

        return AuditValidationReport(
            validation_id=validation_id,
            tenant_id=tenant_id,
            is_valid=is_valid,
            t30_status="SKIPPED",
            t31_status="SKIPPED",
            chain_length=len(chain),
            hash_chain_verified=hash_chain_verified,
            signatures_verified=signatures_verified,
            cts_reconciled=len(dev_records) > 0,
            prov_graph_valid=prov_graph_valid,
            stages_verified=sorted(list(stages_verified)),
            detected_gaps=detected_gaps,
            findings=findings,
            t34_audit_eligible=is_valid,
        )
