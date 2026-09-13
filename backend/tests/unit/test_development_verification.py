"""Unit tests for T21: UI Templates, CMS Schemas & Code Diff Engineering (W_DEV + S_CODE)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agents.development import DevelopmentAgent
from app.core.exceptions import SandboxInvocationError
from app.integrations.sandbox.capabilities import validate_capability_access
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.micro_tools import execute_s_code
from app.schemas.agent_contracts import (
    CmsSchemaDiff,
    CodeDiffEntry,
    DevelopmentDeliverable,
    TaskGrant,
    UITemplateDefinition,
)
from app.schemas.cms import CmsPageModel, CmsPublishState
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from tests.conftest import FakeSandboxClient


def test_s_code_with_valid_ui_template_and_staged_models() -> None:
    """S_CODE generates responsive UI templates, CMS schema diffs, and unified code diffs."""
    payload = {
        "task_id": "task-dev-001",
        "tenant_id": "tenant_acme",
        "component_name": "ProductHeroBanner",
        "component_type": "component",
        "t06_staged_models": json.dumps([
            {
                "page_id": "page-product-01",
                "tenant_id": "tenant_acme",
                "slug": "product-landing",
                "title": "Product Showcase",
                "layout_id": "default",
                "publish_state": "staged",
            }
        ]),
        "target_files": "components/product_hero_banner.py,templates/product_hero_banner.html",
    }

    result = execute_s_code(payload)

    assert result["status"] == "success"
    assert result["task_id"] == "task-dev-001"
    assert result["ast_valid"] == "True"
    assert int(result["function_count"]) >= 1
    assert int(result["class_count"]) >= 1
    assert "+++ b/components/product_hero_banner.py" in result["diff"]

    # Verify DevelopmentDeliverable JSON
    deliverable = DevelopmentDeliverable.model_validate_json(result["dev_deliverable"])
    assert deliverable.deliverable_id == "dev-task-dev-001"
    assert deliverable.tenant_id == "tenant_acme"
    assert deliverable.component_name == "ProductHeroBanner"
    assert deliverable.security_checks_passed is True

    # Verify UI template & responsive breakpoints
    assert len(deliverable.ui_templates) == 1
    template = deliverable.ui_templates[0]
    assert template.name == "ProductHeroBanner Responsive Template"
    assert template.is_responsive_validated is True
    assert len(template.responsive_breakpoints) == 3
    bp_names = [bp.breakpoint for bp in template.responsive_breakpoints]
    assert "mobile" in bp_names
    assert "tablet" in bp_names
    assert "desktop" in bp_names

    # Verify CMS schema diff
    assert len(deliverable.cms_schema_diffs) == 1
    schema_diff = deliverable.cms_schema_diffs[0]
    assert schema_diff.is_backward_compatible is True
    assert len(schema_diff.added_fields) >= 3

    # Verify code diff
    assert len(deliverable.code_diffs) == 1
    assert deliverable.code_diffs[0].ast_validated is True


def test_s_code_ast_syntax_error() -> None:
    """S_CODE catches Python syntax errors, fails lint safely, and notes syntax error in output."""
    payload = {
        "task_id": "task-dev-syntax-err",
        "code": "class BrokenClass\n    def invalid(self):\n        pass",
        "component_name": "BrokenClass",
    }

    result = execute_s_code(payload)

    assert result["status"] == "lint_failed"
    assert result["ast_valid"] == "False"
    assert "SyntaxError" in result["syntax_error"]


def test_s_code_security_path_traversal_rejection() -> None:
    """S_CODE rejects path traversal attempts in target files (fail closed)."""
    payload = {
        "task_id": "task-dev-traversal",
        "target_files": "../../etc/shadow,components/safe.py",
    }

    result = execute_s_code(payload)

    assert result["status"] == "security_violation"
    assert result["security_checks_passed"] == "False"
    assert "Security violation" in result["syntax_error"]
    assert result["diff"] == ""


def test_s_code_security_unauthorized_sensitive_file() -> None:
    """S_CODE rejects sensitive configuration or credential targets."""
    payload = {
        "task_id": "task-dev-secret",
        "target_files": ".env,credentials.json",
    }

    result = execute_s_code(payload)

    assert result["status"] == "security_violation"
    assert result["security_checks_passed"] == "False"


def test_s_code_security_dangerous_system_call_rejection() -> None:
    """S_CODE rejects malicious system/subprocess code patterns."""
    payload = {
        "task_id": "task-dev-dangerous",
        "code": "import os\nos.system('rm -rf /')\n",
    }

    result = execute_s_code(payload)

    assert result["status"] == "security_violation"
    assert result["security_checks_passed"] == "False"
    assert "Disallowed system execution" in result["syntax_error"]


@pytest.mark.asyncio
async def test_w_dev_generates_valid_evidence_envelope_and_deliverable() -> None:
    """DevelopmentAgent processes T06 staged models and produces valid EvidenceEnvelope and DevelopmentDeliverable."""
    agent = DevelopmentAgent(SandboxClient())

    grant = TaskGrant(
        task_id="task-dev-e2e-01",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant_delta", brand_ids=["brand_delta"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    page_model = CmsPageModel(
        page_id="page-landing-1",
        tenant_id="tenant_delta",
        slug="new-features",
        title="Features Overview",
        publish_state=CmsPublishState.STAGED,
    )

    context: dict[str, object] = {
        "component_name": "FeatureGrid",
        "component_type": "component",
        "staged_cms_models": [page_model],
        "target_files": ["components/feature_grid.py", "templates/feature_grid.html"],
    }

    envelope = await agent.run(grant, context)

    assert envelope.task_id == "task-dev-e2e-01"
    assert envelope.worker_role == WorkerRole.DEVELOPMENT
    assert envelope.confidence.point_estimate >= 0.8
    assert "diff:task-dev-e2e-01" in envelope.generated_artifacts
    assert "dev:task-dev-e2e-01" in envelope.generated_artifacts
    assert envelope.provenance["capability"] == "S_CODE"
    assert len(envelope.findings) >= 3

    # Extract strongly typed DevelopmentDeliverable
    deliverable = agent.extract_development_deliverable(envelope)
    assert deliverable is not None
    assert deliverable.deliverable_id == "dev-task-dev-e2e-01"
    assert deliverable.tenant_id == "tenant_delta"
    assert deliverable.component_name == "FeatureGrid"
    assert len(deliverable.ui_templates) >= 1
    assert len(deliverable.code_diffs) >= 1
    assert deliverable.code_diffs[0].ast_validated is True


@pytest.mark.asyncio
async def test_w_dev_missing_t06_staged_cms_models_fails_closed() -> None:
    """DevelopmentAgent fails closed when required T06 staged CMS model dependency is missing."""
    agent = DevelopmentAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-dev-missing-t06",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant_1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "require_dependencies": True,
        "component_name": "HeroSection",
        # Missing staged_cms_models!
    }

    with pytest.raises(ValueError, match="Missing or invalid T06 Staged CMS Models dependency"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_w_dev_cross_tenant_cms_model_breach_fails_closed() -> None:
    """DevelopmentAgent rejects staged CMS models belonging to another tenant."""
    agent = DevelopmentAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-dev-cross-tenant",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant_secure"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "component_name": "NavMenu",
        "staged_cms_models": [
            {"page_id": "p1", "tenant_id": "tenant_attacker", "title": "Injected Page"}
        ],
    }

    with pytest.raises(ValueError, match="Tenant isolation breach in T06 staged CMS models"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_w_dev_path_traversal_fails_closed() -> None:
    """DevelopmentAgent rejects file paths attempting path traversal."""
    agent = DevelopmentAgent(SandboxClient())
    grant = TaskGrant(
        task_id="task-dev-traversal-block",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant_1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "component_name": "ExploitComponent",
        "target_files": ["../../etc/passwd"],
    }

    with pytest.raises(ValueError, match="Security policy violation: Path traversal"):
        await agent.run(grant, context)


def test_unauthorized_capability_access_rejection() -> None:
    """Requesting CODE capability with unauthorized worker role fails closed."""
    with pytest.raises(SandboxInvocationError, match="Capability access denied"):
        validate_capability_access(
            capability=SandboxCapability.CODE,
            worker_role=WorkerRole.STRATEGY,
            operation="generate_diff",
        )


@pytest.mark.asyncio
async def test_sandbox_failure_returns_risk_envelope() -> None:
    """When sandbox execution fails, DevelopmentAgent returns risk envelope with 0.0 confidence."""
    failing_client = FakeSandboxClient(should_fail=True)
    agent = DevelopmentAgent(failing_client)

    grant = TaskGrant(
        task_id="task-fail-exec-dev",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="t1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "component_name": "TestComponent",
    }

    envelope = await agent.run(grant, context)

    assert envelope.confidence.point_estimate == 0.0
    assert len(envelope.unresolved_risks_or_assumptions) >= 1
    assert "simulated sandbox failure" in envelope.unresolved_risks_or_assumptions[0]


def test_model_a_no_direct_rag_cms_or_database_imports() -> None:
    """Model-A architectural invariant: W_DEV must not import RAG, persistence, CMS client, or DB."""
    import inspect
    import app.agents.development as dev_module

    source = inspect.getsource(dev_module)

    assert "app.services.rag" not in source
    assert "app.persistence" not in source
    assert "app.integrations.cms.client" not in source
    assert "app.orchestration.rag_query_dispatch" not in source
    assert "sqlalchemy" not in source
    assert "httpx" not in source
