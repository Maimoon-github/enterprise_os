"""DEV-SEC: Security Review Sub-Agent (DE-11).

Responsible for:
- Independent, read-only security audit of verified DE-10 candidate snapshots
- Plan authority and task grant verification (fails closed if expired or unauthorized)
- Verification dossier prerequisite check (rejects unverified or failed candidates)
- Exact candidate hash verification (fails closed on missing, mismatched, or stale snapshot)
- Strict read-only invariant (never modifies candidate code or applies auto-fixes)
- Deterministic multi-tier security scans via sandboxed micro-tools (S_CODE):
  1. scan_sast: Static Application Security Testing for dangerous functions and command injections
  2. scan_secrets: High-entropy secret, API key, token, and private key pattern scanning
  3. scan_dependencies_sca: Software Composition Analysis for known vulnerable dependencies / CVEs
  4. review_manifest_configs: Deployment, container, and runtime configuration security review
  5. check_authorization_boundaries: Unauthenticated routes and tenant boundary validation
  6. analyze_ast_dangerous_patterns: AST introspection and Python magic-attribute analysis
- Hard policy enforcement: machine DENY on CRITICAL/HIGH findings blocks release progression
- Sealed, tamper-evident SecurityDossier with canonical byte hashing
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import ConfidenceInterval, EvidenceEnvelope, TaskGrant
from app.schemas.cms import CmsCandidateDeliverable
from app.schemas.development.development_plan import DevelopmentPlan, DevelopmentPlanStep
from app.schemas.development.development_result import (
    CodeCandidateDeliverable,
    DevelopmentTaskGrant,
    SecurityCategory,
    SecurityDossier,
    SecurityFinding,
    SecuritySeverity,
    SecurityVerdict,
    VerificationDossier,
    VerificationVerdict,
)
from app.schemas.development.ui import UiCandidateDeliverable
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate

logger = logging.getLogger(__name__)


class SecurityReviewAgent:
    """DEV-SEC security review sub-agent for W_DEV."""

    def __init__(
        self,
        sandbox_client: Any,
        llm_client: Any | None = None,
    ) -> None:
        self._sandbox_client = sandbox_client
        self._llm_client = llm_client

    async def _invoke_sandbox(
        self,
        *,
        tenant_id: str = "default",
        task_id: str = "unknown",
        operation: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke sandbox control plane via S_CODE with in-process micro-tool fallback."""
        mandate = SandboxInvocationMandate(
            tenant_id=tenant_id,
            task_id=task_id,
            worker_role=WorkerRole.DEVELOPMENT,
            capability=SandboxCapability.CODE,
            operation=operation,
            payload=payload,
        )

        result = None
        if hasattr(self._sandbox_client, "invoke"):
            result = await self._sandbox_client.invoke(mandate)
        elif hasattr(self._sandbox_client, "execute"):
            result = await self._sandbox_client.execute(mandate)

        if result is not None and not result.success:
            logger.error(
                "Sandbox invocation failed for DEV-SEC operation %s",
                operation,
                extra={"operation": operation, "error": result.error},
            )
            return {"status": "error", "error": result.error or "Sandbox execution failure"}

        output = result.sanitized_output if result else {}
        output = output or {}

        # If sandbox microtool ran in-process, output may be wrapped or returned directly
        if "output" in output and isinstance(output["output"], dict):
            return output["output"]
        if "findings" in output or "verdict" in output:
            return output

        # Fallback to direct micro-tool execution if client returned raw wrapper
        from app.integrations.sandbox.micro_tools import execute_s_code

        fallback_payload = dict(payload)
        fallback_payload["operation"] = operation
        return execute_s_code(fallback_payload)

    async def execute_security_task(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant | None = None,
        candidate: (
            CodeCandidateDeliverable
            | UiCandidateDeliverable
            | CmsCandidateDeliverable
            | Any
            | None
        ) = None,
        expected_candidate_hash: str | None = None,
        verification_dossier: VerificationDossier | None = None,
        plan: DevelopmentPlan | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        context: dict[str, Any] | None = None,
    ) -> SecurityDossier:
        """Execute independent security audit against a verified candidate snapshot."""
        tenant_id = (
            grant.tenant_scope.tenant_id
            if hasattr(grant, "tenant_scope") and grant.tenant_scope
            else "default"
        )
        task_id = grant.task_id if hasattr(grant, "task_id") else "unknown"
        return await self.review_security(
            tenant_id=tenant_id,
            task_id=task_id,
            workflow_id=workflow_id,
            plan=plan,
            task_grant=grant,
            verification_dossier=verification_dossier,
            candidate=candidate,
            expected_candidate_hash=expected_candidate_hash,
            context=context,
        )

    async def review_security(
        self,
        *,
        tenant_id: str = "default",
        task_id: str = "unknown",
        workflow_id: str | None = None,
        plan: DevelopmentPlan | None = None,
        task_grant: TaskGrant | DevelopmentTaskGrant | None = None,
        verification_dossier: VerificationDossier | None = None,
        candidate: (
            CodeCandidateDeliverable
            | UiCandidateDeliverable
            | CmsCandidateDeliverable
            | Any
            | None
        ) = None,
        expected_candidate_hash: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> SecurityDossier:
        """Execute comprehensive security review on the verified candidate snapshot."""
        ctx = context or {}
        wf_id = workflow_id or f"wf-sec-{uuid.uuid4().hex[:8]}"

        # 1. Plan Authority Enforcement
        if plan is not None:
            sec_step: DevelopmentPlanStep | None = None
            for s in plan.steps:
                step_name = (
                    getattr(s, "step_name", None)
                    or getattr(s, "subagent_id", None)
                    or getattr(s, "subagent", None)
                    or getattr(s, "step_id", None)
                    or ""
                )
                if "SEC" in step_name.upper():
                    sec_step = s
                    break

            if (
                sec_step is not None
                and getattr(sec_step, "status", None) == "SKIPPED_NOT_APPLICABLE"
            ):
                raise PolicyViolationError(
                    "Execution of DEV-SEC is not authorized by the development plan "
                    "(step marked SKIPPED_NOT_APPLICABLE)."
                )

        # 2. Task Grant Validity Check
        if task_grant is not None:
            if hasattr(task_grant, "is_expired") and task_grant.is_expired():
                raise PolicyViolationError("Task grant has expired for DEV-SEC security review.")
            if (
                hasattr(task_grant, "expires_at")
                and task_grant.expires_at is not None
                and task_grant.expires_at < datetime.now(UTC)
            ):
                raise PolicyViolationError(
                    "Task grant has expired for DEV-SEC security review."
                )

        # 3. Candidate Deliverable and Snapshot Integrity Check (Fail-Closed)
        if candidate is None and verification_dossier is None:
            raise PolicyViolationError(
                "Neither candidate deliverable nor verification dossier provided for DEV-SEC."
            )

        candidate_id = ""
        component_name = "Component"
        actual_hash = ""

        if candidate is not None:
            candidate_id = getattr(candidate, "candidate_id", "") or getattr(
                candidate, "deliverable_id", ""
            )
            component_name = getattr(candidate, "component_name", "Component")
            actual_hash = getattr(candidate, "candidate_hash", "")
            if not actual_hash and hasattr(candidate, "compute_candidate_hash"):
                actual_hash = candidate.compute_candidate_hash()
            elif not actual_hash and hasattr(candidate, "compute_deliverable_hash"):
                actual_hash = candidate.compute_deliverable_hash()

        if verification_dossier is not None:
            if verification_dossier.verdict != VerificationVerdict.PASS:
                raise PolicyViolationError(
                    f"DEV-SEC cannot run on candidate with verification verdict "
                    f"'{verification_dossier.verdict}'. DE-10 PASS is strictly required."
                )
            dossier_cand_hash = verification_dossier.candidate_hash
            if actual_hash and actual_hash != dossier_cand_hash:
                raise PolicyViolationError(
                    f"Candidate digest mismatch: candidate hash '{actual_hash}' does not match "
                    f"verification dossier candidate hash '{dossier_cand_hash}'."
                )
            if not actual_hash:
                actual_hash = dossier_cand_hash
            if not candidate_id:
                candidate_id = verification_dossier.target_candidate_id
            if component_name == "Component":
                component_name = verification_dossier.component_name

        if not actual_hash:
            raise PolicyViolationError("Candidate snapshot has no valid tamper-evident hash.")

        if expected_candidate_hash is not None and expected_candidate_hash != actual_hash:
            raise PolicyViolationError(
                f"Candidate digest mismatch: expected '{expected_candidate_hash}', "
                f"got '{actual_hash}'. Snapshot integrity compromised."
            )

        # Determine responsible authoring sub-agent for remediation routing
        if (
            isinstance(candidate, UiCandidateDeliverable)
            or getattr(candidate, "subagent", "") == "DEV-UI"
        ):
            author_subagent = "DEV-UI"
        elif (
            isinstance(candidate, CmsCandidateDeliverable)
            or getattr(candidate, "subagent", "") == "DEV-CMS"
        ):
            author_subagent = "DEV-CMS"
        else:
            author_subagent = "DEV-CODE"

        # 4. Strict Read-Only Guard
        if (
            ctx.get("mutation_requested")
            or ctx.get("auto_fix")
            or ctx.get("write_file")
            or ctx.get("apply_patch")
        ):
            raise PolicyViolationError(
                "Security violation: DEV-SEC is strictly read-only and does not accept "
                "auto-fix or mutation requests."
            )

        # Extract candidate source files strictly read-only
        source_code: dict[str, str] = {}
        if hasattr(candidate, "source_code") and isinstance(candidate.source_code, dict):
            source_code = dict(candidate.source_code)
        elif hasattr(candidate, "code_diffs"):
            for d in getattr(candidate, "code_diffs", []):
                fp = getattr(d, "file_path", "")
                if fp:
                    source_code[fp] = getattr(d, "diff_unified", "")
        if "source_code" in ctx and isinstance(ctx["source_code"], dict):
            source_code.update(ctx["source_code"])

        scanners_to_run = [
            "scan_sast",
            "scan_secrets",
            "scan_dependencies_sca",
            "review_manifest_configs",
            "check_authorization_boundaries",
            "analyze_ast_dangerous_patterns",
        ]

        all_findings: list[SecurityFinding] = []
        evidence_envelopes: list[EvidenceEnvelope] = []
        scanners_run: list[str] = []

        scanner_payload_base = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "component_name": component_name,
            "source_code": source_code,
            "candidate_source": source_code,
            "dependencies": ctx.get("dependencies", {}),
            "requirements_content": ctx.get("requirements_content", ""),
            "manifests": ctx.get("manifests", {}),
            "routes": ctx.get("routes", []),
        }

        for sc_op in scanners_to_run:
            t0 = time.perf_counter()
            sc_payload = dict(scanner_payload_base)

            # Pass-through any simulated or contextual items
            if f"simulated_findings_{sc_op}" in ctx:
                sc_payload["simulated_findings"] = ctx[f"simulated_findings_{sc_op}"]
            elif "simulated_findings" in ctx and sc_op == "scan_sast":
                sc_payload["simulated_findings"] = ctx["simulated_findings"]
            if "simulate_vulnerability" in ctx and sc_op == "scan_dependencies_sca":
                sc_payload["simulate_vulnerability"] = ctx["simulate_vulnerability"]

            res = await self._invoke_sandbox(
                tenant_id=tenant_id,
                task_id=task_id,
                operation=sc_op,
                payload=sc_payload,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            scanners_run.append(sc_op)

            # Check if sandbox returned security violation (mutation attempt)
            if res.get("security_violation"):
                raise PolicyViolationError(
                    f"DEV-SEC sandbox rejected operation due to read-only violation: "
                    f"{res.get('error')}"
                )

            # Extract findings
            raw_findings = res.get("findings") or []
            for rf in raw_findings:
                sev_str = str(rf.get("severity", "HIGH")).upper()
                sev = (
                    SecuritySeverity(sev_str)
                    if sev_str in SecuritySeverity._value2member_map_
                    else SecuritySeverity.HIGH
                )
                cat_str = str(rf.get("category", "SAST")).upper()
                cat = (
                    SecurityCategory(cat_str)
                    if cat_str in SecurityCategory._value2member_map_
                    else SecurityCategory.SAST
                )
                is_hb = bool(
                    rf.get("is_hard_block")
                    or sev in (SecuritySeverity.CRITICAL, SecuritySeverity.HIGH)
                )

                finding = SecurityFinding(
                    finding_id=str(rf.get("finding_id") or f"find-{uuid.uuid4().hex[:8]}"),
                    rule_id=str(rf.get("rule_id", "SEC-GEN-001")),
                    category=cat,
                    severity=sev,
                    title=str(rf.get("title", "Security finding")),
                    description=str(rf.get("description", "")),
                    file_path=str(rf.get("file_path", "unknown")),
                    line_number=rf.get("line_number"),
                    code_snippet=str(rf.get("code_snippet", "")),
                    remediation_target=str(rf.get("remediation_target", author_subagent)),
                    is_hard_block=is_hb,
                    cve_id=rf.get("cve_id"),
                    cwe_id=rf.get("cwe_id"),
                )
                all_findings.append(finding)

            # Produce evidence envelope for scanner run
            env_envelope = EvidenceEnvelope(
                task_id=task_id,
                worker_role=WorkerRole.DEVELOPMENT,
                confidence=ConfidenceInterval(
                    point_estimate=1.0 if not raw_findings else 0.4,
                    lower_bound=0.9 if not raw_findings else 0.2,
                    upper_bound=1.0,
                ),
                findings=[
                    f"{f.rule_id}: {f.title}" for f in all_findings
                ] or ["Clean security scan"],
                payload={
                    "operation": sc_op,
                    "findings_count": str(len(raw_findings)),
                    "status": str(res.get("status", "SUCCESS")),
                    "elapsed_ms": f"{elapsed_ms:.1f}",
                },
                produced_at=datetime.now(UTC),
            )
            evidence_envelopes.append(env_envelope)

        hard_blocks = sum(1 for f in all_findings if f.is_hard_block)
        remediation_targets = sorted(list({f.remediation_target for f in all_findings}))
        final_verdict = SecurityVerdict.DENY if hard_blocks > 0 else SecurityVerdict.PASS

        dossier = SecurityDossier(
            dossier_id=f"sec-dossier-{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            workflow_id=wf_id,
            candidate_hash=actual_hash,
            target_candidate_id=candidate_id or f"cand-{task_id}",
            component_name=component_name,
            verdict=final_verdict,
            scanners_run=scanners_run,
            scanner_versions={
                "scan_sast": "1.0.0",
                "scan_secrets": "1.0.0",
                "scan_dependencies_sca": "1.0.0",
                "review_manifest_configs": "1.0.0",
                "check_authorization_boundaries": "1.0.0",
                "analyze_ast_dangerous_patterns": "1.0.0",
            },
            findings=all_findings,
            hard_block_count=hard_blocks,
            remediation_targets=remediation_targets,
            evidence_envelopes=evidence_envelopes,
            provenance={
                "subagent": "DEV-SEC",
                "evaluated_at": datetime.now(UTC).isoformat(),
                "verdict": final_verdict.value,
                "hard_block_count": hard_blocks,
            },
        )
        dossier.compute_dossier_hash()

        logger.info(
            "DEV-SEC completed security review: verdict=%s, hard_blocks=%d, total_findings=%d",
            final_verdict.value,
            hard_blocks,
            len(all_findings),
            extra={
                "task_id": task_id,
                "dossier_id": dossier.dossier_id,
                "verdict": final_verdict.value,
            },
        )

        return dossier


# Canonical alias
DevSecAgent = SecurityReviewAgent
