"""DEV-VERIFY: Technical Verification Sub-Agent (DE-10).

Responsible for:
- Independent technical acceptance verification of approved DE-09 / DE-08 / DE-07 candidates
- Plan authority enforcement (verifies DEV-VERIFY is active in approved DevelopmentPlan)
- Exact candidate hash verification (fails closed on missing, mismatched, or stale snapshot)
- Strict read-only invariant (never modifies candidate code or applies auto-fixes)
- Deterministic test and check execution order in fresh isolated sandbox (S_CODE):
  1. verify_environment
  2. run_build
  3. run_lint_check
  4. run_format_check
  5. run_type_check
  6. run_automated_tests (unit & integration)
  7. run_coverage_analysis
- Machine verdict determination: PASS, FAIL, ERROR, BLOCKED
- Automated routing to responsible authoring sub-agent (DEV-CODE, DEV-UI, DEV-CMS) on failure
- Sealed, tamper-evident VerificationDossier with canonical byte hashing
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
    CheckOutcome,
    CodeCandidateDeliverable,
    CoverageReport,
    DevelopmentTaskGrant,
    TestTotals,
    VerificationCheckResult,
    VerificationDossier,
    VerificationVerdict,
)
from app.schemas.development.ui import UiCandidateDeliverable
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate

logger = logging.getLogger(__name__)


class VerificationAgent:
    """DEV-VERIFY technical verification sub-agent for W_DEV."""

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
                "Sandbox invocation failed for DEV-VERIFY operation %s",
                operation,
                extra={"operation": operation, "error": result.error},
            )
            return {"status": "error", "error": result.error or "Sandbox execution failure"}

        output = result.sanitized_output if result else {}
        output = output or {}

        verify_expected_keys = {
            "verify_environment": ("is_ready", "isolation_validated"),
            "run_build": ("build_passed", "success", "compiled_files"),
            "run_lint_check": ("lint_passed", "passed", "error_count"),
            "run_format_check": ("format_passed", "passed", "unformatted_files"),
            "run_type_check": ("type_check_passed", "passed", "error_count"),
            "run_automated_tests": ("test_totals", "all_passed"),
            "run_coverage_analysis": ("coverage_threshold_met", "line_coverage_pct"),
        }
        needed = verify_expected_keys.get(operation, ())
        if not any(k in output for k in needed):
            from app.integrations.sandbox.micro_tools import execute_s_code

            exec_payload = dict(payload)
            exec_payload["operation"] = operation
            exec_res = execute_s_code(exec_payload, operation=operation)
            if exec_res.get("output"):
                return exec_res["output"]
            return exec_res

        return output

    async def execute_verification_task(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        candidate: CodeCandidateDeliverable
        | UiCandidateDeliverable
        | CmsCandidateDeliverable
        | None,
        expected_candidate_hash: str | None = None,
        plan: DevelopmentPlan | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        context: dict[str, Any] | None = None,
    ) -> VerificationDossier:
        """Execute independent technical verification against an approved candidate deliverable."""
        ctx = context or {}
        tenant_id = (
            grant.tenant_scope.tenant_id
            if hasattr(grant, "tenant_scope") and grant.tenant_scope
            else "default"
        )
        task_id = grant.task_id if hasattr(grant, "task_id") else "unknown"
        wf_id = workflow_id or f"wf-verify-{uuid.uuid4().hex[:8]}"

        # 1. Plan Authority Enforcement
        if plan is not None:
            verify_step: DevelopmentPlanStep | None = None
            for s in plan.steps:
                step_name = getattr(s, "step_name", None) or getattr(s, "subagent", None) or ""
                if "VERIFY" in step_name.upper():
                    verify_step = s
                    break

            if (
                verify_step is not None
                and getattr(verify_step, "status", None) == "SKIPPED_NOT_APPLICABLE"
            ):
                raise PolicyViolationError(
                    "Execution of DEV-VERIFY is not authorized by the development plan "
                    "(step marked SKIPPED_NOT_APPLICABLE)."
                )

        # 2. Candidate Deliverable and Hash Integrity Check (Fail-Closed)
        if candidate is None:
            raise PolicyViolationError("Candidate deliverable is missing for DEV-VERIFY.")

        candidate_id = getattr(candidate, "candidate_id", "") or getattr(
            candidate, "deliverable_id", ""
        )
        component_name = getattr(candidate, "component_name", "Component")

        # Determine actual candidate hash
        actual_hash = getattr(candidate, "candidate_hash", None)
        if not actual_hash and hasattr(candidate, "compute_candidate_hash"):
            actual_hash = candidate.compute_candidate_hash()
        elif not actual_hash and hasattr(candidate, "compute_deliverable_hash"):
            actual_hash = candidate.compute_deliverable_hash()

        if not actual_hash:
            raise PolicyViolationError("Candidate deliverable has no valid tamper-evident hash.")

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

        # Extract candidate source files strictly read-only
        source_code: dict[str, str] = {}
        if hasattr(candidate, "source_code") and isinstance(candidate.source_code, dict):
            source_code = dict(candidate.source_code)
        elif hasattr(candidate, "code_diffs"):
            for d in getattr(candidate, "code_diffs", []):
                fp = getattr(d, "file_path", "")
                if fp:
                    source_code[fp] = getattr(d, "diff_unified", "")

        checks_results: list[VerificationCheckResult] = []
        overall_verdict = VerificationVerdict.PASS
        remediation_step: str | None = None
        test_totals = TestTotals()
        coverage_report: CoverageReport | None = None
        evidence_envelopes: list[EvidenceEnvelope] = []

        # Read-only check guard
        if ctx.get("mutation_requested") or ctx.get("auto_fix"):
            raise PolicyViolationError(
                "Security violation: DEV-VERIFY is strictly read-only and does not accept "
                "auto-fix or mutation requests."
            )

        # -------------------------------------------------------------
        # Check 1: verify_environment
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        env_payload = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "required_tools": ctx.get("required_tools", ["python", "pytest", "ruff", "mypy"]),
            "isolation_validated": ctx.get("isolation_validated", True),
            "env_status": ctx.get("env_status", "READY"),
        }
        for k in ctx:
            if k.startswith("tool_missing_"):
                env_payload[k] = ctx[k]

        env_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="verify_environment",
            payload=env_payload,
        )
        t_env = (time.perf_counter() - t0) * 1000

        is_env_ready = bool(env_res.get("is_ready", False))
        env_outcome = CheckOutcome.PASS if is_env_ready else CheckOutcome.ERROR
        env_check = VerificationCheckResult(
            check_id="chk-env-01",
            check_type="environment",
            outcome=env_outcome,
            command_or_operation="verify_environment",
            exit_code=0 if is_env_ready else 1,
            duration_ms=round(t_env, 2),
            output_summary="Environment tools and sandbox isolation verified."
            if is_env_ready
            else "Environment verification failed.",
            stdout=str(env_res.get("stdout", "")),
            stderr=str(env_res.get("error", "")),
            error_count=0 if is_env_ready else len(env_res.get("missing_tools", [1])),
            failure_reasons=[str(env_res.get("error"))]
            if not is_env_ready and env_res.get("error")
            else [],
            is_mandatory=True,
        )
        checks_results.append(env_check)

        if not is_env_ready:
            overall_verdict = VerificationVerdict.BLOCKED
            remediation_step = author_subagent
            return self._build_dossier(
                task_id=task_id,
                workflow_id=wf_id,
                candidate_hash=actual_hash,
                target_candidate_id=candidate_id,
                component_name=component_name,
                verdict=overall_verdict,
                remediation_step=remediation_step,
                checks=checks_results,
                test_totals=test_totals,
                coverage_report=coverage_report,
                evidence_envelopes=evidence_envelopes,
                author_subagent=author_subagent,
            )

        # -------------------------------------------------------------
        # Check 2: run_build (Repository-native compilation / build)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        build_payload = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "source_code": source_code,
            "target_files": getattr(candidate, "changed_files", list(source_code.keys())),
            "simulate_build_failure": ctx.get("simulate_build_failure"),
        }
        build_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="run_build",
            payload=build_payload,
        )
        t_build = (time.perf_counter() - t0) * 1000

        build_passed = bool(build_res.get("build_passed", False) or build_res.get("success", False))
        build_errors = [str(e) for e in build_res.get("errors", [])]
        build_outcome = CheckOutcome.PASS if build_passed else CheckOutcome.FAIL
        build_check = VerificationCheckResult(
            check_id="chk-build-02",
            check_type="build",
            outcome=build_outcome,
            command_or_operation="run_build",
            exit_code=0 if build_passed else 1,
            duration_ms=round(t_build, 2),
            output_summary="Build compilation succeeded cleanly."
            if build_passed
            else "Build compilation failed.",
            stdout=str(build_res.get("stdout", "")),
            stderr=str(build_res.get("stderr", "")),
            error_count=len(build_errors),
            failure_reasons=build_errors,
            is_mandatory=True,
        )
        checks_results.append(build_check)
        if not build_passed and overall_verdict == VerificationVerdict.PASS:
            overall_verdict = VerificationVerdict.FAIL
            remediation_step = author_subagent

        # -------------------------------------------------------------
        # Check 3: run_lint_check (Repository-native linter check-only)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        lint_payload = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "source_code": source_code,
            "simulate_lint_errors": ctx.get("simulate_lint_errors"),
        }
        lint_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="run_lint_check",
            payload=lint_payload,
        )
        t_lint = (time.perf_counter() - t0) * 1000

        lint_passed = bool(lint_res.get("lint_passed", False) or lint_res.get("passed", False))
        lint_errors = [str(e) for e in lint_res.get("errors", [])]
        lint_outcome = CheckOutcome.PASS if lint_passed else CheckOutcome.FAIL
        lint_check = VerificationCheckResult(
            check_id="chk-lint-03",
            check_type="lint",
            outcome=lint_outcome,
            command_or_operation="run_lint_check",
            exit_code=0 if lint_passed else 1,
            duration_ms=round(t_lint, 2),
            output_summary="Lint checks passed with 0 violations."
            if lint_passed
            else f"Lint violations detected ({len(lint_errors)} errors).",
            stdout=str(lint_res.get("stdout", "")),
            stderr=str(lint_res.get("stderr", "")),
            error_count=len(lint_errors),
            warning_count=int(lint_res.get("warning_count", 0)),
            failure_reasons=lint_errors,
            is_mandatory=True,
        )
        checks_results.append(lint_check)
        if not lint_passed and overall_verdict == VerificationVerdict.PASS:
            overall_verdict = VerificationVerdict.FAIL
            remediation_step = author_subagent

        # -------------------------------------------------------------
        # Check 4: run_format_check (Format check-only, non-mutating)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        fmt_payload = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "source_code": source_code,
            "simulate_unformatted_files": ctx.get("simulate_unformatted_files"),
        }
        fmt_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="run_format_check",
            payload=fmt_payload,
        )
        t_fmt = (time.perf_counter() - t0) * 1000

        fmt_passed = bool(fmt_res.get("format_passed", False) or fmt_res.get("passed", False))
        unformatted = [str(f) for f in fmt_res.get("unformatted_files", [])]
        fmt_outcome = CheckOutcome.PASS if fmt_passed else CheckOutcome.FAIL
        fmt_check = VerificationCheckResult(
            check_id="chk-fmt-04",
            check_type="format",
            outcome=fmt_outcome,
            command_or_operation="run_format_check",
            exit_code=0 if fmt_passed else 1,
            duration_ms=round(t_fmt, 2),
            output_summary="Code style matches formatting specifications."
            if fmt_passed
            else f"Formatting check failed for {len(unformatted)} file(s).",
            stdout=str(fmt_res.get("stdout", "")),
            stderr=str(fmt_res.get("stderr", "")),
            error_count=len(unformatted),
            failure_reasons=[f"File requires reformatting: {f}" for f in unformatted],
            is_mandatory=True,
        )
        checks_results.append(fmt_check)
        if not fmt_passed and overall_verdict == VerificationVerdict.PASS:
            overall_verdict = VerificationVerdict.FAIL
            remediation_step = author_subagent

        # -------------------------------------------------------------
        # Check 5: run_type_check (Type check)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        type_payload = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "source_code": source_code,
            "simulate_type_errors": ctx.get("simulate_type_errors"),
            "strict_type_checking": ctx.get("strict_type_checking", False),
        }
        type_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="run_type_check",
            payload=type_payload,
        )
        t_type = (time.perf_counter() - t0) * 1000

        type_passed = bool(
            type_res.get("type_check_passed", False) or type_res.get("passed", False)
        )
        type_errors = [str(e) for e in type_res.get("errors", [])]
        type_outcome = CheckOutcome.PASS if type_passed else CheckOutcome.FAIL
        type_check = VerificationCheckResult(
            check_id="chk-type-05",
            check_type="type_check",
            outcome=type_outcome,
            command_or_operation="run_type_check",
            exit_code=0 if type_passed else 1,
            duration_ms=round(t_type, 2),
            output_summary="Type check passed: static types sound."
            if type_passed
            else f"Type check found {len(type_errors)} violations.",
            stdout=str(type_res.get("stdout", "")),
            stderr=str(type_res.get("stderr", "")),
            error_count=len(type_errors),
            failure_reasons=type_errors,
            is_mandatory=True,
        )
        checks_results.append(type_check)
        if not type_passed and overall_verdict == VerificationVerdict.PASS:
            overall_verdict = VerificationVerdict.FAIL
            remediation_step = author_subagent

        # -------------------------------------------------------------
        # Check 6: run_automated_tests (Automated Unit & Integration Tests)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        test_payload = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "test_type": "unit",
            "simulate_test_results": ctx.get("simulate_test_results"),
        }
        test_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="run_automated_tests",
            payload=test_payload,
        )
        t_test = (time.perf_counter() - t0) * 1000

        raw_totals = test_res.get("test_totals", {})
        test_totals = TestTotals(
            passed=int(raw_totals.get("passed", 0)),
            failed=int(raw_totals.get("failed", 0)),
            skipped=int(raw_totals.get("skipped", 0)),
            errored=int(raw_totals.get("errored", 0)),
            total=int(raw_totals.get("total", 0)),
            duration_s=float(raw_totals.get("duration_s", 0.0)),
        )

        test_passed = bool(
            test_res.get("all_passed", False)
            and test_totals.failed == 0
            and test_totals.errored == 0
        )
        test_failures = [str(f) for f in test_res.get("failures", [])]
        test_outcome = CheckOutcome.PASS if test_passed else CheckOutcome.FAIL
        unit_test_check = VerificationCheckResult(
            check_id="chk-test-06",
            check_type="unit_test",
            outcome=test_outcome,
            command_or_operation="run_automated_tests",
            exit_code=0 if test_passed else 1,
            duration_ms=round(t_test, 2),
            output_summary=(
                f"Automated test runner: {test_totals.passed} passed, {test_totals.failed} failed."
            ),
            stdout=str(test_res.get("stdout", "")),
            stderr=str(test_res.get("stderr", "")),
            error_count=test_totals.failed + test_totals.errored,
            failure_reasons=test_failures,
            is_mandatory=True,
        )
        checks_results.append(unit_test_check)
        if not test_passed and overall_verdict == VerificationVerdict.PASS:
            overall_verdict = VerificationVerdict.FAIL
            remediation_step = author_subagent

        # -------------------------------------------------------------
        # Check 7: run_coverage_analysis
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        cov_payload = {
            "tenant_id": tenant_id,
            "task_id": task_id,
            "minimum_required_pct": float(ctx.get("minimum_required_pct", 80.0)),
            "simulate_coverage": ctx.get("simulate_coverage"),
        }
        cov_res = await self._invoke_sandbox(
            tenant_id=tenant_id,
            task_id=task_id,
            operation="run_coverage_analysis",
            payload=cov_payload,
        )
        t_cov = (time.perf_counter() - t0) * 1000

        cov_thresh_met = bool(cov_res.get("coverage_threshold_met", False))
        line_pct = float(cov_res.get("line_coverage_pct", 0.0))
        branch_pct = float(cov_res.get("branch_coverage_pct", 0.0))
        min_pct = float(cov_res.get("minimum_required_pct", 80.0))
        coverage_report = CoverageReport(
            line_coverage_pct=line_pct,
            branch_coverage_pct=branch_pct,
            total_statements=int(cov_res.get("total_statements", 0)),
            covered_statements=int(cov_res.get("covered_statements", 0)),
            missing_lines_by_file=cov_res.get("missing_lines_by_file", {}),
            coverage_threshold_met=cov_thresh_met,
            minimum_required_pct=min_pct,
        )

        cov_outcome = CheckOutcome.PASS if cov_thresh_met else CheckOutcome.FAIL
        cov_reasons = (
            []
            if cov_thresh_met
            else [f"Line coverage {line_pct:.1f}% is below required {min_pct:.1f}%."]
        )
        cov_check = VerificationCheckResult(
            check_id="chk-cov-07",
            check_type="coverage",
            outcome=cov_outcome,
            command_or_operation="run_coverage_analysis",
            exit_code=0 if cov_thresh_met else 1,
            duration_ms=round(t_cov, 2),
            output_summary=(
                f"Coverage analysis: {line_pct:.1f}% line coverage (minimum {min_pct:.1f}%)."
            ),
            stdout=str(cov_res.get("stdout", "")),
            stderr=str(cov_res.get("stderr", "")),
            error_count=0 if cov_thresh_met else 1,
            failure_reasons=cov_reasons,
            is_mandatory=True,
        )
        checks_results.append(cov_check)
        if not cov_thresh_met and overall_verdict == VerificationVerdict.PASS:
            overall_verdict = VerificationVerdict.FAIL
            remediation_step = author_subagent

        # Collect evidence envelopes
        evidence_envelopes.append(
            EvidenceEnvelope(
                task_id=task_id,
                worker_role=grant.worker_role
                if hasattr(grant, "worker_role")
                else WorkerRole.DEVELOPMENT,
                confidence=ConfidenceInterval(
                    point_estimate=1.0 if overall_verdict == VerificationVerdict.PASS else 0.5,
                    lower_bound=0.9 if overall_verdict == VerificationVerdict.PASS else 0.4,
                    upper_bound=1.0,
                ),
                findings=[
                    c.output_summary for c in checks_results if c.outcome != CheckOutcome.PASS
                ]
                or ["All verification checks passed."],
                payload={
                    "verdict": overall_verdict.value,
                    "checks_count": str(len(checks_results)),
                    "tests_passed": str(test_totals.passed),
                    "tests_failed": str(test_totals.failed),
                    "line_coverage_pct": str(
                        coverage_report.line_coverage_pct if coverage_report else 0.0
                    ),
                },
            )
        )

        return self._build_dossier(
            task_id=task_id,
            workflow_id=wf_id,
            candidate_hash=actual_hash,
            target_candidate_id=candidate_id,
            component_name=component_name,
            verdict=overall_verdict,
            remediation_step=remediation_step,
            checks=checks_results,
            test_totals=test_totals,
            coverage_report=coverage_report,
            evidence_envelopes=evidence_envelopes,
            author_subagent=author_subagent,
        )

    def _build_dossier(
        self,
        *,
        task_id: str,
        workflow_id: str,
        candidate_hash: str,
        target_candidate_id: str,
        component_name: str,
        verdict: VerificationVerdict,
        remediation_step: str | None,
        checks: list[VerificationCheckResult],
        test_totals: TestTotals,
        coverage_report: CoverageReport | None,
        evidence_envelopes: list[EvidenceEnvelope],
        author_subagent: str,
    ) -> VerificationDossier:
        """Construct and seal a VerificationDossier with SHA-256 digest."""
        dossier = VerificationDossier(
            dossier_id=f"dos-{uuid.uuid4().hex[:12]}",
            task_id=task_id,
            workflow_id=workflow_id,
            candidate_hash=candidate_hash,
            target_candidate_id=target_candidate_id,
            component_name=component_name,
            verdict=verdict,
            remediation_step=remediation_step,
            checks=checks,
            test_totals=test_totals,
            coverage_report=coverage_report,
            evidence_envelopes=evidence_envelopes,
            provenance={
                "subagent": "DEV-VERIFY",
                "author_subagent": author_subagent,
                "verified_candidate_hash": candidate_hash,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        dossier.compute_dossier_hash()
        return dossier

    execute_step = execute_verification_task


# Canonical alias
DevVerifyAgent = VerificationAgent
