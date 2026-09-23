"""LEARN-TELEMETRY: Specialist sub-agent for telemetry validation, normalization, and dataset manifests."""

from __future__ import annotations

import json
from typing import Any

from app.core.exceptions import AuthorizationError, PolicyViolationError
from app.integrations.sandbox.s_attr_core import validate_and_normalize_telemetry
from app.schemas.agent_contracts import TaskGrant
from app.schemas.learning_performance import (
    LearningDatasetManifest,
    LearningSpecialistResult,
    SpecialistStatus,
)


class LearningTelemetryAgent:
    """Specialist sub-agent for validating and normalizing raw telemetry snapshots into immutable datasets."""

    specialist_id = "LEARN-TELEMETRY"
    profile_id = "learn.telemetry.v1"

    def __init__(self, sandbox_client: Any = None, llm_client: Any = None) -> None:
        self._sandbox_client = sandbox_client
        self._llm_client = llm_client

    async def run(
        self,
        grant: TaskGrant,
        context: dict[str, Any],
        *,
        attempt_id: str | None = None,
    ) -> tuple[LearningDatasetManifest | None, LearningSpecialistResult]:
        """Execute telemetry validation and normalization under Model A governance.

        Materializes authorized data inside the specialist execution attempt.
        Never returns raw event rows to the caller/parent.
        """
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        task_id = grant.task_id

        # Context payload assembly
        events = context.get("events") or context.get("raw_events") or grant.cts_state.get("raw_events") or []

        payload: dict[str, Any] = {
            "task_id": task_id,
            "tenant_id": grant_tenant,
            "brand_id": context.get("brand_id") or grant.cts_state.get("brand_id"),
            "operation": "normalize_telemetry",
            "events": events,
            "window_start": context.get("window_start") or grant.cts_state.get("window_start"),
            "window_end": context.get("window_end") or grant.cts_state.get("window_end"),
            "allowed_lookback_days": context.get("allowed_lookback_days", 30),
        }

        # Execute normalization via deterministic S_ATTR core / sandbox runner
        res = validate_and_normalize_telemetry(payload)
        status = res.get("status")

        if status == "failed":
            err_cat = res.get("error_category", "validation_failed")
            err_msg = res.get("error", "Telemetry validation failed")
            result = LearningSpecialistResult(
                role=self.specialist_id,
                specialist_profile_id=self.profile_id,
                attempt_id=attempt_id or f"att-{task_id[:8]}",
                dataset_version="none",
                status=SpecialistStatus.FAILED,
                error_category=err_cat,
                findings=[err_msg],
            )
            return None, result

        if status == "insufficient_evidence":
            err_msg = res.get("error", "Insufficient valid telemetry")
            result = LearningSpecialistResult(
                role=self.specialist_id,
                specialist_profile_id=self.profile_id,
                attempt_id=attempt_id or f"att-{task_id[:8]}",
                dataset_version="none",
                status=SpecialistStatus.INSUFFICIENT_EVIDENCE,
                insufficient_evidence_reason=err_msg,
                findings=[err_msg],
            )
            return None, result

        # Parse strongly-typed manifest
        raw_manifest = res.get("manifest", {})
        manifest = LearningDatasetManifest.model_validate(raw_manifest)

        findings = [
            f"Validated {manifest.row_count} telemetry records with content hash {manifest.content_hash[:12]}.",
            f"Coverage: {manifest.identity_coverage * 100:.1f}%. Duplicates filtered: {manifest.duplicate_count}. Quarantined: {manifest.quarantine_count}.",
        ]

        result = LearningSpecialistResult(
            role=self.specialist_id,
            specialist_profile_id=self.profile_id,
            attempt_id=attempt_id or f"att-{task_id[:8]}",
            dataset_version=manifest.version,
            status=SpecialistStatus.COMPLETE,
            findings=findings,
            diagnostic_refs=[f"diag-{manifest.artifact_id}"],
            provenance_refs=manifest.lineage,
        )

        return manifest, result
