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
from app.agents.development_engine.subagents.planning import DevelopmentPlanningAgent
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

    def __init__(
        self,
        sandbox_client: SandboxClient,
        llm_client: Any = None,
    ) -> None:
        super().__init__(sandbox_client, llm_client=llm_client)
        self._identity = DevelopmentEngineIdentity()
        self._status = DevelopmentEngineStatus()
        self._planning_agent = DevelopmentPlanningAgent(sandbox_client, llm_client=llm_client)

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