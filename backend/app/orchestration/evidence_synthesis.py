"""Consolidates worker evidence and confidence intervals."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from datetime import UTC, datetime
from typing import Any

from app.schemas.agent_contracts import (
    CandidateStateDelta,
    ConfidenceInterval,
    ConflictSeverity,
    ConsolidatedConfidenceSummary,
    ConsolidatedEvidencePackage,
    ConsolidatedPackageStatus,
    CreativePackage,
    DevelopmentDeliverable,
    EvidenceConflict,
    EvidenceEnvelope,
    OmnichannelStrategyPlan,
    RejectedEvidenceItem,
)
from app.schemas.artifact import ArtifactReference
from app.schemas.governance import WorkerRole
from app.schemas.task_state import TaskStatus


class SynthesizedEvidence:
    """The consolidated result of merging one or more evidence envelopes."""

    def __init__(
        self,
        task_id: str,
        evidence: list[str],
        confidence: ConfidenceInterval,
        package: ConsolidatedEvidencePackage | None = None,
    ) -> None:
        self.task_id = task_id
        self.evidence = evidence
        self.confidence = confidence
        self.package = package


class EvidenceSynthesizer:
    """Merges and consolidates evidence envelopes with strict validation and conflict detection."""

    def synthesize(self, envelopes: list[EvidenceEnvelope]) -> SynthesizedEvidence:
        """Return a single ``SynthesizedEvidence`` from one or more envelopes.

        Maintains backward compatibility with callers and downstream previews.
        Raises ``ValueError`` if ``envelopes`` is empty.
        """

        if not envelopes:
            raise ValueError("Cannot synthesize evidence from an empty envelope list.")

        task_id = envelopes[0].task_id
        total_weight = sum(env.confidence.point_estimate for env in envelopes) or 1.0

        weighted_point = sum(
            env.confidence.point_estimate * env.confidence.point_estimate for env in envelopes
        ) / total_weight
        weighted_lower = sum(
            env.confidence.lower_bound * env.confidence.point_estimate for env in envelopes
        ) / total_weight
        weighted_upper = sum(
            env.confidence.upper_bound * env.confidence.point_estimate for env in envelopes
        ) / total_weight

        merged_evidence: list[str] = []
        for env in envelopes:
            merged_evidence.extend(env.evidence)

        return SynthesizedEvidence(
            task_id=task_id,
            evidence=merged_evidence,
            confidence=ConfidenceInterval(
                point_estimate=weighted_point,
                lower_bound=weighted_lower,
                upper_bound=weighted_upper,
            ),
        )

    def validate_confidence(self, confidence: ConfidenceInterval) -> tuple[bool, str | None]:
        """Verify numerical bounds, consistency, and completeness of a confidence interval."""
        point = confidence.point_estimate
        lower = confidence.lower_bound
        upper = confidence.upper_bound

        if any(math.isnan(v) or math.isinf(v) for v in (point, lower, upper)):
            return False, f"Non-finite confidence value: point={point}, lower={lower}, upper={upper}"
        if not (0.0 <= point <= 1.0):
            return False, f"Point estimate {point} out of [0.0, 1.0] bounds"
        if not (0.0 <= lower <= 1.0):
            return False, f"Lower bound {lower} out of [0.0, 1.0] bounds"
        if not (0.0 <= upper <= 1.0):
            return False, f"Upper bound {upper} out of [0.0, 1.0] bounds"
        if lower > upper:
            return False, f"Inverted confidence interval: lower_bound ({lower}) > upper_bound ({upper})"
        if point < lower or point > upper:
            return False, f"Point estimate ({point}) outside interval [{lower}, {upper}]"

        return True, None

    def consolidate(
        self,
        envelopes: list[EvidenceEnvelope],
        *,
        expected_tenant_id: str | None = None,
        required_roles: list[WorkerRole] | None = None,
        directive_id: str | None = None,
    ) -> ConsolidatedEvidencePackage:
        """Consolidate evidence envelopes across tasks (T19–T21) into a verified package for T23.

        Validates envelope structure, verifies confidence, enforces tenant boundaries,
        detects cross-envelope contradictions, validates candidate CTS deltas,
        and returns a deterministic ConsolidatedEvidencePackage.
        """

        if not envelopes:
            raise ValueError("Cannot consolidate evidence from an empty envelope list.")

        # Determine authoritative tenant
        inferred_tenant = expected_tenant_id
        if not inferred_tenant:
            for env in envelopes:
                t = env.provenance.get("tenant_id")
                if t and t != "global":
                    inferred_tenant = t
                    break
        effective_tenant_id = inferred_tenant or "default"

        accepted_envelopes: list[EvidenceEnvelope] = []
        rejected_items: list[RejectedEvidenceItem] = []
        warnings: list[str] = []
        conflicts: list[EvidenceConflict] = []
        seen_task_ids: set[str] = set()
        seen_roles: dict[WorkerRole, list[EvidenceEnvelope]] = {}

        # -----------------------------------------------------------------
        # 1. Structural, Tenant, and Confidence Screening
        # -----------------------------------------------------------------
        for env in envelopes:
            # A. Duplicate / Stale Task Detection
            if env.task_id in seen_task_ids:
                conflicts.append(
                    EvidenceConflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type="duplicate_task_evidence",
                        severity=ConflictSeverity.WARNING,
                        conflicting_task_ids=[env.task_id],
                        sources=[env.worker_role.value],
                        description=f"Duplicate envelope received for task_id '{env.task_id}'. Preserving without overwrite.",
                        field_or_topic="task_id",
                        resolvable_by_hitl=True,
                    )
                )
                warnings.append(f"Duplicate evidence envelope for task '{env.task_id}' detected.")
            seen_task_ids.add(env.task_id)

            if env.worker_role in seen_roles:
                seen_roles[env.worker_role].append(env)
                conflicts.append(
                    EvidenceConflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type="multiple_worker_envelopes",
                        severity=ConflictSeverity.WARNING,
                        conflicting_task_ids=[e.task_id for e in seen_roles[env.worker_role]],
                        sources=[env.worker_role.value],
                        description=f"Multiple envelopes submitted for role '{env.worker_role.value}'. Preserving for review.",
                        field_or_topic="worker_role",
                        resolvable_by_hitl=True,
                    )
                )
            else:
                seen_roles[env.worker_role] = [env]

            # B. Tenant Scope Verification
            env_tenant = env.provenance.get("tenant_id")
            if not env_tenant:
                # Try inferring from payload
                for key in ("strategy_plan", "creative_package", "dev_deliverable"):
                    if key in env.payload:
                        try:
                            parsed_payload = json.loads(env.payload[key])
                            if isinstance(parsed_payload, dict) and "tenant_id" in parsed_payload:
                                env_tenant = parsed_payload["tenant_id"]
                                break
                        except (json.JSONDecodeError, TypeError):
                            pass

            if expected_tenant_id and env_tenant and env_tenant != expected_tenant_id:
                rejected_items.append(
                    RejectedEvidenceItem(
                        task_id=env.task_id,
                        worker_role=env.worker_role.value,
                        rejection_reason=f"Tenant mismatch: envelope tenant '{env_tenant}' does not match expected '{expected_tenant_id}'",
                        rejection_code="CROSS_TENANT_BREACH",
                        raw_evidence_summary="; ".join(env.evidence[:2]),
                    )
                )
                continue

            # C. Execution Status Screening
            is_failed = (
                env.proposed_state_changes.get("status") == "failed"
                or any("sandbox execution failed" in line.lower() for line in env.evidence)
                or (env.confidence.point_estimate == 0.0 and any("failed" in line.lower() for line in env.evidence))
            )
            if is_failed:
                rejected_items.append(
                    RejectedEvidenceItem(
                        task_id=env.task_id,
                        worker_role=env.worker_role.value,
                        rejection_reason=f"Execution failed or zero-confidence produced: {env.unresolved_risks_or_assumptions or env.evidence[:1]}",
                        rejection_code="EXECUTION_FAILED",
                        raw_evidence_summary="; ".join(env.evidence[:2]),
                    )
                )
                continue

            # D. Confidence Interval Bounds & Consistency Check
            is_valid_conf, conf_error = self.validate_confidence(env.confidence)
            if not is_valid_conf:
                rejected_items.append(
                    RejectedEvidenceItem(
                        task_id=env.task_id,
                        worker_role=env.worker_role.value,
                        rejection_reason=f"Malformed confidence interval: {conf_error}",
                        rejection_code="MALFORMED_CONFIDENCE",
                        raw_evidence_summary="; ".join(env.evidence[:2]),
                    )
                )
                continue

            # E. Provenance Completeness
            required_prov_keys = ("agent", "capability", "task_id")
            missing_prov = [k for k in required_prov_keys if k not in env.provenance]
            if missing_prov:
                warnings.append(
                    f"Envelope '{env.task_id}' has incomplete provenance keys: {missing_prov}"
                )

            # F. Propagate Unresolved Risks
            for risk in env.unresolved_risks_or_assumptions:
                warnings.append(f"Task {env.task_id} ({env.worker_role.value}) note: {risk}")

            accepted_envelopes.append(env)

        # -----------------------------------------------------------------
        # 2. Prerequisite Role Completeness
        # -----------------------------------------------------------------
        if required_roles:
            present_roles = {e.worker_role for e in accepted_envelopes}
            missing = set(required_roles) - present_roles
            if missing:
                missing_names = sorted([r.value for r in missing])
                conflicts.append(
                    EvidenceConflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type="missing_prerequisite_role",
                        severity=ConflictSeverity.BLOCKING,
                        conflicting_task_ids=[],
                        sources=missing_names,
                        description=f"Missing authoritative evidence for required roles: {missing_names}",
                        field_or_topic="prerequisite_roles",
                        resolvable_by_hitl=False,
                    )
                )
                warnings.append(f"Prerequisite verification failed: missing roles {missing_names}")

        # -----------------------------------------------------------------
        # 3. Cross-Envelope Consistency & Relationship Resolution
        # -----------------------------------------------------------------
        strategy_plan: OmnichannelStrategyPlan | None = None
        strategy_env: EvidenceEnvelope | None = None
        creative_pkg: CreativePackage | None = None
        creative_env: EvidenceEnvelope | None = None
        dev_deliv: DevelopmentDeliverable | None = None
        dev_env: EvidenceEnvelope | None = None

        for env in accepted_envelopes:
            if env.worker_role in (WorkerRole.STRATEGY, "W_STRAT", "strategy"):
                strategy_env = env
                raw_strat = env.payload.get("strategy_plan") or env.payload.get("strategy_roadmap")
                if raw_strat:
                    try:
                        strategy_plan = OmnichannelStrategyPlan.model_validate_json(raw_strat)
                    except Exception:
                        pass
            elif env.worker_role in (WorkerRole.CREATIVE_CONTENT, "W_CREAT", "creative"):
                creative_env = env
                raw_creat = env.payload.get("creative_package")
                if raw_creat:
                    try:
                        creative_pkg = CreativePackage.model_validate_json(raw_creat)
                    except Exception:
                        pass
            elif env.worker_role in (WorkerRole.DEVELOPMENT, "W_DEV", "development"):
                dev_env = env
                raw_dev = env.payload.get("dev_deliverable")
                if raw_dev:
                    try:
                        dev_deliv = DevelopmentDeliverable.model_validate_json(raw_dev)
                    except Exception:
                        pass

        # Check Strategy vs Creative Channel Alignment
        if strategy_plan and creative_pkg and strategy_env and creative_env:
            strat_channels = {
                alloc.channel.lower()
                for alloc in strategy_plan.channel_allocations
                if alloc.allocated_amount > 0
            }
            creat_channels: set[str] = set()
            for copy_var in creative_pkg.ad_copy_variants:
                creat_channels.add(copy_var.channel.lower())
            for social_var in creative_pkg.social_posts:
                creat_channels.add(social_var.platform.lower())
            for sched in creative_pkg.schedules:
                creat_channels.add(sched.channel.lower())
            for brief in creative_pkg.visual_briefs:
                creat_channels.add(brief.channel.lower())

            unallocated = creat_channels - strat_channels
            if unallocated:
                conflicts.append(
                    EvidenceConflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type="channel_allocation_mismatch",
                        severity=ConflictSeverity.WARNING,
                        conflicting_task_ids=[strategy_env.task_id, creative_env.task_id],
                        sources=["strategy", "creative"],
                        description=f"Creative assets target channels with zero/no budget allocation in strategy: {sorted(unallocated)}",
                        field_or_topic="channels",
                        resolvable_by_hitl=True,
                    )
                )

            # Check Claim Grounding Alignment
            if creative_pkg.flagged_unsupported_claims:
                conflicts.append(
                    EvidenceConflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type="unsupported_claims_detected",
                        severity=ConflictSeverity.BLOCKING,
                        conflicting_task_ids=[creative_env.task_id],
                        sources=["creative"],
                        description=f"Creative package contains flagged unsupported claims: {creative_pkg.flagged_unsupported_claims}",
                        field_or_topic="claims",
                        resolvable_by_hitl=True,
                    )
                )

            if strategy_plan.approved_claims_applied and creative_pkg.approved_claim_refs:
                unapproved_refs = set(creative_pkg.approved_claim_refs) - set(strategy_plan.approved_claims_applied)
                if unapproved_refs:
                    conflicts.append(
                        EvidenceConflict(
                            conflict_id=str(uuid.uuid4()),
                            conflict_type="unapproved_claim_reference",
                            severity=ConflictSeverity.WARNING,
                            conflicting_task_ids=[strategy_env.task_id, creative_env.task_id],
                            sources=["strategy", "creative"],
                            description=f"Creative references claims not listed in strategy approved claims: {sorted(unapproved_refs)}",
                            field_or_topic="claims",
                            resolvable_by_hitl=True,
                        )
                    )

        # Check Development Security and Syntax
        if dev_deliv and dev_env:
            if not dev_deliv.security_checks_passed:
                conflicts.append(
                    EvidenceConflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type="security_check_failed",
                        severity=ConflictSeverity.BLOCKING,
                        conflicting_task_ids=[dev_env.task_id],
                        sources=["development"],
                        description="Development deliverable failed automated security checks.",
                        field_or_topic="security",
                        resolvable_by_hitl=False,
                    )
                )
            syntax_errors = [diff.syntax_errors for diff in dev_deliv.code_diffs if diff.syntax_errors]
            if syntax_errors:
                conflicts.append(
                    EvidenceConflict(
                        conflict_id=str(uuid.uuid4()),
                        conflict_type="syntax_errors_in_code_diff",
                        severity=ConflictSeverity.BLOCKING,
                        conflicting_task_ids=[dev_env.task_id],
                        sources=["development"],
                        description=f"Syntax errors detected in code diffs: {syntax_errors}",
                        field_or_topic="code_diff",
                        resolvable_by_hitl=False,
                    )
                )

        # -----------------------------------------------------------------
        # 4. Artifact Reference Resolution
        # -----------------------------------------------------------------
        validated_artifacts: list[dict[str, Any]] = []
        for env in accepted_envelopes:
            for art_id in sorted(list(set(env.generated_artifacts))):
                prefix = art_id.split(":")[0] if ":" in art_id else "generic"
                deliverable_type = "structured_deliverable"
                if prefix in ("copy", "creative"):
                    deliverable_type = "copy_pack"
                elif prefix in ("diff", "dev"):
                    deliverable_type = "code_diff"
                elif prefix in ("strategy", "alloc"):
                    deliverable_type = "structured_deliverable"
                elif prefix in ("dossier", "claim"):
                    deliverable_type = "evidence_dossier"

                payload_str = json.dumps(env.payload, sort_keys=True) if env.payload else ";".join(env.evidence)
                content_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

                art_metadata = {"task_id": env.task_id, "role": env.worker_role.value}
                if "budget_total" in env.payload:
                    art_metadata["budget_total"] = env.payload["budget_total"]

                art_ref = ArtifactReference(
                    artifact_id=art_id,
                    content_hash=content_hash,
                    uri=f"artifact://{effective_tenant_id}/{art_id}",
                    media_type="application/json",
                    deliverable_type=deliverable_type,
                    tenant_id=effective_tenant_id,
                    name=f"{env.worker_role.value} deliverable ({art_id})",
                    creator_agent=env.worker_role.value,
                    provenance_ref=env.provenance.get("execution_id"),
                    metadata=art_metadata,
                )
                validated_artifacts.append(art_ref.model_dump(mode="json"))

        # -----------------------------------------------------------------
        # 5. Confidence Verification & Statistical Summary
        # -----------------------------------------------------------------
        if accepted_envelopes:
            total_weight = sum(e.confidence.point_estimate for e in accepted_envelopes) or 1.0
            weighted_point = sum(
                e.confidence.point_estimate * e.confidence.point_estimate for e in accepted_envelopes
            ) / total_weight
            weighted_lower = sum(
                e.confidence.lower_bound * e.confidence.point_estimate for e in accepted_envelopes
            ) / total_weight
            weighted_upper = sum(
                e.confidence.upper_bound * e.confidence.point_estimate for e in accepted_envelopes
            ) / total_weight

            points = [e.confidence.point_estimate for e in accepted_envelopes]
            mean_p = sum(points) / len(points)
            variance = sum((p - mean_p) ** 2 for p in points) / len(points)
            dispersion = round(math.sqrt(variance), 4)

            if weighted_point >= 0.8:
                band = "HIGH"
            elif weighted_point >= 0.5:
                band = "MODERATE"
            else:
                band = "LOW"

            has_malformed = any(r.rejection_code == "MALFORMED_CONFIDENCE" for r in rejected_items)
            is_stat_sound = dispersion <= 0.35 and not has_malformed

            conf_summary = ConsolidatedConfidenceSummary(
                weighted_point_estimate=round(weighted_point, 4),
                lower_bound=round(weighted_lower, 4),
                upper_bound=round(weighted_upper, 4),
                dispersion=dispersion,
                confidence_band=band,
                is_statistically_sound=is_stat_sound,
                envelope_count=len(accepted_envelopes),
            )
        else:
            conf_summary = ConsolidatedConfidenceSummary(
                weighted_point_estimate=0.0,
                lower_bound=0.0,
                upper_bound=0.0,
                dispersion=0.0,
                confidence_band="ZERO",
                is_statistically_sound=False,
                envelope_count=0,
            )

        # -----------------------------------------------------------------
        # 6. Candidate State Delta Validation
        # -----------------------------------------------------------------
        candidate_deltas: list[CandidateStateDelta] = []
        valid_cts_statuses = {s.value for s in TaskStatus}
        for env in accepted_envelopes:
            proposed = env.proposed_state_changes
            target_status_str = proposed.get("status", "completed").lower()
            is_auth = target_status_str in valid_cts_statuses
            validation_notes = (
                "Authorized CTS transition candidate"
                if is_auth
                else f"Unauthorized CTS target status '{target_status_str}'"
            )

            delta = CandidateStateDelta(
                task_id=env.task_id,
                tenant_id=effective_tenant_id,
                worker_role=env.worker_role,
                target_status=target_status_str,
                proposed_changes=proposed,
                is_authorized=is_auth,
                validation_notes=validation_notes,
            )
            candidate_deltas.append(delta)

        # -----------------------------------------------------------------
        # 7. Package Assembly & Deterministic Identification
        # -----------------------------------------------------------------
        sorted_task_ids = sorted([e.task_id for e in accepted_envelopes])
        hash_basis = f"{effective_tenant_id}::" + "::".join(sorted_task_ids)
        if directive_id:
            hash_basis = f"{directive_id}::{hash_basis}"
        pkg_hash = hashlib.sha256(hash_basis.encode("utf-8")).hexdigest()[:16]
        package_id = f"pkg-{effective_tenant_id}-{pkg_hash}"

        # Determine Package Status
        if len(accepted_envelopes) == 0:
            pkg_status = ConsolidatedPackageStatus.REJECTED
        elif any(c.severity == ConflictSeverity.BLOCKING for c in conflicts):
            pkg_status = ConsolidatedPackageStatus.FLAGGED_WITH_CONFLICTS
        elif len(conflicts) > 0:
            pkg_status = ConsolidatedPackageStatus.FLAGGED_WITH_CONFLICTS
        else:
            pkg_status = ConsolidatedPackageStatus.VALID

        # Synthesized text summary
        synthesized_summary: list[str] = []
        for env in accepted_envelopes:
            role_label = env.worker_role.value if hasattr(env.worker_role, "value") else str(env.worker_role)
            summary_items = list(env.findings) + [e for e in env.evidence if e not in env.findings]
            synthesized_summary.append(
                f"[{role_label}] {env.task_id}: {'; '.join(summary_items[:3])}"
            )

        provenance_summary: dict[str, Any] = {
            "consolidator": "IntelligenceEngine.EvidenceSynthesizer",
            "accepted_count": len(accepted_envelopes),
            "rejected_count": len(rejected_items),
            "conflict_count": len(conflicts),
            "tenant_id": effective_tenant_id,
            "tasks": sorted_task_ids,
        }
        if strategy_plan:
            provenance_summary["total_spend"] = float(strategy_plan.total_allocated)


        return ConsolidatedEvidencePackage(
            package_id=package_id,
            tenant_id=effective_tenant_id,
            status=pkg_status,
            source_task_ids=sorted_task_ids,
            participating_roles=sorted(list({e.worker_role for e in accepted_envelopes})),
            validated_artifacts=validated_artifacts,
            confidence_summary=conf_summary,
            conflicts=conflicts,
            warnings=warnings,
            rejected_items=rejected_items,
            proposed_state_deltas=candidate_deltas,
            synthesized_evidence_summary=synthesized_summary,
            provenance_summary=provenance_summary,
            consolidated_at=datetime.now(UTC),
        )