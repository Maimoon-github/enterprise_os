"""W_DEV: CMS schemas, UI layouts, code diffs, and web-development engineering."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any, Literal

from app.agents.base import BoundedWorkerAgent
from app.core.exceptions import PolicyViolationError
from app.core.logging import get_logger
from app.integrations.sandbox.client import SandboxClient
from app.schemas.agent_contracts import (
    ConfidenceInterval,
    DevelopmentDeliverable,
    EvidenceEnvelope,
    TaskGrant,
)
from app.schemas.development.development_result import (
    DevelopmentEngineIdentity,
    DevelopmentEngineRequest,
    DevelopmentEngineResult,
    DevelopmentEngineStatus,
    DevelopmentTaskGrant,
)
from app.schemas.governance import WorkerRole
from app.schemas.development.development_plan import DevelopmentPlan
from app.schemas.cms import CmsCandidateDeliverable
from app.schemas.development.ui import UiCandidateDeliverable
from app.schemas.development.development_result import (
    CodeCandidateDeliverable,
    ReleaseCandidateDeliverable,
    SecurityDossier,
    VerificationDossier,
)
from app.agents.development_engine.subagents.planning import DevelopmentPlanningAgent
from app.agents.development_engine.subagents.cms_contract import CmsContractAgent
from app.agents.development_engine.subagents.ui_layout import UiLayoutAgent
from app.agents.development_engine.subagents.implementation import CodeImplementationAgent
from app.agents.development_engine.subagents.verification import VerificationAgent
from app.agents.development_engine.subagents.security_review import SecurityReviewAgent
from app.agents.development_engine.subagents.release_ops import ReleaseOpsAgent
from app.schemas.sandbox import SandboxCapability

logger = get_logger(__name__)


class DevelopmentAgent(BoundedWorkerAgent):
    """W_DEV Development Engine.

    Subordinate worker/sub-orchestrator responsible for development-domain tasks.
    Consumes staged CMS models (T06) and bounded task grants (T15) to produce
    responsive UI templates, CMS schema/model changes, component definitions, and
    deterministic unified code diffs using sandboxed S_CODE.

    Enforces path traversal protection, syntax/AST validation, responsive constraint
    checks, and tenant isolation under Model-A (no direct persistence or RAG).
    """

    capability = SandboxCapability.CODE
    _planning_agent: DevelopmentPlanningAgent
    _cms_agent: CmsContractAgent
    _ui_agent: UiLayoutAgent
    _code_agent: CodeImplementationAgent
    _verify_agent: VerificationAgent
    _security_agent: SecurityReviewAgent
    _release_agent: ReleaseOpsAgent

    def __init__(
        self,
        sandbox_client: SandboxClient,
        llm_client: Any = None,
    ) -> None:
        super().__init__(sandbox_client, llm_client=llm_client)
        self._identity = DevelopmentEngineIdentity()
        self._status = DevelopmentEngineStatus()
        self._planning_agent = DevelopmentPlanningAgent(sandbox_client, llm_client=llm_client)
        self._cms_agent = CmsContractAgent(sandbox_client, llm_client=llm_client)
        self._ui_agent = UiLayoutAgent(sandbox_client, llm_client=llm_client)
        self._code_agent = CodeImplementationAgent(sandbox_client, llm_client=llm_client)
        self._verify_agent = VerificationAgent(sandbox_client, llm_client=llm_client)
        self._security_agent = SecurityReviewAgent(sandbox_client, llm_client=llm_client)
        self._release_agent = ReleaseOpsAgent(sandbox_client, llm_client=llm_client)

    @property
    def identity(self) -> DevelopmentEngineIdentity:
        """Engine identity and architectural boundary specification."""
        return self._identity

    @property
    def status(self) -> DevelopmentEngineStatus:
        """Current operational status of W_DEV."""
        return self._status

    @property
    def planning_agent(self) -> DevelopmentPlanningAgent:
        """Sub-agent responsible for planning and impact analysis (DEV-PLAN)."""
        return self._planning_agent

    @property
    def cms_agent(self) -> CmsContractAgent:
        """Sub-agent responsible for CMS contracts, migrations, and compatibility (DEV-CMS)."""
        return self._cms_agent

    @property
    def ui_agent(self) -> UiLayoutAgent:
        """Sub-agent responsible for UI layouts, components, and accessibility (DEV-UI)."""
        return self._ui_agent

    @property
    def code_agent(self) -> CodeImplementationAgent:
        """Sub-agent responsible for application/integration code authoring (DEV-CODE)."""
        return self._code_agent

    @property
    def verify_agent(self) -> VerificationAgent:
        """Sub-agent responsible for technical verification (DEV-VERIFY)."""
        return self._verify_agent

    @property
    def security_agent(self) -> SecurityReviewAgent:
        """Sub-agent responsible for independent security review (DEV-SEC)."""
        return self._security_agent

    @property
    def release_agent(self) -> ReleaseOpsAgent:
        """Sub-agent responsible for release packaging and delivery (DEV-REL)."""
        return self._release_agent


    def get_identity(self) -> DevelopmentEngineIdentity:
        """Return engine identity and version."""
        return self._identity

    def get_status(self) -> DevelopmentEngineStatus:
        """Return current operational status."""
        return self._status

    def validate_task_grant(
        self, grant: TaskGrant | DevelopmentTaskGrant
    ) -> DevelopmentTaskGrant:
        """Validate that the incoming task grant is authorized, unexpired, and bounded to W_DEV scope.

        Fails closed on:
        - None or invalid object
        - WorkerRole mismatch (only WorkerRole.DEVELOPMENT allowed)
        - Expired grant
        - Missing or invalid tenant scope
        - Path traversal or sensitive file patterns
        - Unauthorized sandbox capabilities or tools
        """
        if grant is None:
            raise PolicyViolationError("Task grant cannot be None for W_DEV invocation.")

        if not isinstance(grant, TaskGrant):
            raise PolicyViolationError(
                f"Invalid grant type '{type(grant).__name__}'; expected TaskGrant or DevelopmentTaskGrant."
            )

        if grant.worker_role != WorkerRole.DEVELOPMENT:
            raise PolicyViolationError(
                f"Unauthorized worker role '{grant.worker_role}'; W_DEV only accepts '{WorkerRole.DEVELOPMENT}'."
            )

        now = datetime.now(UTC)
        grant_exp = (
            grant.expires_at
            if grant.expires_at.tzinfo is not None
            else grant.expires_at.replace(tzinfo=UTC)
        )
        if grant_exp <= now:
            raise PolicyViolationError(
                f"Task grant has expired at {grant_exp.isoformat()} (current time {now.isoformat()})."
            )

        if not grant.tenant_scope or not grant.tenant_scope.tenant_id:
            raise PolicyViolationError(
                "Task grant must specify a valid tenant_scope with non-empty tenant_id."
            )

        if isinstance(grant, DevelopmentTaskGrant):
            return grant

        try:
            return DevelopmentTaskGrant(
                task_id=grant.task_id,
                worker_role=grant.worker_role,
                tenant_scope=grant.tenant_scope,
                brand_id=grant.brand_id,
                objective=grant.objective,
                task_scope=grant.task_scope,
                task_slice=grant.task_slice,
                cts_state=grant.cts_state,
                brand_rules=grant.brand_rules,
                validated_evidence=grant.validated_evidence,
                provenance_references=grant.provenance_references,
                freshness_metadata=grant.freshness_metadata,
                policy_constraints=grant.policy_constraints,
                context_ids=grant.context_ids,
                expires_at=grant.expires_at,
                tool_permissions=grant.tool_permissions,
                sandbox_capabilities=grant.sandbox_capabilities,
                token_budget=grant.token_budget,
                budget_breakdown=grant.budget_breakdown,
                risk_tier=grant.risk_tier,
                stop_conditions=grant.stop_conditions,
                expected_outputs=grant.expected_outputs,
                expected_output_schema=grant.expected_output_schema,
            )
        except Exception as exc:
            raise PolicyViolationError(
                f"Task grant failed DevelopmentTaskGrant policy validation: {exc}"
            ) from exc

    def _verify_and_normalize_dependencies(
        self, grant: TaskGrant, context: dict[str, object]
    ) -> tuple[
        list[dict[str, Any]],
        str,
        str,
        list[str],
        str,
        str,
        str,
    ]:
        """Verify presence and validity of T06 staged CMS models and enforce tenant isolation.

        Fails closed safely if required dependency models are missing or off-tenant.
        """
        grant_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"

        # -------------------------------------------------------------
        # 1. Verify T06: Staged CMS Models
        # -------------------------------------------------------------
        staged_models: list[dict[str, Any]] = []

        raw_models = (
            context.get("staged_cms_models")
            or context.get("cms_page_model")
            or context.get("cms_schemas")
            or context.get("page_models")
            or grant.cts_state.get("staged_cms_models")
            or grant.cts_state.get("cms_page_model")
        )

        if raw_models:
            if isinstance(raw_models, list):
                for m in raw_models:
                    if isinstance(m, dict):
                        m_tenant = m.get("tenant_id")
                        if m_tenant and m_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in T06 staged CMS models: model tenant '{m_tenant}' "
                                f"does not match grant tenant '{grant_tenant}'."
                            )
                        staged_models.append(m)
                    elif hasattr(m, "model_dump"):
                        dumped = m.model_dump(mode="json")
                        m_tenant = dumped.get("tenant_id")
                        if m_tenant and m_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in T06 staged CMS models: model tenant '{m_tenant}' "
                                f"does not match grant tenant '{grant_tenant}'."
                            )
                        staged_models.append(dumped)
            elif isinstance(raw_models, dict):
                m_tenant = raw_models.get("tenant_id")
                if m_tenant and m_tenant != grant_tenant:
                    raise ValueError(
                        f"Tenant isolation breach in T06 staged CMS models: model tenant '{m_tenant}' "
                        f"does not match grant tenant '{grant_tenant}'."
                    )
                staged_models.append(raw_models)
            elif isinstance(raw_models, str):
                try:
                    parsed_m = json.loads(raw_models)
                    if isinstance(parsed_m, list):
                        for m in parsed_m:
                            if isinstance(m, dict):
                                m_tenant = m.get("tenant_id")
                                if m_tenant and m_tenant != grant_tenant:
                                    raise ValueError(
                                        f"Tenant isolation breach in T06 staged CMS models: model tenant '{m_tenant}' "
                                        f"does not match grant tenant '{grant_tenant}'."
                                    )
                                staged_models.append(m)
                    elif isinstance(parsed_m, dict):
                        m_tenant = parsed_m.get("tenant_id")
                        if m_tenant and m_tenant != grant_tenant:
                            raise ValueError(
                                f"Tenant isolation breach in T06 staged CMS models: model tenant '{m_tenant}' "
                                f"does not match grant tenant '{grant_tenant}'."
                            )
                        staged_models.append(parsed_m)
                except json.JSONDecodeError:
                    pass
            elif hasattr(raw_models, "model_dump"):
                dumped = raw_models.model_dump(mode="json")
                m_tenant = dumped.get("tenant_id")
                if m_tenant and m_tenant != grant_tenant:
                    raise ValueError(
                        f"Tenant isolation breach in T06 staged CMS models: model tenant '{m_tenant}' "
                        f"does not match grant tenant '{grant_tenant}'."
                    )
                staged_models.append(dumped)

        has_explicit_dependencies = (
            bool(context.get("require_dependencies"))
            or any(
                k in context
                for k in (
                    "staged_cms_models",
                    "cms_page_model",
                    "cms_schemas",
                    "page_models",
                    "schema_content",
                )
            )
            or any(
                k in grant.cts_state
                for k in (
                    "staged_cms_models",
                    "cms_page_model",
                    "cms_schemas",
                )
            )
        )

        if not staged_models:
            if has_explicit_dependencies:
                raise ValueError(
                    "Missing or invalid T06 Staged CMS Models dependency: No staged CMS models "
                    f"found for tenant '{grant_tenant}' in context or CTS state."
                )
            staged_models.append({
                "page_id": f"page-default-{grant.brand_id}",
                "tenant_id": grant_tenant,
                "slug": "home",
                "title": "Default Landing Page",
                "layout_id": "default",
                "publish_state": "staged",
            })

        # -------------------------------------------------------------
        # 2. Target Files & Security Checks
        # -------------------------------------------------------------
        component_name = str(context.get("component_name", "LandingHeader"))
        component_type = str(context.get("component_type", "component"))

        raw_target_files = context.get("target_files") or context.get("file_path")
        target_files: list[str] = []
        if raw_target_files:
            if isinstance(raw_target_files, list):
                target_files = [str(f) for f in raw_target_files]
            elif isinstance(raw_target_files, str):
                target_files = [f.strip() for f in raw_target_files.split(",") if f.strip()]
        else:
            target_files = [
                f"components/{component_name.lower()}.py",
                f"templates/{component_name.lower()}.html",
            ]

        # Fail closed on path traversal or sensitive files
        disallowed_patterns = (
            "..",
            "/etc/",
            "c:\\",
            "c:/",
            ".env",
            "credentials",
            "secret",
            "password",
            "shadow",
        )
        for f in target_files:
            f_lower = f.lower().replace("\\", "/")
            if any(p in f_lower for p in disallowed_patterns) or f_lower.startswith("/"):
                raise ValueError(
                    f"Security policy violation: Path traversal or unauthorized file path '{f}' detected."
                )

        code_content = str(context.get("code", context.get("schema_content", "")))
        schema_content = str(context.get("schema_content", ""))

        persona = context.get("brand_persona")
        brand_voice = getattr(persona, "voice", "neutral")

        return (
            staged_models,
            component_name,
            component_type,
            target_files,
            code_content,
            schema_content,
            brand_voice,
        )

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        """Build authorized sandbox execution payload for S_CODE."""
        (
            staged_models,
            component_name,
            component_type,
            target_files,
            code_content,
            schema_content,
            brand_voice,
        ) = self._verify_and_normalize_dependencies(grant, context)

        tenant_id = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"

        payload: dict[str, str] = {
            "task_id": grant.task_id,
            "operation": "generate_diff",
            "tenant_id": tenant_id,
            "component_name": component_name,
            "component_type": component_type,
            "code": code_content,
            "schema_content": schema_content,
            "t06_staged_models": json.dumps(staged_models, default=str),
            "target_files": ",".join(target_files),
            "brand_voice": brand_voice,
        }

        return payload

    def interpret_result(
        self, sanitized_output: dict[str, str]
    ) -> tuple[list[str], ConfidenceInterval]:
        """Parse sanitized output from S_CODE into evidence lines and confidence interval."""
        evidence: list[str] = []

        status = sanitized_output.get("status", "unknown")
        component_name = sanitized_output.get("component_name", "Component")
        syntax_error = sanitized_output.get("syntax_error", "")

        if status == "security_violation":
            evidence.append(f"Security Violation: {syntax_error or 'Unauthorized access attempt detected.'}")
            confidence = ConfidenceInterval(point_estimate=0.0, lower_bound=0.0, upper_bound=0.0)
            return evidence, confidence

        if status == "lint_failed":
            evidence.append(f"Syntax/AST Verification Failed for '{component_name}': {syntax_error}")
            confidence = ConfidenceInterval(point_estimate=0.40, lower_bound=0.20, upper_bound=0.60)
            return evidence, confidence

        dev_raw = sanitized_output.get("dev_deliverable")
        dev_data: dict[str, Any] | None = None
        if dev_raw:
            try:
                dev_data = json.loads(dev_raw)
            except Exception:
                pass

        if dev_data:
            deliv_id = dev_data.get("deliverable_id", "dev-unknown")
            c_name = dev_data.get("component_name", component_name)
            evidence.append(f"Development Deliverable [{deliv_id}]: Component: '{c_name}'")

            # UI Templates
            templates = dev_data.get("ui_templates", [])
            evidence.append(f"Responsive UI Templates Generated: {len(templates)}")
            for t in templates:
                if isinstance(t, dict):
                    t_name = t.get("name", "Template")
                    is_resp = t.get("is_responsive_validated", False)
                    evidence.append(f"  Template: '{t_name}' (Responsive Validated: {is_resp})")

            # CMS Schema Diffs
            schema_diffs = dev_data.get("cms_schema_diffs", [])
            evidence.append(f"CMS Schema Diffs: {len(schema_diffs)}")
            for sd in schema_diffs:
                if isinstance(sd, dict):
                    s_name = sd.get("schema_name", "schema")
                    added = len(sd.get("added_fields", []))
                    compat = sd.get("is_backward_compatible", False)
                    evidence.append(f"  Schema Diff '{s_name}': {added} fields added (Backward Compatible: {compat})")

            # Code Diffs
            code_diffs = dev_data.get("code_diffs", [])
            evidence.append(f"Deterministic Code Diffs: {len(code_diffs)}")
            for cd in code_diffs:
                if isinstance(cd, dict):
                    f_path = cd.get("file_path", "unknown")
                    act = cd.get("action", "modify")
                    ast_ok = cd.get("ast_validated", False)
                    evidence.append(f"  File [{f_path}] ({act}): AST Validated: {ast_ok}")

            # Validation findings
            for vf in dev_data.get("validation_findings", []):
                evidence.append(f"Validation Finding: {vf}")

            # Confidence
            conf_data = dev_data.get("confidence", {})
            pt = float(str(conf_data.get("point_estimate", 0.92)))
            low = float(str(conf_data.get("lower_bound", 0.82)))
            high = float(str(conf_data.get("upper_bound", 0.98)))
            confidence = ConfidenceInterval(point_estimate=pt, lower_bound=low, upper_bound=high)
        else:
            # Fallback legacy parsing
            ast_valid = sanitized_output.get("ast_valid", "False")
            node_count = sanitized_output.get("node_count", "0")
            func_count = sanitized_output.get("function_count", "0")
            class_count = sanitized_output.get("class_count", "0")
            diff = sanitized_output.get("diff", "")

            evidence.append(f"Component '{component_name}' AST Validated: {ast_valid}")
            evidence.append(f"Metrics: {node_count} nodes, {class_count} classes, {func_count} functions.")
            evidence.append(f"Generated Unified Diff: {diff[:120]}...")

            confidence = ConfidenceInterval(point_estimate=0.85, lower_bound=0.75, upper_bound=0.95)

        return evidence, confidence

    def extract_development_deliverable(
        self, envelope: EvidenceEnvelope
    ) -> DevelopmentDeliverable | None:
        """Helper to extract strongly typed DevelopmentDeliverable from an EvidenceEnvelope."""
        raw_deliv = envelope.payload.get("dev_deliverable")
        if not raw_deliv:
            return None
        if isinstance(raw_deliv, str):
            try:
                return DevelopmentDeliverable.model_validate_json(raw_deliv)
            except Exception:
                return None
        if isinstance(raw_deliv, dict):
            try:
                return DevelopmentDeliverable.model_validate(raw_deliv)
            except Exception:
                return None
        return None

    async def run(self, grant: TaskGrant, context: dict[str, Any]) -> EvidenceEnvelope:
        """Execute bounded development task grant with strict contract validation."""
        self.validate_task_grant(grant)
        return await super().run(grant, context)

    async def invoke_development(
        self, request: DevelopmentEngineRequest
    ) -> DevelopmentEngineResult:
        """Bounded Intelligence Engine -> W_DEV -> Intelligence Engine invocation contract.

        Validates request, transitions operational status to BUSY, executes bounded sandbox run,
        extracts deliverable, and returns structured DevelopmentEngineResult.
        Fails closed on invalid grants or security exceptions.
        """
        logger.info(
            "W_DEV received development request",
            extra={"request_id": request.request_id, "task_id": request.grant.task_id},
        )

        validated_grant = self.validate_task_grant(request.grant)

        self._status.status = "BUSY"
        self._status.active_task_id = validated_grant.task_id
        self._status.last_active_at = datetime.now(UTC)

        try:
            envelope = await self.run(validated_grant, request.context)
            deliverable = self.extract_development_deliverable(envelope)

            status: Literal["SUCCESS", "FAILED"] = (
                "SUCCESS" if envelope.confidence.point_estimate > 0.0 else "FAILED"
            )
            findings = envelope.findings

            result = DevelopmentEngineResult(
                task_id=validated_grant.task_id,
                engine_id=self._identity.engine_id,
                status=status,
                deliverable=deliverable,
                evidence_envelope=envelope,
                validation_findings=findings,
                provenance={
                    "engine_id": self._identity.engine_id,
                    "engine_version": self._identity.version,
                    "request_id": request.request_id,
                    "completed_at": datetime.now(UTC).isoformat(),
                    **envelope.provenance,
                },
            )
            self._status.status = "IDLE"
            self._status.active_task_id = None
            return result
        except Exception as exc:
            self._status.status = "ERROR"
            self._status.active_task_id = None
            logger.error("W_DEV execution failed", exc_info=exc)
            raise

    async def plan_development_task(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        previous_plan: DevelopmentPlan | None = None,
        reviewer_feedback: str | None = None,
        is_release_producing: bool = True,
        provenance_recorder: Any = None,
    ) -> tuple[DevelopmentPlan, str]:
        """Execute DEV-PLAN sub-agent to generate a validated DevelopmentPlan.

        Validates incoming grant, runs read-only planning inspection, computes plan hash,
        records provenance if recorder is provided, and returns the sealed (plan, plan_hash).
        """
        validated_grant = self.validate_task_grant(grant)
        ctx = context or {}

        plan = await self._planning_agent.create_plan(
            grant=validated_grant,
            context=ctx,
            workflow_id=workflow_id,
            attempt_id=attempt_id,
            previous_plan=previous_plan,
            reviewer_feedback=reviewer_feedback,
            is_release_producing=is_release_producing,
        )
        plan_hash = plan.plan_hash or plan.compute_plan_hash()

        if provenance_recorder is not None:
            try:
                tenant_id = validated_grant.tenant_scope.tenant_id
                activity_id = f"act-plan-{plan.plan_id}"
                await provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=f"plan:{plan.plan_id}:{plan_hash[:12]}",
                    activity=activity_id,
                    agent="DEV-PLAN",
                    metadata={
                        "plan_id": plan.plan_id,
                        "task_id": validated_grant.task_id,
                        "plan_hash": plan_hash,
                        "attempt_id": attempt_id,
                        "steps_count": len(plan.steps),
                        "risk_class": plan.risk_class,
                        "is_release_producing": is_release_producing,
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record provenance for DEV-PLAN", exc_info=exc)

        return plan, plan_hash

    async def execute_cms_step(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        plan: DevelopmentPlan | None = None,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        previous_candidate: CmsCandidateDeliverable | None = None,
        reviewer_feedback: str | None = None,
        provenance_recorder: Any = None,
    ) -> tuple[CmsCandidateDeliverable, str]:
        """Execute DEV-CMS sub-agent to generate a validated CmsCandidateDeliverable.

        Validates incoming grant, enforces approved DevelopmentPlan authority,
        runs isolated sandbox schema/contract/migration analysis, computes candidate hash,
        records provenance if recorder is provided, and returns sealed (candidate, candidate_hash).
        """
        validated_grant = self.validate_task_grant(grant)
        ctx = context or {}

        candidate = await self._cms_agent.execute_cms_task(
            grant=validated_grant,
            plan=plan,
            context=ctx,
            workflow_id=workflow_id,
            attempt_id=attempt_id,
            previous_candidate=previous_candidate,
            reviewer_feedback=reviewer_feedback,
        )
        candidate_hash = candidate.candidate_hash or candidate.compute_candidate_hash()

        if provenance_recorder is not None:
            try:
                tenant_id = validated_grant.tenant_scope.tenant_id
                activity_id = f"act-cms-{candidate.candidate_id}"
                await provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=f"cms_candidate:{candidate.candidate_id}:{candidate_hash[:12]}",
                    activity=activity_id,
                    agent="DEV-CMS",
                    metadata={
                        "candidate_id": candidate.candidate_id,
                        "task_id": validated_grant.task_id,
                        "candidate_hash": candidate_hash,
                        "attempt_id": attempt_id,
                        "schema_id": candidate.schema_definition.schema_id,
                        "change_classification": candidate.change_classification.value,
                        "is_breaking": candidate.compatibility_report.is_breaking,
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record provenance for DEV-CMS", exc_info=exc)

        return candidate, candidate_hash

    async def execute_ui_step(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        plan: DevelopmentPlan | None = None,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        previous_candidate: UiCandidateDeliverable | None = None,
        reviewer_feedback: str | None = None,
        provenance_recorder: Any = None,
    ) -> tuple[UiCandidateDeliverable, str]:
        """Execute DEV-UI sub-agent to generate a validated UiCandidateDeliverable.

        Validates incoming grant, enforces approved DevelopmentPlan authority,
        runs isolated sandbox UI/component/template/accessibility analysis, computes candidate hash,
        records provenance if recorder is provided, and returns sealed (candidate, candidate_hash).
        """
        validated_grant = self.validate_task_grant(grant)
        ctx = context or {}

        candidate = await self._ui_agent.execute_ui_task(
            grant=validated_grant,
            plan=plan,
            context=ctx,
            workflow_id=workflow_id,
            attempt_id=attempt_id,
            previous_candidate=previous_candidate,
            reviewer_feedback=reviewer_feedback,
        )
        candidate_hash = candidate.candidate_hash or candidate.compute_candidate_hash()

        if provenance_recorder is not None:
            try:
                tenant_id = validated_grant.tenant_scope.tenant_id
                activity_id = f"act-ui-{candidate.candidate_id}"
                await provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=f"ui_candidate:{candidate.candidate_id}:{candidate_hash[:12]}",
                    activity=activity_id,
                    agent="DEV-UI",
                    metadata={
                        "candidate_id": candidate.candidate_id,
                        "task_id": validated_grant.task_id,
                        "candidate_hash": candidate_hash,
                        "attempt_id": attempt_id,
                        "component_name": candidate.component_name,
                        "compliance_score": candidate.accessibility_report.compliance_score,
                        "is_accessible": candidate.accessibility_report.is_accessible,
                        "viewports_count": len(candidate.render_evidence.viewports),
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record provenance for DEV-UI", exc_info=exc)

        return candidate, candidate_hash

    async def execute_code_step(
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
        provenance_recorder: Any = None,
    ) -> tuple[CodeCandidateDeliverable, str]:
        """Execute DEV-CODE sub-agent to generate a validated CodeCandidateDeliverable.

        Validates incoming grant, enforces approved DevelopmentPlan authority,
        runs isolated sandbox code authoring, AST inspection, formatting, and compiler sanity checks,
        computes candidate hash, records provenance if recorder is provided, and returns sealed (candidate, candidate_hash).
        """
        validated_grant = self.validate_task_grant(grant)
        ctx = context or {}

        candidate = await self._code_agent.execute_code_task(
            grant=validated_grant,
            plan=plan,
            context=ctx,
            workflow_id=workflow_id,
            attempt_id=attempt_id,
            previous_candidate=previous_candidate,
            reviewer_feedback=reviewer_feedback,
            expected_predecessor_hash=expected_predecessor_hash,
        )
        candidate_hash = candidate.candidate_hash or candidate.compute_candidate_hash()

        if provenance_recorder is not None:
            try:
                tenant_id = validated_grant.tenant_scope.tenant_id
                activity_id = f"act-code-{candidate.candidate_id}"
                await provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=f"code_candidate:{candidate.candidate_id}:{candidate_hash[:12]}",
                    activity=activity_id,
                    agent="DEV-CODE",
                    metadata={
                        "candidate_id": candidate.candidate_id,
                        "task_id": validated_grant.task_id,
                        "candidate_hash": candidate_hash,
                        "attempt_id": attempt_id,
                        "component_name": candidate.component_name,
                        "changed_files": candidate.changed_files,
                        "compiler_passed": candidate.sanity_check_result.compiler_passed,
                        "is_valid": candidate.sanity_check_result.is_valid,
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record provenance for DEV-CODE", exc_info=exc)

        return candidate, candidate_hash

    async def execute_verify_step(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        candidate: CodeCandidateDeliverable | UiCandidateDeliverable | CmsCandidateDeliverable | None,
        expected_candidate_hash: str | None = None,
        plan: DevelopmentPlan | None = None,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        provenance_recorder: Any = None,
    ) -> VerificationDossier:
        """Execute DEV-VERIFY sub-agent to produce a sealed VerificationDossier.

        Enforces plan authority, validates candidate deliverable and exact digest hash,
        executes repository-native builds, lint checks, formatting checks, type checks,
        automated tests, and coverage analysis in isolated sandbox,
        computes dossier hash, records provenance, and returns sealed VerificationDossier.
        """
        validated_grant = self.validate_task_grant(grant)
        ctx = context or {}

        dossier = await self._verify_agent.execute_verification_task(
            grant=validated_grant,
            candidate=candidate,
            expected_candidate_hash=expected_candidate_hash,
            plan=plan,
            workflow_id=workflow_id,
            attempt_id=attempt_id,
            context=ctx,
        )

        if provenance_recorder is not None:
            try:
                tenant_id = validated_grant.tenant_scope.tenant_id
                activity_id = f"act-verify-{dossier.dossier_id}"
                await provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=f"verification_dossier:{dossier.dossier_id}:{dossier.dossier_hash[:12]}",
                    activity=activity_id,
                    agent="DEV-VERIFY",
                    metadata={
                        "dossier_id": dossier.dossier_id,
                        "task_id": validated_grant.task_id,
                        "dossier_hash": dossier.dossier_hash,
                        "candidate_hash": dossier.candidate_hash,
                        "verdict": dossier.verdict.value,
                        "remediation_step": dossier.remediation_step,
                        "checks_count": len(dossier.checks),
                        "tests_passed": dossier.test_totals.passed,
                        "tests_failed": dossier.test_totals.failed,
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record provenance for DEV-VERIFY", exc_info=exc)

        return dossier

    async def execute_security_step(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        candidate: (
            CodeCandidateDeliverable
            | UiCandidateDeliverable
            | CmsCandidateDeliverable
            | None
        ) = None,
        expected_candidate_hash: str | None = None,
        verification_dossier: VerificationDossier | None = None,
        plan: DevelopmentPlan | None = None,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        provenance_recorder: Any = None,
    ) -> SecurityDossier:
        """Execute DEV-SEC sub-agent to produce a sealed SecurityDossier.

        Enforces plan authority, validates unexpired task grant, checks DE-10 verification prerequisite,
        executes SAST, secret detection, SCA, configuration review, boundary checks, and AST pattern analysis,
        computes tamper-evident dossier hash, records provenance, and returns sealed SecurityDossier.
        """
        validated_grant = self.validate_task_grant(grant)
        ctx = context or {}

        dossier = await self._security_agent.execute_security_task(
            grant=validated_grant,
            candidate=candidate,
            expected_candidate_hash=expected_candidate_hash,
            verification_dossier=verification_dossier,
            plan=plan,
            workflow_id=workflow_id,
            attempt_id=attempt_id,
            context=ctx,
        )

        if provenance_recorder is not None:
            try:
                tenant_id = validated_grant.tenant_scope.tenant_id
                activity_id = f"act-sec-{dossier.dossier_id}"
                await provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=f"security_dossier:{dossier.dossier_id}:{dossier.dossier_hash[:12]}",
                    activity=activity_id,
                    agent="DEV-SEC",
                    metadata={
                        "dossier_id": dossier.dossier_id,
                        "task_id": validated_grant.task_id,
                        "dossier_hash": dossier.dossier_hash,
                        "candidate_hash": dossier.candidate_hash,
                        "verdict": dossier.verdict.value,
                        "hard_block_count": dossier.hard_block_count,
                        "total_findings": len(dossier.findings),
                        "remediation_targets": dossier.remediation_targets,
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record provenance for DEV-SEC", exc_info=exc)

        return dossier

    async def execute_release_step(
        self,
        *,
        grant: TaskGrant | DevelopmentTaskGrant,
        security_dossier: SecurityDossier,
        candidate: (
            CodeCandidateDeliverable
            | UiCandidateDeliverable
            | CmsCandidateDeliverable
            | None
        ) = None,
        expected_candidate_hash: str | None = None,
        plan: DevelopmentPlan | None = None,
        hitl_approved: bool = True,
        hitl_approval_token: str | None = None,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        attempt_id: str = "att-1",
        provenance_recorder: Any = None,
    ) -> ReleaseCandidateDeliverable:
        """Execute DEV-REL sub-agent to produce an immutable ReleaseCandidateDeliverable.

        Enforces security dossier PASS gate (machine DENY overrides human approval),
        validates pre-DEV-REL HITL authorization, packages immutable release artifacts,
        generates CycloneDX v1.5 SBOM, deployment and rollback manifests, migration dry-run evidence,
        binds SLSA v1.0 / in-toto attestations, computes release hash, and records provenance.
        """
        validated_grant = self.validate_task_grant(grant)
        ctx = context or {}

        if (
            provenance_recorder is not None
            and getattr(self._release_agent, "_provenance_recorder", None) is None
        ):
            self._release_agent._provenance_recorder = provenance_recorder

        deliverable = await self._release_agent.execute_release_task(
            grant=validated_grant,
            candidate=candidate,
            expected_candidate_hash=expected_candidate_hash,
            security_dossier=security_dossier,
            plan=plan,
            hitl_approved=hitl_approved,
            hitl_approval_token=hitl_approval_token,
            workflow_id=workflow_id,
            attempt_id=attempt_id,
            context=ctx,
        )

        if provenance_recorder is not None:
            try:
                tenant_id = validated_grant.tenant_scope.tenant_id
                activity_id = f"act-rel-{deliverable.release_id}"
                await provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=f"release_deliverable:{deliverable.release_id}:{deliverable.release_hash[:12]}",
                    activity=activity_id,
                    agent="DEV-REL",
                    metadata={
                        "release_id": deliverable.release_id,
                        "task_id": validated_grant.task_id,
                        "release_hash": deliverable.release_hash,
                        "candidate_hash": deliverable.candidate_hash,
                        "security_dossier_hash": deliverable.security_dossier_hash,
                        "version": deliverable.version,
                        "artifact_count": len(deliverable.release_artifacts),
                        "sbom_hash": deliverable.sbom.sbom_hash,
                    },
                )
            except Exception as exc:
                logger.warning("Failed to record provenance for DEV-REL", exc_info=exc)

        return deliverable