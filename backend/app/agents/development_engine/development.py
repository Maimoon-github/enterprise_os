"""W_DEV: CMS schemas, UI layouts, code diffs, and web-development engineering."""

from __future__ import annotations

import json
from typing import Any

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import (
    ConfidenceInterval,
    DevelopmentDeliverable,
    EvidenceEnvelope,
    TaskGrant,
)
from app.schemas.sandbox import SandboxCapability


class DevelopmentAgent(BoundedWorkerAgent):
    """W_DEV Development Engine.

    Consumes staged CMS models (T06) and bounded task grants (T15) to produce
    responsive UI templates, CMS schema/model changes, component definitions, and
    deterministic unified code diffs using sandboxed S_CODE.

    Enforces path traversal protection, syntax/AST validation, responsive constraint
    checks, and tenant isolation under Model-A (no direct persistence or RAG).
    """

    capability = SandboxCapability.CODE

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