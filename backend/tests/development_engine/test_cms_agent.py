"""Focused unit and integration tests for Task DE-07: DEV-CMS.

Validates:
1. DEV-CMS enforces approved plan authority (fails closed if DEV-CMS was skipped).
2. Additive schema change generation, diff classification, and 1-step migration.
3. Breaking schema change detection and 4-phase expand-contract migration generation.
4. Migration simulation and reversibility (forward and rollback verification).
5. JSON Schema Draft 2020-12 compliance and TypeScript contract generation.
6. Fail-closed validation for invalid schemas and tenant isolation breaches.
7. LLM reasoning engine integration and deterministic fallback.
8. Rejection and revision continuity (att-1 -> att-2) preserving att-1 immutability.
9. Deterministic candidate hash sealing and canonical byte representation.
10. Integration with DevelopmentAgent.execute_cms_step and ProvenanceRecorder.
11. Direct sandbox micro_tools execution for all CMS operations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import Any
import pytest

from app.agents.development_engine.development import DevelopmentAgent
from app.agents.development_engine.subagents.cms_contract import CmsContractAgent
from app.core.exceptions import PolicyViolationError
from app.integrations.sandbox.micro_tools import execute_s_code
from app.schemas.agent_contracts import TaskGrant
from app.schemas.cms import (
    CmsCandidateDeliverable,
    CmsChangeClassification,
    CmsContentModelSchema,
    CmsFieldDefinition,
    CmsFieldType,
    CmsMigrationPhase,
    CmsMigrationPlan,
    CmsMigrationStep,
)
from app.schemas.development import (
    DevelopmentPlan,
    DevelopmentPlanStep,
    DevelopmentTaskGrant,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from app.services.provenance import ProvenanceRecorder
from tests.conftest import FakeProvenanceRepository, FakeSandboxClient


class FakeLlmClient:
    """Mock LLM client returning realistic JSON reasoning responses."""

    def __init__(self, response_dict: dict[str, Any] | None = None) -> None:
        self.call_count = 0
        self.last_prompt = ""
        self.response_dict = response_dict or {
            "rationale": "Add author_bio to BlogPost for enhanced author profiles.",
            "breaking_analysis": "Additive change: new optional field introduces no backward incompatibility.",
            "migration_strategy": "Direct additive schema migration without downtime.",
            "constraints_considered": ["field naming convention", "Draft 2020-12 validation"],
            "feedback_adjustments": [],
        }

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        return json.dumps(self.response_dict)


@pytest.fixture
def fake_sandbox() -> FakeSandboxClient:
    return FakeSandboxClient()


@pytest.fixture
def cms_agent(fake_sandbox: FakeSandboxClient) -> CmsContractAgent:
    return CmsContractAgent(fake_sandbox)


@pytest.fixture
def dev_agent(fake_sandbox: FakeSandboxClient) -> DevelopmentAgent:
    return DevelopmentAgent(fake_sandbox)


@pytest.fixture
def valid_grant() -> DevelopmentTaskGrant:
    return DevelopmentTaskGrant(
        task_id="task-cms-001",
        worker_role=WorkerRole.DEVELOPMENT,
        tenant_scope=TenantScope(tenant_id="tenant-acme"),
        brand_id="brand-core",
        objective="Update blog post CMS schema to support featured images and author bio",
        component_name="BlogPostModel",
        target_files=["schemas/blog_post.json"],
        token_budget=8000,
        expires_at=datetime.now(UTC) + timedelta(minutes=45),
        sandbox_capabilities=[SandboxCapability.CODE.value],
    )


@pytest.fixture
def base_schema() -> CmsContentModelSchema:
    return CmsContentModelSchema(
        schema_id="blog_post",
        name="BlogPost",
        description="Standard article and blog post model",
        version="1.0.0",
        tenant_id="tenant-acme",
        fields=[
            CmsFieldDefinition(
                name="title",
                field_type=CmsFieldType.STRING,
                label="Article Title",
                required=True,
                max_length=200,
            ),
            CmsFieldDefinition(
                name="content",
                field_type=CmsFieldType.RICHTEXT,
                label="Article Body",
                required=True,
            ),
            CmsFieldDefinition(
                name="published_at",
                field_type=CmsFieldType.DATETIME,
                label="Publication Timestamp",
                required=False,
            ),
        ],
    )


# ===========================================================================
# 1. Additive Schema Change & 1-Step Migration Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_additive_schema_change_execution(
    cms_agent: CmsContractAgent,
    valid_grant: DevelopmentTaskGrant,
    base_schema: CmsContentModelSchema,
) -> None:
    """DEV-CMS creates additive change with direct migration, Draft 2020-12 schema, and TS contracts."""
    # New target schema adds an optional 'author_bio' field
    target_schema = base_schema.model_copy(deep=True)
    target_schema.version = "1.1.0"
    target_schema.fields.append(
        CmsFieldDefinition(
            name="author_bio",
            field_type=CmsFieldType.STRING,
            label="Author Biography",
            required=False,
            max_length=500,
        )
    )

    context = {
        "current_schema": base_schema.model_dump(mode="json"),
        "target_schema": target_schema.model_dump(mode="json"),
    }

    candidate = await cms_agent.execute_cms_task(
        grant=valid_grant,
        context=context,
    )

    assert isinstance(candidate, CmsCandidateDeliverable)
    assert candidate.task_id == valid_grant.task_id
    assert candidate.change_classification == CmsChangeClassification.ADDITIVE
    assert not candidate.compatibility_report.is_breaking

    # Diffs check
    diff = candidate.detailed_diff
    assert len(diff.added_fields) == 1
    assert diff.added_fields[0].name == "author_bio"
    assert len(diff.removed_fields) == 0
    assert len(diff.modified_fields) == 0

    # Migration plan check: direct apply (1 step)
    migration = candidate.migration_plan
    assert isinstance(migration, CmsMigrationPlan)
    assert migration.is_expand_contract is False
    assert len(migration.steps) == 1
    step = migration.steps[0]
    assert step.phase == CmsMigrationPhase.DIRECT_APPLY
    assert "ADD COLUMN author_bio" in step.up_script
    assert "DROP COLUMN author_bio" in step.down_script

    # Contract checks
    assert candidate.json_schema_draft_2020_12.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert "author_bio" in candidate.json_schema_draft_2020_12["properties"]
    assert "export interface BlogPost" in candidate.typescript_interfaces
    assert "author_bio?:" in candidate.typescript_interfaces

    # Simulation check
    assert candidate.validation_evidence.migration_simulated is True
    assert candidate.validation_evidence.rollback_simulated is True
    assert candidate.candidate_hash is not None


# ===========================================================================
# 2. Breaking Schema Change & 4-Phase Expand-Contract Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_breaking_schema_change_expand_contract(
    cms_agent: CmsContractAgent,
    valid_grant: DevelopmentTaskGrant,
    base_schema: CmsContentModelSchema,
) -> None:
    """DEV-CMS detects breaking field drop and incompatible type changes, creating 4-phase expand-contract."""
    # Target schema drops 'content' and changes 'title' to integer (incompatible)
    target_schema = CmsContentModelSchema(
        schema_id="blog_post",
        name="BlogPost",
        description="Modified blog post",
        version="2.0.0",
        tenant_id="tenant-acme",
        fields=[
            CmsFieldDefinition(
                name="title",
                field_type=CmsFieldType.INTEGER,
                label="Article ID",
                required=True,
            ),
            CmsFieldDefinition(
                name="summary",
                field_type=CmsFieldType.STRING,
                label="Summary",
                required=True,
            ),
        ],
    )

    context = {
        "current_schema": base_schema.model_dump(mode="json"),
        "target_schema": target_schema.model_dump(mode="json"),
    }

    candidate = await cms_agent.execute_cms_task(
        grant=valid_grant,
        context=context,
    )

    assert candidate.change_classification == CmsChangeClassification.BREAKING
    assert candidate.compatibility_report.is_breaking is True
    assert len(candidate.compatibility_report.dropped_fields) >= 1

    # Migration plan check: 4 phases
    migration = candidate.migration_plan
    assert isinstance(migration, CmsMigrationPlan)
    assert migration.is_expand_contract is True
    assert len(migration.steps) == 4
    phases = [s.phase for s in migration.steps]
    assert phases == [
        CmsMigrationPhase.EXPAND,
        CmsMigrationPhase.MIGRATE_BACKFILL,
        CmsMigrationPhase.VALIDATE,
        CmsMigrationPhase.CONTRACT,
    ]

    # Every step must have both up_script and down_script
    for step in migration.steps:
        assert step.up_script is not None and len(step.up_script) > 0
        assert step.down_script is not None and len(step.down_script) > 0

    # Simulation must succeed
    assert candidate.validation_evidence.migration_simulated is True
    assert candidate.validation_evidence.rollback_simulated is True


# ===========================================================================
# 3. Plan Authority Enforcement Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_plan_authority_enforced_fails_if_skipped(
    cms_agent: CmsContractAgent,
    valid_grant: DevelopmentTaskGrant,
    base_schema: CmsContentModelSchema,
) -> None:
    """Fails closed if the approved DevelopmentPlan specifies DEV-CMS as SKIPPED_NOT_APPLICABLE."""
    skipped_plan = DevelopmentPlan(
        plan_id="plan-skip-cms",
        task_id=valid_grant.task_id,
        workflow_id="wf-test-01",
        objective="Update CMS schema",
        steps=[
            DevelopmentPlanStep(
                step_id="step-cms",
                subagent_id="DEV-CMS",
                status="SKIPPED_NOT_APPLICABLE",
                skip_reason="Task is pure frontend UI template adjustment without CMS schema mutations.",
            ),
            DevelopmentPlanStep(
                step_id="step-ui",
                subagent_id="DEV-UI",
                status="REQUIRED",
                description="Build navbar template",
            ),
        ],
    )

    context = {"current_schema": base_schema.model_dump(mode="json")}

    with pytest.raises(PolicyViolationError) as exc_info:
        await cms_agent.execute_cms_task(
            grant=valid_grant,
            plan=skipped_plan,
            context=context,
        )
    assert "SKIPPED_NOT_APPLICABLE" in str(exc_info.value)


@pytest.mark.asyncio
async def test_plan_authority_passes_when_required(
    cms_agent: CmsContractAgent,
    valid_grant: DevelopmentTaskGrant,
    base_schema: CmsContentModelSchema,
) -> None:
    """Succeeds when approved DevelopmentPlan specifies DEV-CMS as REQUIRED."""
    required_plan = DevelopmentPlan(
        plan_id="plan-req-cms",
        task_id=valid_grant.task_id,
        workflow_id="wf-test-01",
        objective="Update CMS schema",
        steps=[
            DevelopmentPlanStep(
                step_id="step-cms",
                subagent_id="DEV-CMS",
                status="REQUIRED",
                description="Update blog post schema",
            ),
        ],
    )

    context = {"current_schema": base_schema.model_dump(mode="json")}

    candidate = await cms_agent.execute_cms_task(
        grant=valid_grant,
        plan=required_plan,
        context=context,
    )
    assert candidate.candidate_id is not None
    assert candidate.schema_definition.schema_id == "blog_post"


# ===========================================================================
# 4. Fail-Closed Validation & Tenant Isolation Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_tenant_isolation_breach_rejected(
    cms_agent: CmsContractAgent,
    valid_grant: DevelopmentTaskGrant,
    base_schema: CmsContentModelSchema,
) -> None:
    """Fails closed when target schema tenant does not match grant tenant."""
    alien_schema = base_schema.model_copy(deep=True)
    alien_schema.tenant_id = "tenant-evil-corp"

    context = {
        "current_schema": base_schema.model_dump(mode="json"),
        "target_schema": alien_schema.model_dump(mode="json"),
    }

    with pytest.raises(PolicyViolationError) as exc_info:
        await cms_agent.execute_cms_task(
            grant=valid_grant,
            context=context,
        )
    assert "Tenant isolation violation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_invalid_schema_definition_fails_closed(
    cms_agent: CmsContractAgent,
    valid_grant: DevelopmentTaskGrant,
) -> None:
    """Fails closed when target schema is missing required fields or invalid."""
    invalid_schema = {
        "schema_id": "",  # Empty schema ID
        "name": "InvalidSchema",
        "fields": [],
    }

    context = {"target_schema": invalid_schema}

    with pytest.raises((PolicyViolationError, ValueError)):
        await cms_agent.execute_cms_task(
            grant=valid_grant,
            context=context,
        )


# ===========================================================================
# 5. LLM Reasoning & Fallback Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_llm_reasoning_integration(
    fake_sandbox: FakeSandboxClient,
    valid_grant: DevelopmentTaskGrant,
    base_schema: CmsContentModelSchema,
) -> None:
    """DEV-CMS incorporates LLM reasoning for schema planning and analysis."""
    fake_llm = FakeLlmClient({
        "rationale": "LLM: Adding author_bio to enable rich author display in UI.",
        "breaking_analysis": "LLM: Fully compatible additive modification.",
        "migration_strategy": "LLM: Direct schema alter table execution.",
        "constraints_considered": ["field length max 500"],
        "feedback_adjustments": [],
    })

    agent = CmsContractAgent(fake_sandbox, llm_client=fake_llm)

    target_schema = base_schema.model_copy(deep=True)
    target_schema.fields.append(
        CmsFieldDefinition(
            name="author_bio",
            field_type=CmsFieldType.STRING,
            label="Bio",
            required=False,
        )
    )

    context = {
        "current_schema": base_schema.model_dump(mode="json"),
        "target_schema": target_schema.model_dump(mode="json"),
    }

    candidate = await agent.execute_cms_task(grant=valid_grant, context=context)

    assert fake_llm.call_count == 1
    assert "LLM: Adding author_bio" in candidate.provenance.get("llm_reasoning", {}).get("rationale", "")
    assert candidate.candidate_hash is not None


@pytest.mark.asyncio
async def test_deterministic_fallback_without_llm(
    fake_sandbox: FakeSandboxClient,
    valid_grant: DevelopmentTaskGrant,
    base_schema: CmsContentModelSchema,
) -> None:
    """DEV-CMS falls back deterministically when no LLM client is configured."""
    agent = CmsContractAgent(fake_sandbox, llm_client=None)

    context = {"current_schema": base_schema.model_dump(mode="json")}

    candidate = await agent.execute_cms_task(grant=valid_grant, context=context)
    assert candidate is not None
    assert candidate.provenance.get("llm_reasoning", {}).get("rationale") is not None


# ===========================================================================
# 6. HITL Rejection & Revision Continuity Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_rejection_and_revision_attempt_handling(
    cms_agent: CmsContractAgent,
    valid_grant: DevelopmentTaskGrant,
    base_schema: CmsContentModelSchema,
) -> None:
    """att-1 candidate remains sealed and immutable; att-2 incorporates reviewer feedback."""
    context = {"current_schema": base_schema.model_dump(mode="json")}

    # Step 1: Initial attempt (att-1)
    cand_1 = await cms_agent.execute_cms_task(
        grant=valid_grant,
        context=context,
        attempt_id="att-1",
    )
    hash_1 = cand_1.candidate_hash

    # Step 2: Human reviewer rejects and gives feedback
    reviewer_feedback = "Please add a tags field of type array/string and make it optional."

    cand_2 = await cms_agent.execute_cms_task(
        grant=valid_grant,
        context=context,
        attempt_id="att-2",
        previous_candidate=cand_1,
        reviewer_feedback=reviewer_feedback,
    )
    hash_2 = cand_2.candidate_hash

    # att-1 remains unchanged
    assert cand_1.candidate_hash == hash_1

    # att-2 has new candidate_id and candidate_hash
    assert cand_2.candidate_id != cand_1.candidate_id
    assert hash_2 != hash_1
    assert cand_2.provenance["previous_candidate_hash"] == hash_1
    assert cand_2.provenance["attempt_id"] == "att-2"


# ===========================================================================
# 7. Deterministic Sealing & Canonical Bytes Tests
# ===========================================================================

def test_deterministic_candidate_sealing(base_schema: CmsContentModelSchema) -> None:
    """Two identical candidate objects must produce identical SHA-256 candidate hashes."""
    from app.schemas.cms import (
        CmsCompatibilityReport,
        CmsDetailedSchemaDiff,
        CmsMigrationPlan,
        CmsValidationEvidence,
    )

    common_kwargs = {
        "candidate_id": "cand-test-fixed",
        "task_id": "task-test-01",
        "workflow_id": "wf-01",
        "schema_definition": base_schema,
        "json_schema_draft_2020_12": base_schema.to_json_schema_draft_2020_12(),
        "typescript_interfaces": base_schema.to_typescript_interface(),
        "detailed_diff": CmsDetailedSchemaDiff(model_name="blog_post"),
        "change_classification": CmsChangeClassification.COMPATIBLE,
        "compatibility_report": CmsCompatibilityReport(
            is_breaking=False,
            change_classification=CmsChangeClassification.COMPATIBLE,
        ),
        "migration_plan": CmsMigrationPlan(steps=[]),
        "validation_evidence": CmsValidationEvidence(
            ast_valid=True,
            json_schema_valid=True,
            migration_simulated=True,
            rollback_simulated=True,
            confidence=0.95,
        ),
    }

    c1 = CmsCandidateDeliverable(**common_kwargs)
    c2 = CmsCandidateDeliverable(**common_kwargs)

    assert c1.canonical_bytes() == c2.canonical_bytes()
    assert c1.compute_candidate_hash() == c2.compute_candidate_hash()
    assert len(c1.compute_candidate_hash()) == 64


# ===========================================================================
# 8. Integration with DevelopmentAgent & ProvenanceRecorder Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_development_agent_execute_cms_step_with_provenance(
    dev_agent: DevelopmentAgent,
    valid_grant: DevelopmentTaskGrant,
    base_schema: CmsContentModelSchema,
) -> None:
    """DevelopmentAgent.execute_cms_step records DEV-CMS provenance and returns sealed candidate."""
    repo = FakeProvenanceRepository()
    recorder = ProvenanceRecorder(repo)

    context = {"current_schema": base_schema.model_dump(mode="json")}

    candidate, candidate_hash = await dev_agent.execute_cms_step(
        grant=valid_grant,
        context=context,
        workflow_id="wf-integ-01",
        attempt_id="att-1",
        provenance_recorder=recorder,
    )

    assert isinstance(candidate, CmsCandidateDeliverable)
    assert candidate_hash == candidate.candidate_hash

    # Verify provenance event recorded
    events = repo._chains.get(valid_grant.tenant_scope.tenant_id, [])
    assert len(events) >= 1
    cms_event = [e for e in events if e.agent == "DEV-CMS"][0]
    assert cms_event.tenant_id == valid_grant.tenant_scope.tenant_id
    assert cms_event.metadata["candidate_hash"] == candidate_hash
    assert cms_event.metadata["attempt_id"] == "att-1"


# ===========================================================================
# 9. Direct Sandbox micro_tools Tests
# ===========================================================================

def test_sandbox_micro_tools_cms_operations(base_schema: CmsContentModelSchema) -> None:
    """Direct execution of all CMS micro-tools inside execute_s_code."""
    target_schema = base_schema.model_copy(deep=True)
    target_schema.version = "1.2.0"
    target_schema.fields.append(
        CmsFieldDefinition(
            name="tags",
            field_type=CmsFieldType.JSON,
            label="Tags",
            required=False,
        )
    )

    curr_dict = base_schema.model_dump(mode="json")
    targ_dict = target_schema.model_dump(mode="json")

    # 1. validate_cms_schema
    res_val = execute_s_code("validate_cms_schema", schema=targ_dict)
    assert res_val["status"] == "SUCCESS"
    assert res_val["output"]["is_valid"] is True

    # 2. generate_schema_diff
    res_diff = execute_s_code("generate_schema_diff", current_schema=curr_dict, target_schema=targ_dict)
    assert res_diff["status"] == "SUCCESS"
    assert len(res_diff["output"]["added_fields"]) == 1
    assert res_diff["output"]["added_fields"][0]["name"] == "tags"

    # 3. analyze_compatibility
    res_compat = execute_s_code("analyze_compatibility", current_schema=curr_dict, target_schema=targ_dict)
    assert res_compat["status"] == "SUCCESS"
    assert res_compat["output"]["is_breaking"] is False

    # 4. generate_migration
    res_mig = execute_s_code("generate_migration", current_schema=curr_dict, target_schema=targ_dict)
    assert res_mig["status"] == "SUCCESS"
    steps = res_mig["output"]["steps"]
    assert len(steps) >= 1

    # 5. simulate_migration
    res_sim = execute_s_code("simulate_migration", steps=steps)
    assert res_sim["status"] == "SUCCESS"
    assert res_sim["output"]["forward_success"] is True
    assert res_sim["output"]["rollback_success"] is True

    # 6. generate_contracts
    res_contracts = execute_s_code("generate_contracts", schema=targ_dict)
    assert res_contracts["status"] == "SUCCESS"
    assert res_contracts["output"]["json_schema"]["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert "export interface BlogPost" in res_contracts["output"]["typescript_interfaces"]
