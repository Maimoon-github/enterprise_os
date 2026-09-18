"""DEV-PLAN: Development Planning & Impact Sub-Agent (DE-06).

Converts an authorized Intelligence Engine Development Task Grant into a validated,
ordered, human-approvable Development Execution Plan without modifying project artifacts.
Runs inside an isolated sandbox with read-only capabilities.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import uuid
from typing import Any

from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.client import SandboxClient
from app.schemas.agent_contracts import TaskGrant
from app.schemas.development.development_plan import (
    DevelopmentPlan,
    DevelopmentPlanStep,
    SUBAGENT_CMS,
    SUBAGENT_CODE,
    SUBAGENT_REL,
    SUBAGENT_SEC,
    SUBAGENT_UI,
    SUBAGENT_VERIFY,
)
from app.schemas.development.development_result import DevelopmentTaskGrant
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import SandboxCapability, SandboxInvocationMandate


class DevelopmentPlanningAgent:
    """DEV-PLAN sub-agent for W_DEV.

    Performs:
    - Requirements decomposition
    - Read-only repository and architecture analysis (AST, symbols, dependencies, schemas)
    - Dependency and change-impact analysis
    - Affected artifact identification
    - Risk classification and acceptance criteria formulation
    - Generation of sealed, immutable, policy-validated DevelopmentPlan
    """

    def __init__(
        self,
        sandbox_client: SandboxClient,
        llm_client: Any = None,
    ) -> None:
        self._sandbox_client = sandbox_client
        self._llm_client = llm_client

    async def _reason_with_llm(
        self,
        *,
        objective: str,
        task_id: str,
        component_name: str,
        target_files: list[str],
        context: dict[str, Any],
        reviewer_feedback: str | None = None,
        discovered_facts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """LLM cognitive reasoning loop for DEV-PLAN: Think -> Ponder -> Reflect -> React.

        - Think & Ponder: Decomposes requirements, evaluates architectural impacts and risks.
        - Reflect: Processes reviewer feedback and past attempt history to resolve gaps.
        - React: Synthesizes risk classification, architectural rationale, and tailored acceptance criteria.
        Falls back to deterministic rule-based planning if LLM client is unconfigured.
        """
        cognitive_result: dict[str, Any] = {
            "thought_process": f"Pondered architectural requirements for '{objective}' on '{component_name}'.",
            "architectural_insights": [
                f"Scoped impact across {len(target_files)} target file(s).",
                "Enforcing read-only isolation during analysis phase.",
            ],
            "risk_assessment": "Standard development risk tier.",
            "reflection_notes": f"Incorporated feedback: {reviewer_feedback}" if reviewer_feedback else "Initial attempt baseline.",
        }

        if self._llm_client is not None:
            system_prompt = (
                "You are DEV-PLAN, the Development Engine's specialist planning and impact-analysis agent. "
                "Your role is to think, ponder, and reflect upon software development task grants, "
                "repository architecture, dependency risks, and reviewer feedback to produce "
                "robust architectural rationales and risk classifications. "
                "Structure your output strictly as a JSON dictionary."
            )
            user_prompt = (
                f"Task ID: {task_id}\n"
                f"Objective: {objective}\n"
                f"Component Name: {component_name}\n"
                f"Target Files: {json.dumps(target_files)}\n"
                f"Reviewer Feedback: {reviewer_feedback or 'None'}\n"
                f"Discovered Facts: {json.dumps(discovered_facts or {})}\n"
                "Return a JSON object with keys:\n"
                "- thought_process: string description of cognitive analysis\n"
                "- architectural_insights: list of strings detailing architecture/impact insights\n"
                "- risk_assessment: string assessment of technical and integration risk\n"
                "- reflection_notes: string reflecting on prior feedback or edge cases\n"
                "- additional_assumptions: list of strings (optional)\n"
            )
            try:
                raw_res: Any = None
                if hasattr(self._llm_client, "generate"):
                    raw_res = await self._llm_client.generate(prompt=user_prompt, system=system_prompt)
                elif hasattr(self._llm_client, "complete"):
                    raw_res = await self._llm_client.complete(user_prompt, system=system_prompt)
                elif callable(self._llm_client):
                    raw_res = await self._llm_client(user_prompt)

                parsed = None
                if isinstance(raw_res, dict):
                    parsed = raw_res
                elif isinstance(raw_res, str):
                    clean_str = raw_res.strip()
                    if clean_str.startswith("```"):
                        clean_str = clean_str.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                    parsed = json.loads(clean_str)
                if isinstance(parsed, dict):
                    for k in ("thought_process", "architectural_insights", "risk_assessment", "reflection_notes", "additional_assumptions"):
                        if k in parsed:
                            cognitive_result[k] = parsed[k]
            except Exception:
                pass

        return cognitive_result


    async def _execute_read_only_analysis(
        self,
        *,
        tenant_id: str,
        task_id: str,
        operation: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a read-only inspection operation inside the isolated sandbox."""
        mandate = SandboxInvocationMandate(
            tenant_id=tenant_id,
            task_id=task_id,
            worker_role=WorkerRole.DEVELOPMENT,
            capability=SandboxCapability.CODE,
            operation=operation,
            payload=payload,
        )
        if hasattr(self._sandbox_client, "invoke"):
            result = await self._sandbox_client.invoke(mandate)
        else:
            result = await self._sandbox_client.execute(mandate)
        if not result.success:
            return {"error": result.error or "Sandbox analysis failed"}
        return result.sanitized_output or {}

    def _determine_step_applicability(
        self,
        grant: TaskGrant | DevelopmentTaskGrant,
        context: dict[str, Any],
    ) -> tuple[bool, str | None, bool, str | None, bool, str | None]:
        """Determine applicability and skip reasons for conditionally excludable sub-agents.

        Returns:
            (cms_needed, cms_skip_reason, ui_needed, ui_skip_reason, code_needed, code_skip_reason)
        """
        objective = grant.objective.lower()
        task_scope = getattr(grant, "task_scope", "").lower()
        context_str = json.dumps(context).lower()
        target_files = [str(f).lower() for f in getattr(grant, "target_files", [])]

        # 1. DEV-CMS: Content & Schema Modeling
        cms_indicators = ("cms", "schema", "content_model", "content model", "staged_cms", "page_model")
        has_cms_indicators = any(ind in objective or ind in task_scope or ind in context_str for ind in cms_indicators) or any("schema" in f for f in target_files)
        has_explicit_cms_skip = context.get("skip_cms") is True or "no cms" in objective
        if has_explicit_cms_skip or not has_cms_indicators:
            cms_needed = False
            cms_skip_reason = context.get("cms_skip_reason") or "No CMS content models or schema extensions required for this task."
        else:
            cms_needed = True
            cms_skip_reason = None

        # 2. DEV-UI: Responsive UI Templates & Layouts
        ui_indicators = ("ui", "template", "layout", "responsive", "frontend", "html", "css", "view", "page", "styling")
        has_ui_target_files = any(f.endswith((".html", ".css", ".tsx", ".jsx", ".vue")) for f in target_files)
        has_ui_indicators = any(ind in objective or ind in task_scope or ind in context_str for ind in ui_indicators) or has_ui_target_files
        has_explicit_ui_skip = context.get("skip_ui") is True or "backend only" in objective or "no ui" in objective
        if has_explicit_ui_skip or not has_ui_indicators:
            ui_needed = False
            ui_skip_reason = context.get("ui_skip_reason") or "No UI templates or visual components required for this task."
        else:
            ui_needed = True
            ui_skip_reason = None

        # 3. DEV-CODE: Backend Logic & Code Diffs
        code_indicators = ("code", "diff", "logic", "handler", "api", "backend", "endpoint", "function", "service", "python", "query", "database", "auth")
        has_code_target_files = any(f.endswith((".py", ".ts", ".js", ".go", ".rs", ".sql")) for f in target_files)
        has_code_indicators = any(ind in objective or ind in task_scope or ind in context_str for ind in code_indicators) or has_code_target_files
        has_explicit_code_skip = context.get("skip_code") is True or "no backend code" in objective
        if has_explicit_code_skip or (not has_code_indicators and (cms_needed or ui_needed)):
            code_needed = False
            code_skip_reason = context.get("code_skip_reason") or "No backend logic or source code diffs required for this task."
        else:
            code_needed = True
            code_skip_reason = None

        return (
            cms_needed,
            cms_skip_reason,
            ui_needed,
            ui_skip_reason,
            code_needed,
            code_skip_reason,
        )

    async def create_plan(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        previous_plan: DevelopmentPlan | None = None,
        reviewer_feedback: str | None = None,
        is_release_producing: bool = True,
    ) -> DevelopmentPlan:
        """Alias for generate_plan."""
        return await self.generate_plan(
            grant=grant,
            context=context,
            workflow_id=workflow_id,
            attempt_id=attempt_id,
            previous_plan=previous_plan,
            reviewer_feedback=reviewer_feedback,
            is_release_producing=is_release_producing,
        )

    async def generate_plan(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        previous_plan: DevelopmentPlan | None = None,
        reviewer_feedback: str | None = None,
        is_release_producing: bool = True,
    ) -> DevelopmentPlan:
        """Convert a task grant and context into a sealed, policy-validated DevelopmentPlan.

        Strictly enforces:
        - Read-only repository inspection (zero project mutations).
        - Mandatory DEV-VERIFY, DEV-SEC, and DEV-REL inclusion.
        - Justified conditional exclusion of DEV-CMS, DEV-UI, or DEV-CODE.
        - Immutable retry attempt generation on revision without modifying previous plan.
        """
        if grant is None:
            raise PolicyViolationError("Task grant cannot be None for DEV-PLAN invocation.")

        if grant.worker_role != WorkerRole.DEVELOPMENT:
            raise PolicyViolationError(
                f"Unauthorized worker role '{grant.worker_role}'; DEV-PLAN only accepts '{WorkerRole.DEVELOPMENT}'."
            )

        if hasattr(grant, "is_expired") and grant.is_expired():
            raise PolicyViolationError("Task grant has expired for DEV-PLAN invocation.")
        if (
            hasattr(grant, "expires_at")
            and grant.expires_at is not None
            and grant.expires_at < datetime.now(UTC)
        ):
            raise PolicyViolationError("Task grant has expired for DEV-PLAN invocation.")

        if not getattr(grant, "tenant_scope", None) or not grant.tenant_scope.tenant_id:
            raise PolicyViolationError("Task grant must include a valid tenant scope for DEV-PLAN invocation.")

        if hasattr(grant, "sandbox_capabilities") and grant.sandbox_capabilities:
            for cap in grant.sandbox_capabilities:
                cap_str = str(getattr(cap, "value", cap))
                if cap_str not in (SandboxCapability.CODE.value, "S_CODE", "CODE"):
                    raise PolicyViolationError(
                        f"Unauthorized sandbox capability '{cap_str}' in task grant; "
                        "DEV-PLAN only permits S_CODE read-only capability."
                    )

        ctx = context or {}
        tenant_id = grant.tenant_scope.tenant_id
        wf_id = workflow_id or f"wf-{uuid.uuid4().hex[:10]}"
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        effective_feedback = reviewer_feedback or ctx.get("rejection_notes") or ctx.get("reviewer_feedback")

        # 1. Read-Only Repository & Architecture Analysis (Sandbox S_CODE)
        discovered_facts: dict[str, Any] = {
            "component_name": getattr(grant, "component_name", "Component"),
            "target_files": getattr(grant, "target_files", []),
            "token_budget": getattr(grant, "token_budget", 0),
        }

        # Inspect target files in read-only sandbox mode
        files_to_inspect = getattr(grant, "target_files", []) or ["components/component.py"]
        file_inspection_report = await self._execute_read_only_analysis(
            tenant_id=tenant_id,
            task_id=grant.task_id,
            operation="inspect_files",
            payload={"files_to_inspect": files_to_inspect, "read_only": True},
        )
        discovered_facts["inspected_files"] = file_inspection_report

        code_content = ctx.get("code") or ctx.get("source_code") or ""
        manifest_content = ctx.get("manifest") or ctx.get("dependencies") or ""

        if code_content:
            symbol_report = await self._execute_read_only_analysis(
                tenant_id=tenant_id,
                task_id=grant.task_id,
                operation="extract_symbols",
                payload={"code": code_content},
            )
            discovered_facts["symbols"] = symbol_report

        if manifest_content or code_content:
            dep_report = await self._execute_read_only_analysis(
                tenant_id=tenant_id,
                task_id=grant.task_id,
                operation="inspect_dependencies",
                payload={"manifest": manifest_content, "code": code_content},
            )
            discovered_facts["dependencies"] = dep_report

        # 1.1 Cognitive Reasoning Loop: Think -> Ponder -> Reflect -> React
        cognitive_reasoning = await self._reason_with_llm(
            objective=grant.objective,
            task_id=grant.task_id,
            component_name=getattr(grant, "component_name", "Component"),
            target_files=files_to_inspect,
            context=ctx,
            reviewer_feedback=effective_feedback,
            discovered_facts=discovered_facts,
        )
        discovered_facts["cognitive_reasoning"] = cognitive_reasoning

        # 2. Determine Sub-Agent Step Applicability & Exclusions

        (
            cms_needed,
            cms_skip_reason,
            ui_needed,
            ui_skip_reason,
            code_needed,
            code_skip_reason,
        ) = self._determine_step_applicability(grant, ctx)

        # 3. Build Ordered Execution Steps
        steps: list[DevelopmentPlanStep] = []
        active_step_ids: list[str] = []

        # Step 1: DEV-CMS (Conditional)
        step_cms_id = "step-01-cms"
        steps.append(
            DevelopmentPlanStep(
                step_id=step_cms_id,
                subagent_id=SUBAGENT_CMS,
                order=1,
                name="CMS Schema & Model Specification",
                description="Formulate structured content models and backward-compatible schema definitions.",
                status="REQUIRED" if cms_needed else "SKIPPED_NOT_APPLICABLE",
                skip_reason=None if cms_needed else cms_skip_reason,
                dependencies=[],
                required_capabilities=["schema_validation"],
                required_tools=["schema_introspector"],
                affected_artifacts=["schemas/content_model.json"] if cms_needed else [],
                risk_class="LOW",
                acceptance_criteria=[
                    "CMS models match staged T06 expectations",
                    "Backward compatibility verified with zero field collisions",
                ],
            )
        )
        if cms_needed:
            active_step_ids.append(step_cms_id)

        grant_target_files = [str(f) for f in getattr(grant, "target_files", [])]
        ui_targets = [f for f in grant_target_files if f.endswith((".html", ".css", ".tsx", ".jsx", ".vue"))]
        code_targets = [f for f in grant_target_files if f not in ui_targets and not f.endswith(".json")]

        ui_artifacts = ui_targets if ui_targets else (["templates/component.html"] if ui_needed else [])
        code_artifacts = code_targets if code_targets else (["components/component.py"] if code_needed else [])

        # Step 2: DEV-UI (Conditional)
        step_ui_id = "step-02-ui"
        ui_deps = list(active_step_ids)
        steps.append(
            DevelopmentPlanStep(
                step_id=step_ui_id,
                subagent_id=SUBAGENT_UI,
                order=2,
                name="Responsive Layout & UI Templates",
                description="Construct mobile, tablet, and desktop UI component templates conforming to brand voice.",
                status="REQUIRED" if ui_needed else "SKIPPED_NOT_APPLICABLE",
                skip_reason=None if ui_needed else ui_skip_reason,
                dependencies=ui_deps,
                required_capabilities=["template_rendering"],
                required_tools=["template_generator"],
                affected_artifacts=ui_artifacts,
                risk_class="LOW",
                acceptance_criteria=[
                    "Mobile, tablet, and desktop responsive breakpoints validated",
                    "Brand rules and accessibility constraints satisfied",
                ],
            )
        )
        if ui_needed:
            active_step_ids.append(step_ui_id)

        # Step 3: DEV-CODE (Conditional)
        step_code_id = "step-03-code"
        code_deps = list(active_step_ids)
        steps.append(
            DevelopmentPlanStep(
                step_id=step_code_id,
                subagent_id=SUBAGENT_CODE,
                order=3,
                name="Deterministic Code Diff Engineering",
                description="Implement minimal, deterministic code diffs and logic within bounded sandbox.",
                status="REQUIRED" if code_needed else "SKIPPED_NOT_APPLICABLE",
                skip_reason=None if code_needed else code_skip_reason,
                dependencies=code_deps,
                required_capabilities=["ast_parsing", "diff_generation"],
                required_tools=["ast_parser", "diff_generator"],
                affected_artifacts=code_artifacts,
                risk_class="MEDIUM",
                acceptance_criteria=[
                    "Syntax and AST clean with zero parse errors",
                    "Path traversal safeguards strictly enforced",
                ],
            )
        )
        if code_needed:
            active_step_ids.append(step_code_id)

        # Step 4: DEV-VERIFY (Mandatory)
        step_verify_id = "step-04-verify"
        verify_deps = list(active_step_ids)
        verify_criteria = [
            "All test assertions pass with zero failures",
            "Lint checks and AST validation complete cleanly",
        ]
        if effective_feedback and any(w in effective_feedback.lower() for w in ("test", "verify", "assert", "coverage")):
            verify_criteria.append(f"Addressed feedback: {effective_feedback}")

        steps.append(
            DevelopmentPlanStep(
                step_id=step_verify_id,
                subagent_id=SUBAGENT_VERIFY,
                order=4,
                name="Automated Syntax, AST & Test Verification",
                description="Execute automated linters, syntax checks, and regression test suites in sandbox.",
                status="REQUIRED",
                skip_reason=None,
                dependencies=verify_deps,
                required_capabilities=["test_execution", "linting"],
                required_tools=["code_linter", "ast_parser"],
                affected_artifacts=["reports/test_results.json"],
                risk_class="LOW",
                acceptance_criteria=verify_criteria,
            )
        )
        active_step_ids.append(step_verify_id)

        # Step 5: DEV-SEC (Mandatory)
        step_sec_id = "step-05-sec"
        sec_criteria = [
            "Zero hardcoded secrets, keys, or credentials detected",
            "Sandbox isolation boundaries verified intact",
        ]
        if effective_feedback and any(w in effective_feedback.lower() for w in ("sec", "csrf", "sanitiz", "vuln", "auth", "input")):
            sec_criteria.append(f"Addressed feedback: {effective_feedback}")

        steps.append(
            DevelopmentPlanStep(
                step_id=step_sec_id,
                subagent_id=SUBAGENT_SEC,
                order=5,
                name="Static Security, Secret & Boundary Verification",
                description="Screen codebase for secret leaks, traversal exploits, and egress policy compliance.",
                status="REQUIRED",
                skip_reason=None,
                dependencies=[step_verify_id],
                required_capabilities=["security_screening"],
                required_tools=["secret_scanner", "boundary_validator"],
                affected_artifacts=["reports/security_audit.json"],
                risk_class="LOW",
                acceptance_criteria=sec_criteria,
            )
        )
        active_step_ids.append(step_sec_id)

        # Step 6: DEV-REL (Mandatory)
        step_rel_id = "step-06-rel"
        steps.append(
            DevelopmentPlanStep(
                step_id=step_rel_id,
                subagent_id=SUBAGENT_REL,
                order=6,
                name="Artifact Sealing, Provenance & Release Attestation",
                description="Package deliverables, seal hashes, record DE-05 provenance, and generate SLSA attestation.",
                status="REQUIRED",
                skip_reason=None,
                dependencies=[step_sec_id],
                required_capabilities=["cryptographic_signing", "provenance_recording"],
                required_tools=["slsa_attestation_generator", "hash_sealer"],
                affected_artifacts=["dist/release_bundle.tar.gz", "attestation.json"],
                risk_class="LOW",
                acceptance_criteria=[
                    "Deterministic output snapshot hash generated and signed",
                    "SLSA v1.0 / in-toto attestation generated and chained to tenant ledger",
                ],
            )
        )

        # 4. Resolve Affected Files
        affected_files: list[str] = []
        for s in steps:
            if s.status == "REQUIRED":
                affected_files.extend(s.affected_artifacts)
        for f in grant_target_files:
            if f not in affected_files:
                affected_files.append(f)
        if not affected_files:
            affected_files = ["dist/deliverable.json"]

        # 5. Handle Rejection & Reviewer Feedback
        assumptions = [
            "Source repository is isolated and read-only during planning",
            "Execution leases are single-tenant and concurrency-bounded (max_concurrency=1)",
        ]
        unresolved_items: list[str] = []

        if effective_feedback:
            assumptions.append(f"Revised under attempt {attempt_id} addressing human feedback: {effective_feedback}")
            unresolved_items.append(f"Reviewer feedback incorporated: {effective_feedback}")

        for extra in cognitive_reasoning.get("additional_assumptions", []):
            if isinstance(extra, str) and extra not in assumptions:
                assumptions.append(extra)


        # 6. Risk Tiering
        grant_risk = getattr(grant, "risk_tier", "LOW").upper()
        risk_class = grant_risk if grant_risk in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else "LOW"

        # 7. Plan Versioning
        if previous_plan:
            try:
                prev_v = int(str(previous_plan.plan_version).split(".")[0])
                plan_version = prev_v + 1
            except Exception:
                plan_version = 2
        else:
            plan_version = 1

        # 8. Construct and Validate Plan
        plan = DevelopmentPlan(
            plan_id=plan_id,
            task_id=grant.task_id,
            workflow_id=wf_id,
            attempt_id=attempt_id,
            plan_version=plan_version,
            objective=grant.objective,
            architecture_summary=f"W_DEV execution pipeline for '{grant.task_id}' with {len(active_step_ids)} active sub-agent steps.",
            change_impact_summary=f"Modifies/generates {len(affected_files)} deliverables across {len(steps)} planned steps.",
            affected_files=sorted(list(set(affected_files))),
            steps=steps,
            risk_class=risk_class,  # type: ignore[arg-type]
            assumptions=assumptions,
            unresolved_items=unresolved_items,
            discovered_facts=discovered_facts,
            plan_hash="",
            status="DRAFT",
            rejection_feedback=effective_feedback,
        )

        # Enforce governance policy before sealing
        plan.validate_policy(is_release_producing=is_release_producing)

        # Seal candidate
        computed_hash = plan.compute_plan_hash()
        sealed_plan = plan.model_copy(update={
            "plan_hash": computed_hash,
            "status": "SEALED",
        })

        return sealed_plan
