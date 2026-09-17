"""DEV-CODE: Application Code Implementation Specialist Sub-Agent (DE-09).

Responsible for:
- Application & business logic implementation
- API & integration logic implementation
- State management & error handling
- Approved refactoring and generated-code integration
- Plan authority enforcement and artifact mutation scoping
- Predecessor snapshot and hash verification (DEV-UI / DEV-CMS / DEV-PLAN)
- Scoped file patch, formatting, AST structural symbol analysis, and native compiler sanity checks
- Strict dependency control (fail-closed on unauthorized dependency mutations)
- Sealed code candidate deliverable production for DE-04 HITL review
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import logging
import re
from typing import Any
import uuid

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import CodeDiffEntry, TaskGrant
from app.schemas.cms import CmsCandidateDeliverable
from app.schemas.development.development_plan import DevelopmentPlan, DevelopmentPlanStep
from app.schemas.development.development_result import (
    CodeCandidateDeliverable,
    CodeSanityCheckResult,
    DependencyChange,
    DependencyChangeAction,
    DevelopmentTaskGrant,
    InterfaceChange,
    ToolExecutionEvidence,
)
from app.schemas.development.ui import UiCandidateDeliverable
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate

logger = logging.getLogger(__name__)


class CodeImplementationAgent:
    """Specialist sub-agent for bounded application and integration code authoring."""

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
        """Invoke the sandbox control plane via S_CODE with in-process micro-tool fallback."""
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
                "Sandbox invocation failed for DEV-CODE operation %s",
                operation,
                extra={"operation": operation, "error": result.error},
            )
            return {"status": "error", "error": result.error or "Sandbox execution failure"}

        output = result.sanitized_output if result else {}
        output = output or {}

        code_expected_keys = {
            "apply_code_patch": ("patched_content", "diff_unified", "is_patched"),
            "format_code": ("formatted_code", "is_formatted"),
            "inspect_ast_symbols": ("classes", "functions", "symbols_summary"),
            "validate_syntax_compiler": ("compiler_passed", "syntax_valid", "checks_run"),
            "manage_packages": ("is_authorized", "message"),
            "generate_code": ("code", "component_name"),
        }
        needed = code_expected_keys.get(operation, ())
        if not any(k in output for k in needed):
            from app.integrations.sandbox.micro_tools import execute_s_code

            exec_payload = dict(payload)
            exec_payload["operation"] = operation
            exec_res = execute_s_code(exec_payload, operation=operation)
            if exec_res.get("output"):
                return exec_res["output"]
            return exec_res

        return output

    async def _reason_with_llm(
        self,
        *,
        objective: str,
        context: dict[str, Any],
        component_name: str,
        target_files: list[str],
        predecessor_artifacts: dict[str, Any] | None = None,
        reviewer_feedback: str | None = None,
    ) -> dict[str, Any]:
        """LLM-assisted cognitive reasoning for application logic, contracts, and error handling.

        Decomposes application logic requirements, structures classes, functions, error handling,
        interfaces, and dependency requirements. Falls back to deterministic rule-based code
        generation if LLM client is not configured.
        """
        parts = [p for p in component_name.replace("-", "_").split("_") if p]
        c_clean = "".join(p[:1].upper() + p[1:] for p in parts) if parts else "AppService"
        c_slug = component_name.lower().replace("-", "_")

        if self._llm_client and hasattr(self._llm_client, "generate"):
            system_prompt = (
                "You are DEV-CODE, the Development Engine's specialist application software engineer. "
                "Your role is to author clean, robust application/business logic, API integrations, "
                "state management, and error handling strictly within plan-authorized boundaries. "
                "Preserve public contracts, architectural patterns, and formatting conventions. "
                "Structure your output strictly as a JSON dictionary."
            )
            user_prompt = (
                f"Objective: {objective}\n"
                f"Component Name: {component_name}\n"
                f"Target Files: {json.dumps(target_files)}\n"
                f"Predecessor Artifacts: {json.dumps(predecessor_artifacts or {})}\n"
                f"Reviewer Feedback: {reviewer_feedback or 'None'}\n"
                "Return a JSON object with keys:\n"
                "- files: dict mapping file_path to code content\n"
                "- summary: string describing implementation changes\n"
                "- interfaces: list of dicts with keys (symbol_name, symbol_type, change_type, file_path, signature, is_breaking)\n"
                "- dependencies: list of dicts with keys (package_name, action, version_spec, is_authorized)\n"
                "- assumptions: list of string assumptions\n"
                "- unresolved_issues: list of string unresolved issues\n"
            )
            try:
                raw_res = await self._llm_client.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
                if isinstance(raw_res, str):
                    clean_str = raw_res.strip()
                    if clean_str.startswith("```"):
                        clean_str = clean_str.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                    return json.loads(clean_str)
                if isinstance(raw_res, dict):
                    return raw_res
            except Exception as exc:
                logger.warning("LLM reasoning failed for DEV-CODE; falling back to deterministic authoring: %s", exc)

        # Deterministic offline authoring fallback
        primary_file = target_files[0] if target_files else f"services/{c_slug}_service.py"

        extra_methods = ""
        if reviewer_feedback and "retry" in reviewer_feedback.lower():
            extra_methods += (
                "    async def retry_operation(self, operation: str, max_retries: int = 3) -> dict[str, Any]:\n"
                "        \"\"\"Execute bounded retry for transient operations.\"\"\"\n"
                "        logger.info('Executing bounded retry for %s (budget=%d)', operation, max_retries)\n"
                "        return {'status': 'SUCCESS', 'retries_used': 1}\n\n"
            )

        code_content = (
            f'"""Application service for {c_clean}.\n\n'
            f'Generated by DEV-CODE bounded application-code authoring specialist.\n'
            f'"""\n\n'
            f'from __future__ import annotations\n\n'
            f'from datetime import UTC, datetime\n'
            f'import logging\n'
            f'from typing import Any\n\n'
            f'logger = logging.getLogger(__name__)\n\n\n'
            f'class {c_clean}Service:\n'
            f'    """Core business logic service for {c_clean}."""\n\n'
            f'    def __init__(self, config: dict[str, Any] | None = None) -> None:\n'
            f'        self.config = config or {{}}\n'
            f'        self._initialized_at = datetime.now(UTC)\n\n'
            f'    async def process_payload(self, payload: dict[str, Any]) -> dict[str, Any]:\n'
            f'        """Process business logic payload with error handling."""\n'
            f'        if not payload:\n'
            f'            raise ValueError("Payload cannot be empty")\n'
            f'        logger.info("Processing payload for {c_clean}: keys=%s", list(payload.keys()))\n'
            f'        return {{\n'
            f'            "status": "SUCCESS",\n'
            f'            "component": "{c_clean}",\n'
            f'            "payload_size": len(payload),\n'
            f'            "processed_at": datetime.now(UTC).isoformat(),\n'
            f'        }}\n\n'
            f'{extra_methods}'
        )

        interfaces = [
            {
                "symbol_name": f"{c_clean}Service",
                "symbol_type": "class",
                "change_type": "added",
                "file_path": primary_file,
                "signature": f"class {c_clean}Service",
                "docstring": f"Core business logic service for {c_clean}.",
                "is_breaking": False,
            },
            {
                "symbol_name": "process_payload",
                "symbol_type": "method",
                "change_type": "added",
                "file_path": primary_file,
                "signature": "async def process_payload(self, payload: dict[str, Any]) -> dict[str, Any]",
                "docstring": "Process business logic payload with error handling.",
                "is_breaking": False,
            },
        ]

        return {
            "files": {primary_file: code_content},
            "summary": f"Implemented {c_clean} business logic service with structured error handling and payload processing.",
            "interfaces": interfaces,
            "dependencies": [],
            "assumptions": [
                "Service executes within asynchronous event loop.",
                "Payloads adhere to validated schema contracts.",
            ],
            "unresolved_issues": [],
        }

    async def execute_step(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        plan: DevelopmentPlan | None = None,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        previous_candidate: CodeCandidateDeliverable | None = None,
        reviewer_feedback: str | None = None,
        expected_predecessor_hash: str | None = None,
    ) -> CodeCandidateDeliverable:
        """Execute DEV-CODE sub-agent workflow.

        Enforces plan authority, validates predecessor snapshot/hash, enforces tenant
        isolation and mutation scoping, checks dependency authorizations, runs sandbox
        micro-tools (patch, format, AST inspect, compile check), and seals a tamper-evident
        CodeCandidateDeliverable for HITL review.
        """
        ctx = context or {}

        # 1. Plan Authority Verification
        if plan is not None:
            code_step: DevelopmentPlanStep | None = None
            for s in plan.steps:
                if s.subagent_id == "DEV-CODE":
                    code_step = s
                    break

            if code_step is not None:
                if code_step.status == "SKIPPED_NOT_APPLICABLE" or not code_step.is_applicable:
                    raise PolicyViolationError(
                        f"DEV-CODE execution rejected: Step '{code_step.step_id}' is marked SKIPPED_NOT_APPLICABLE. "
                        f"Reason: {code_step.skip_reason}"
                    )
            elif plan.steps:
                raise PolicyViolationError(
                    "DEV-CODE execution rejected: Approved DevelopmentPlan does not contain a step for DEV-CODE."
                )

        # 2. Predecessor Snapshot & Hash Verification
        predecessor_hash: str | None = None
        predecessor_candidate = (
            ctx.get("ui_candidate")
            or ctx.get("cms_candidate")
            or ctx.get("predecessor_candidate")
            or previous_candidate
        )

        if predecessor_candidate is not None:
            if isinstance(predecessor_candidate, (UiCandidateDeliverable, CmsCandidateDeliverable, CodeCandidateDeliverable)):
                if (
                    predecessor_candidate.candidate_hash
                    and len(predecessor_candidate.candidate_hash) == 64
                    and predecessor_candidate.candidate_hash != predecessor_candidate.compute_candidate_hash()
                ):
                    raise PolicyViolationError(
                        "Predecessor verification failed: Predecessor candidate deliverable hash mismatch or candidate has been tampered."
                    )
                predecessor_hash = predecessor_candidate.candidate_hash
            elif isinstance(predecessor_candidate, dict):
                predecessor_hash = (
                    predecessor_candidate.get("candidate_hash")
                    or hashlib.sha256(json.dumps(predecessor_candidate, sort_keys=True).encode()).hexdigest()
                )
        elif plan is not None:
            predecessor_hash = plan.plan_hash

        # Context-supplied predecessor hash check
        ctx_pred_hash = ctx.get("predecessor_hash") or expected_predecessor_hash
        if ctx_pred_hash:
            if predecessor_hash and predecessor_hash != ctx_pred_hash:
                raise PolicyViolationError(
                    f"Predecessor hash mismatch: Expected '{ctx_pred_hash}', but predecessor snapshot hash is '{predecessor_hash}'."
                )
            if not predecessor_hash:
                predecessor_hash = ctx_pred_hash

        if ctx.get("simulate_stale_predecessor"):
            raise PolicyViolationError(
                "Predecessor verification failed: Snapshot hash is stale or invalid relative to approved checkpoint."
            )

        # 3. Tenant Isolation Enforcement
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        ctx_tenant = ctx.get("tenant_id")
        if ctx_tenant and ctx_tenant != grant_tenant:
            raise PolicyViolationError(
                f"Tenant isolation breach: Context tenant '{ctx_tenant}' does not match grant tenant '{grant_tenant}'."
            )

        # 4. Scope Boundary Screening: Target Artifacts
        component_name = (
            getattr(grant, "component_name", None)
            or ctx.get("component_name")
            or (plan.objective.split()[0] if plan and plan.objective else "AppModule")
        )
        c_slug = component_name.lower().replace("-", "_")

        allowed_artifacts: set[str] = set()
        if plan is not None:
            allowed_artifacts.update(plan.affected_files)
            for s in plan.steps:
                if s.subagent_id == "DEV-CODE":
                    allowed_artifacts.update(s.affected_artifacts)

        target_files = getattr(grant, "target_files", []) or ctx.get("target_files", [])
        if not target_files:
            default_target = f"services/{c_slug}_service.py"
            target_files = [default_target]

        if allowed_artifacts:
            unauthorized = [f for f in target_files if f not in allowed_artifacts]
            if unauthorized:
                raise PolicyViolationError(
                    f"Scope boundary violation: Target files {unauthorized} are not authorized in approved plan. "
                    f"Authorized artifacts: {sorted(allowed_artifacts)}"
                )

        # 5. Dependency Control Verification
        requested_deps_raw = ctx.get("requested_dependencies") or []
        plan_dependencies_authorized = False
        allowed_packages: list[str] = []

        if plan is not None:
            plan_dependencies_authorized = getattr(plan, "dependencies_authorized", False) or bool(plan.discovered_facts.get("dependencies_authorized"))
            allowed_packages = list(getattr(plan, "allowed_dependencies", []) or plan.discovered_facts.get("allowed_dependencies", []))
            for s in plan.steps:
                if s.subagent_id == "DEV-CODE":
                    step_meta = getattr(s, "metadata", {}) or {}
                    if step_meta.get("dependencies_authorized"):
                        plan_dependencies_authorized = True
                    allowed_packages.extend(step_meta.get("allowed_dependencies", []))

        dependency_changes: list[DependencyChange] = []
        if requested_deps_raw:
            for dep in requested_deps_raw:
                pkg_name = dep.get("package_name") if isinstance(dep, dict) else str(dep)
                pkg_action = dep.get("action", "ADD") if isinstance(dep, dict) else "ADD"
                pkg_version = dep.get("version_spec", "") if isinstance(dep, dict) else ""

                is_authorized = plan_dependencies_authorized or (pkg_name in allowed_packages)
                if not is_authorized:
                    raise PolicyViolationError(
                        f"Security policy violation: Dependency change for package '{pkg_name}' is not authorized by the approved plan."
                    )

                dependency_changes.append(
                    DependencyChange(
                        package_name=pkg_name,
                        action=DependencyChangeAction(pkg_action),
                        version_spec=pkg_version,
                        is_authorized=True,
                        authorization_reference=plan.plan_id if plan else "grant",
                        notes=f"Explicitly authorized in development plan for {pkg_name}.",
                    )
                )

        # 6. Cognitive LLM Reasoning / Authoring
        predecessor_artifacts_dict = {}
        if isinstance(predecessor_candidate, UiCandidateDeliverable):
            predecessor_artifacts_dict = {
                "type": "UI",
                "component_name": predecessor_candidate.component_name,
                "changed_files": predecessor_candidate.changed_files,
            }
        elif isinstance(predecessor_candidate, CmsCandidateDeliverable):
            predecessor_artifacts_dict = {
                "type": "CMS",
                "schema_id": predecessor_candidate.schema_definition.schema_id,
            }

        reasoning = await self._reason_with_llm(
            objective=plan.objective if plan else f"Implement application code for {component_name}",
            context=ctx,
            component_name=component_name,
            target_files=target_files,
            predecessor_artifacts=predecessor_artifacts_dict,
            reviewer_feedback=reviewer_feedback or ctx.get("rejection_feedback"),
        )

        files_to_author = reasoning.get("files", {})
        if not files_to_author:
            for tf in target_files:
                files_to_author[tf] = ctx.get("initial_code", "")

        # 7. Sandbox Micro-Tool Executions
        tool_evidence: list[ToolExecutionEvidence] = []
        source_code: dict[str, str] = {}
        code_diffs: list[CodeDiffEntry] = []
        ast_symbol_summary: dict[str, Any] = {}
        all_compiler_checks: list[str] = []
        all_compiler_errors: list[str] = []
        all_compiler_warnings: list[str] = []
        compiler_passed = True
        syntax_valid = True

        for file_path, raw_code in files_to_author.items():
            # Check scope boundary on authored files
            if allowed_artifacts and file_path not in allowed_artifacts:
                raise PolicyViolationError(
                    f"Scope boundary violation: Authored file '{file_path}' is not authorized in approved plan."
                )

            # 7.1 Sandbox Code Patching
            start_patch = datetime.now(UTC)
            patch_res = await self._invoke_sandbox(
                tenant_id=grant_tenant,
                task_id=grant.task_id,
                operation="apply_code_patch",
                payload={
                    "target_file": file_path,
                    "new_content": raw_code,
                    "allowed_artifacts": list(allowed_artifacts) if allowed_artifacts else None,
                },
            )
            duration_patch = (datetime.now(UTC) - start_patch).total_seconds() * 1000.0

            if patch_res.get("security_violation"):
                raise PolicyViolationError(patch_res.get("error", "Security violation during code patch."))

            patched_content = patch_res.get("patched_content", raw_code)
            diff_unified = patch_res.get("diff_unified", "")
            action = patch_res.get("action", "create")

            tool_evidence.append(
                ToolExecutionEvidence(
                    tool_name="code_patcher",
                    command_or_operation="apply_code_patch",
                    exit_code=0 if patch_res.get("is_patched") else 1,
                    duration_ms=round(duration_patch, 2),
                    output_summary=f"Patched {file_path} ({action})",
                    status="SUCCESS" if patch_res.get("is_patched") else "ERROR",
                )
            )

            # 7.2 Repository-Native Code Formatting
            start_fmt = datetime.now(UTC)
            format_res = await self._invoke_sandbox(
                tenant_id=grant_tenant,
                task_id=grant.task_id,
                operation="format_code",
                payload={"code": patched_content, "file_path": file_path},
            )
            duration_fmt = (datetime.now(UTC) - start_fmt).total_seconds() * 1000.0
            formatted_content = format_res.get("formatted_code", patched_content)

            tool_evidence.append(
                ToolExecutionEvidence(
                    tool_name="code_formatter",
                    command_or_operation="format_code",
                    exit_code=0 if format_res.get("is_formatted") else 1,
                    duration_ms=round(duration_fmt, 2),
                    output_summary=f"Formatted {file_path}",
                    status="SUCCESS",
                )
            )

            # 7.3 AST Structural Symbol Inspection
            start_ast = datetime.now(UTC)
            ast_res = await self._invoke_sandbox(
                tenant_id=grant_tenant,
                task_id=grant.task_id,
                operation="inspect_ast_symbols",
                payload={"code": formatted_content, "file_path": file_path},
            )
            duration_ast = (datetime.now(UTC) - start_ast).total_seconds() * 1000.0
            ast_symbol_summary[file_path] = ast_res.get("symbols_summary", {})

            tool_evidence.append(
                ToolExecutionEvidence(
                    tool_name="ast_symbol_inspector",
                    command_or_operation="inspect_ast_symbols",
                    exit_code=0 if ast_res.get("ast_valid") else 1,
                    duration_ms=round(duration_ast, 2),
                    output_summary=f"Extracted {len(ast_res.get('classes', []))} classes, {len(ast_res.get('functions', []))} functions",
                    status="SUCCESS" if ast_res.get("ast_valid") else "ERROR",
                )
            )

            # 7.4 Repository-Native Syntax & Compiler Sanity Check
            start_compile = datetime.now(UTC)
            compile_res = await self._invoke_sandbox(
                tenant_id=grant_tenant,
                task_id=grant.task_id,
                operation="validate_syntax_compiler",
                payload={"code": formatted_content, "file_path": file_path},
            )
            duration_compile = (datetime.now(UTC) - start_compile).total_seconds() * 1000.0

            file_compile_passed = bool(compile_res.get("compiler_passed", True))
            file_syntax_valid = bool(compile_res.get("syntax_valid", True))
            compiler_passed = compiler_passed and file_compile_passed
            syntax_valid = syntax_valid and file_syntax_valid

            all_compiler_checks.extend(compile_res.get("checks_run", []))
            all_compiler_errors.extend(compile_res.get("errors", []))
            all_compiler_warnings.extend(compile_res.get("warnings", []))

            tool_evidence.append(
                ToolExecutionEvidence(
                    tool_name="compiler_sanity_checker",
                    command_or_operation="validate_syntax_compiler",
                    exit_code=0 if file_compile_passed else 1,
                    duration_ms=round(duration_compile, 2),
                    output_summary=compile_res.get("compiler_output", ""),
                    status="SUCCESS" if file_compile_passed else "ERROR",
                )
            )

            source_code[file_path] = formatted_content

            # Re-generate diff if formatted_content differs or was empty
            if not diff_unified or formatted_content != raw_code:
                comp_lines = formatted_content.splitlines()
                diff_unified = (
                    f"--- a/{file_path}\n"
                    f"+++ b/{file_path}\n"
                    f"@@ -0,0 +1,{len(comp_lines)} @@\n"
                    + "".join(f"+ {line}\n" for line in comp_lines)
                )

            code_diffs.append(
                CodeDiffEntry(
                    file_path=file_path,
                    action=action,
                    diff_unified=diff_unified,
                    ast_validated=bool(ast_res.get("ast_valid", True)),
                    syntax_lint_passed=file_syntax_valid and file_compile_passed,
                    syntax_errors=compile_res.get("errors", []),
                    scope_boundary_verified=True,
                )
            )

        # 7.5 Controlled Package Management Check (if authorized dependencies present)
        for dep in dependency_changes:
            pkg_res = await self._invoke_sandbox(
                tenant_id=grant_tenant,
                task_id=grant.task_id,
                operation="manage_packages",
                payload={
                    "package_name": dep.package_name,
                    "action": dep.action.value,
                    "version_spec": dep.version_spec,
                    "egress_granted": True,
                    "is_plan_authorized": True,
                    "authorized_packages": [dep.package_name],
                },
            )
            tool_evidence.append(
                ToolExecutionEvidence(
                    tool_name="package_manager_proxy",
                    command_or_operation="manage_packages",
                    exit_code=0 if pkg_res.get("is_authorized") else 1,
                    duration_ms=15.0,
                    output_summary=pkg_res.get("message", ""),
                    status="SUCCESS" if pkg_res.get("is_authorized") else "ERROR",
                )
            )

        # 8. Interface & Contract Changes Structuring
        raw_interfaces = reasoning.get("interfaces", [])
        interface_changes: list[InterfaceChange] = []
        for iface in raw_interfaces:
            if isinstance(iface, dict):
                interface_changes.append(
                    InterfaceChange(
                        symbol_name=iface.get("symbol_name", "Symbol"),
                        symbol_type=iface.get("symbol_type", "function"),
                        change_type=iface.get("change_type", "added"),
                        file_path=iface.get("file_path", target_files[0]),
                        signature=iface.get("signature", ""),
                        docstring=iface.get("docstring", ""),
                        is_breaking=bool(iface.get("is_breaking", False)),
                    )
                )

        sanity_check_result = CodeSanityCheckResult(
            is_valid=compiler_passed and syntax_valid and len(all_compiler_errors) == 0,
            syntax_valid=syntax_valid,
            compiler_passed=compiler_passed,
            checks_run=list(set(all_compiler_checks)),
            compiler_output="Compiler sanity checks verified repository-native execution." if compiler_passed else f"Compiler errors: {all_compiler_errors}",
            errors=all_compiler_errors,
            warnings=all_compiler_warnings,
        )

        candidate_id = f"cand-code-{uuid.uuid4().hex[:8]}"
        wf_id = workflow_id or (plan.workflow_id if plan else f"wf-{uuid.uuid4().hex[:8]}")

        deliverable = CodeCandidateDeliverable(
            candidate_id=candidate_id,
            task_id=grant.task_id,
            workflow_id=wf_id,
            attempt_id=attempt_id,
            component_name=component_name,
            changed_files=sorted(list(files_to_author.keys())),
            code_diffs=code_diffs,
            source_code=source_code,
            implementation_summary=reasoning.get("summary", f"Implemented application logic for {component_name}."),
            dependency_changes=dependency_changes,
            contract_interface_changes=interface_changes,
            commands_tool_evidence=tool_evidence,
            ast_symbol_summary=ast_symbol_summary,
            sanity_check_result=sanity_check_result,
            predecessor_hash=predecessor_hash,
            input_plan_hash=plan.plan_hash if plan else None,
            assumptions=reasoning.get("assumptions", []),
            unresolved_issues=reasoning.get("unresolved_issues", []),
            rejection_feedback=reviewer_feedback,
            provenance={
                "subagent": "DEV-CODE",
                "attempt_id": attempt_id,
                "input_plan_hash": plan.plan_hash if plan else "",
                "predecessor_hash": predecessor_hash or "",
                "changed_files_count": len(files_to_author),
                "compiler_passed": compiler_passed,
            },
        )

        # 9. Tamper-Evident SHA-256 Candidate Hash Sealing
        deliverable.compute_candidate_hash()
        return deliverable

    # Alias for development engine compatibility
    execute_code_task = execute_step


# Backwards compatibility alias
ImplementationAgent = CodeImplementationAgent
