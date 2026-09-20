"""Unit tests for T20: Creative Content Generation & Channel Adaptation (W_CREAT + S_COPY)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agents.base import BoundedWorkerAgent
from app.agents.creative_content import CreativeContentAgent
from app.core.exceptions import PolicyViolationError, SandboxInvocationError
from app.integrations.sandbox.capabilities import validate_capability_access
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.micro_tools import execute_s_copy
from app.schemas.agent_contracts import (
    AdaptedCreativePack,
    AdCopyVariant,
    ConceptItem,
    ConceptPack,
    ContentScheduleItem,
    CopyPack,
    CreativePackage,
    CreativePlan,
    PlatformSpecItem,
    PlatformSpecSnapshot,
    QAFinding,
    QAReasonCode,
    QAReport,
    QAStatus,
    ResearchBrief,
    ResearchFindingItem,
    TaskGrant,
    VisualBrief,
    VisualPack,
)
from app.schemas.governance import TenantScope, WorkerRole
from app.schemas.sandbox import SandboxCapability
from tests.conftest import FakeSandboxClient


def test_s_copy_with_t16_claims_and_t19_strategy() -> None:
    """S_COPY grounds copy variants in T16 claims, adapts across T19 channels, and generates briefs and schedules."""
    payload = {
        "task_id": "task-copy-001",
        "tenant_id": "acme_corp",
        "brand_id": "acme_glow",
        "brand_voice": "punchy and authoritative",
        "objective": "Q4 acquisition campaign",
        "target_audience": "enterprise leaders",
        "channels": "meta,google,tiktok,linkedin,email",
        "t16_claims": json.dumps([
            {
                "id": "claim-hydra-01",
                "text": "Clinically proven 42% hydration improvement in 28 days.",
                "category": "clinical",
                "validation_status": "SUPPORTED",
            },
            {
                "id": "claim-perf-02",
                "text": "Reduces operational overhead by 35% in enterprise environments.",
                "category": "performance",
                "validation_status": "SUPPORTED",
            },
        ]),
        "t19_strategy": json.dumps({
            "plan_id": "strat-q4-acme",
            "channels": ["meta", "google", "tiktok", "linkedin", "email"],
            "target_audience": "enterprise leaders",
        }),
        "required_disclaimers": "*Results based on double-blind 28-day clinical trial.",
    }

    result = execute_s_copy(payload)

    assert result["status"] == "success"
    assert result["task_id"] == "task-copy-001"
    assert "headline" in result
    assert float(result["hook_score"]) >= 0.8
    assert int(result["variants_count"]) == 5
    assert int(result["visual_briefs_count"]) == 5
    assert int(result["schedules_count"]) == 5

    # Verify structured package
    package_data = json.loads(result["creative_package"])
    package = CreativePackage.model_validate(package_data)

    assert package.package_id == "pkg-task-copy-001"
    assert package.tenant_id == "acme_corp"
    assert len(package.ad_copy_variants) == 5
    assert len(package.visual_briefs) == 5
    assert len(package.social_posts) >= 3
    assert len(package.schedules) == 5

    # Check channels adapted
    channels = [v.channel for v in package.ad_copy_variants]
    assert "meta" in channels
    assert "google" in channels
    assert "tiktok" in channels
    assert "linkedin" in channels
    assert "email" in channels

    # Check claim grounding
    for variant in package.ad_copy_variants:
        assert len(variant.source_claim_ids) >= 1
        assert variant.source_claim_ids[0] in ("claim-hydra-01", "claim-perf-02")
        assert variant.cta != ""
        assert len(variant.cta_variants) >= 2


def test_s_copy_screens_prohibited_terms() -> None:
    """S_COPY strictly screens out prohibited terms from headlines, hooks, and body copy."""
    payload = {
        "task_id": "task-copy-proh",
        "brand_voice": "innovative",
        "objective": "enterprise growth",
        "prohibited_terms": "secret, formula, miracle",
        "channels": "meta,google",
        "t16_claims": json.dumps([
            {"id": "c1", "text": "Validated workflow improvement.", "status": "SUPPORTED"}
        ]),
    }

    result = execute_s_copy(payload)
    assert result["status"] == "success"

    package = CreativePackage.model_validate_json(result["creative_package"])
    for variant in package.ad_copy_variants:
        assert "secret" not in variant.headline.lower()
        assert "formula" not in variant.headline.lower()
        assert "miracle" not in variant.headline.lower()
        assert "secret" not in variant.body_copy.lower()
        assert "formula" not in variant.body_copy.lower()


def test_s_copy_flags_unsupported_claims() -> None:
    """S_COPY detects and flags unsupported claims, excluding them from approved references."""
    payload = {
        "task_id": "task-copy-unsupported",
        "t16_claims": json.dumps([
            {"id": "claim-approved-1", "text": "Verified 20% speed gain.", "status": "SUPPORTED"}
        ]),
        "unapproved_claims": json.dumps([
            "Cures all workflow issues instantly and guarantees 1000% ROI.",
        ]),
        "channels": "meta",
    }

    result = execute_s_copy(payload)
    assert result["status"] == "success"

    package = CreativePackage.model_validate_json(result["creative_package"])
    assert len(package.flagged_unsupported_claims) == 1
    assert "Cures all workflow issues instantly" in package.flagged_unsupported_claims[0]
    assert len(package.compliance_warnings) >= 1

    # Verify that only the approved claim was linked to variants
    for variant in package.ad_copy_variants:
        assert "claim-approved-1" in variant.source_claim_ids
        assert "1000% ROI" not in variant.body_copy


@pytest.mark.asyncio
async def test_w_creat_generates_valid_evidence_envelope_and_creative_package() -> None:
    """CreativeContentAgent processes T16 and T19 inputs and produces valid EvidenceEnvelope and CreativePackage."""
    agent = CreativeContentAgent()

    grant = TaskGrant(
        task_id="task-creat-e2e-1",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="tenant_omega", brand_ids=["brand_alpha"], allowed_channels=["meta", "linkedin"]),
        brand_id="brand_alpha",
        objective="Launch Q4 B2B campaign",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )

    context: dict[str, object] = {
        "objective": "Launch Q4 B2B campaign",
        "target_audience": "enterprise CTOs",
        "claims_dossier": {
            "tenant_id": "tenant_omega",
            "claims": [
                {
                    "claim_id": "c-alpha-01",
                    "claim_text": "Zero data leaks across 10 million test transactions.",
                    "validation_status": "SUPPORTED",
                    "confidence": 0.95,
                }
            ],
        },
        "strategy_plan": {
            "tenant_id": "tenant_omega",
            "plan_id": "strat-omega-01",
            "channel_allocations": [
                {"channel": "linkedin", "allocated_amount": 15000.0, "percentage_of_total": 0.60},
                {"channel": "meta", "allocated_amount": 10000.0, "percentage_of_total": 0.40},
            ],
            "target_audience": "enterprise CTOs",
        },
        "required_disclaimers": "*Independent SOC2 audit conducted June 2026.",
    }

    envelope = await agent.run(grant, context)

    assert envelope.task_id == "task-creat-e2e-1"
    assert envelope.worker_role == WorkerRole.CREATIVE_CONTENT
    assert envelope.confidence.point_estimate >= 0.8
    assert "creative:task-creat-e2e-1" in envelope.generated_artifacts
    assert "copy:task-creat-e2e-1" in envelope.generated_artifacts
    assert envelope.provenance["capability"] == "NONE"
    assert envelope.provenance["agent"] == "W_CREAT"
    assert len(envelope.findings) >= 4

    # Extract strongly typed CreativePackage
    pkg = agent.extract_creative_package(envelope)
    assert pkg is not None
    assert pkg.package_id == "pkg-task-creat-e2e-1"
    assert pkg.tenant_id == "tenant_omega"
    assert len(pkg.ad_copy_variants) == 2
    assert len(pkg.visual_briefs) == 2
    assert len(pkg.schedules) == 2


@pytest.mark.asyncio
async def test_missing_t16_product_evidence_fails_closed() -> None:
    """CreativeContentAgent fails closed when T16 approved claims evidence is missing."""
    agent = CreativeContentAgent()
    grant = TaskGrant(
        task_id="task-creat-fail-t16",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="tenant_1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        # Missing T16!
        "strategy_plan": {"tenant_id": "tenant_1", "channels": ["meta"]},
    }

    with pytest.raises(ValueError, match="Missing or invalid T16 Product Evidence dependency"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_missing_t19_strategy_fails_closed() -> None:
    """CreativeContentAgent fails closed when T19 omnichannel strategy is missing."""
    agent = CreativeContentAgent()
    grant = TaskGrant(
        task_id="task-creat-fail-t19",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="tenant_1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "claims_dossier": {
            "tenant_id": "tenant_1",
            "claims": [{"claim_id": "c1", "text": "Valid", "validation_status": "SUPPORTED"}],
        },
        # Missing T19!
    }

    with pytest.raises(ValueError, match="Missing or invalid T19 Omnichannel Strategy dependency"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_cross_tenant_t16_dossier_breach_fails_closed() -> None:
    """CreativeContentAgent rejects T16 evidence originating from another tenant."""
    agent = CreativeContentAgent()
    grant = TaskGrant(
        task_id="task-creat-tenant-breach",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="tenant_alpha"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "claims_dossier": {
            "tenant_id": "tenant_beta",  # Breach!
            "claims": [{"claim_id": "c1", "text": "Valid", "validation_status": "SUPPORTED"}],
        },
        "strategy_plan": {"tenant_id": "tenant_alpha", "channels": ["meta"]},
    }

    with pytest.raises(ValueError, match="Tenant isolation breach in T16 product evidence"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_cross_tenant_t19_strategy_breach_fails_closed() -> None:
    """CreativeContentAgent rejects T19 strategy originating from another tenant."""
    agent = CreativeContentAgent()
    grant = TaskGrant(
        task_id="task-creat-strat-breach",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="tenant_alpha"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "claims_dossier": {
            "tenant_id": "tenant_alpha",
            "claims": [{"claim_id": "c1", "text": "Valid", "validation_status": "SUPPORTED"}],
        },
        "strategy_plan": {
            "tenant_id": "tenant_beta",  # Breach!
            "channels": ["meta"],
        },
    }

    with pytest.raises(ValueError, match="Tenant isolation breach in T19 omnichannel strategy"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_policy_strictly_overrides_brand_persona() -> None:
    """Policy constraints strictly take precedence over brand persona preferences."""
    agent = CreativeContentAgent()

    class MockBrandPersona:
        voice = "bold and disruptive"
        prohibited_terms = ("boring",)
        required_disclaimers = ()

    grant = TaskGrant(
        task_id="task-policy-override",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="tenant_sec"),
        policy_constraints=["prohibit:miracle", "prohibit:cure", "require:statutory_disclaimer"],
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "brand_persona": MockBrandPersona(),
        "claims_dossier": {
            "tenant_id": "tenant_sec",
            "claims": [{"claim_id": "c1", "text": "Verified efficiency.", "validation_status": "SUPPORTED"}],
        },
        "strategy_plan": {"tenant_id": "tenant_sec", "channels": ["meta"]},
    }

    (
        approved_claims,
        strategy_plan,
        channels,
        prohibited_terms,
        required_disclaimers,
        unapproved_claims,
        brand_voice,
        objective,
        target_audience,
    ) = agent._verify_and_normalize_dependencies(grant, context)

    # Policy terms must be present in prohibited_terms
    assert "miracle" in prohibited_terms
    assert "cure" in prohibited_terms
    assert "boring" in prohibited_terms


def test_unauthorized_capability_access_rejection() -> None:
    """Requesting COPY capability with unauthorized worker role fails closed."""
    # WorkerRole.STRATEGY is only allowed ALLOC, not COPY
    with pytest.raises(SandboxInvocationError, match="Capability access denied"):
        validate_capability_access(
            capability=SandboxCapability.COPY,
            worker_role=WorkerRole.STRATEGY,
            operation="generate_variants",
        )


def test_w_creat_rejects_sandbox_client() -> None:
    """W_CREAT coordinator has zero sandbox capability and strictly rejects SandboxClient."""
    with pytest.raises(PolicyViolationError, match="zero-sandbox and must not receive a SandboxClient"):
        CreativeContentAgent(sandbox_client=SandboxClient())


def test_w_creat_cannot_build_sandbox_payload() -> None:
    """W_CREAT coordinator cannot build sandbox payloads."""
    agent = CreativeContentAgent()
    grant = TaskGrant(
        task_id="task-test-payload",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="t1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    with pytest.raises(PolicyViolationError, match="zero sandbox capability"):
        agent.build_payload(grant, {})


@pytest.mark.asyncio
async def test_w_creat_plan_scope_expansion_fails_closed() -> None:
    """W_CREAT fails closed if LLM produces CreativePlan with unauthorized channels or evidence."""
    class BadChannelLlm:
        async def generate_structured_with_metadata(self, **kwargs):
            return CreativePlan(
                tenant_id="t1",
                task_id="task-expand",
                approved_objectives=["Growth"],
                approved_channels=["meta", "unauthorized_tiktok"],
                required_deliverables=["copy_pack"],
                evidence_manifest=["c1"],
                prohibited_scope=[],
                expected_artifact_types=["AdCopyVariant"],
            ), {}

    agent = CreativeContentAgent(llm_client=BadChannelLlm())  # type: ignore[arg-type]
    grant = TaskGrant(
        task_id="task-expand",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="t1", allowed_channels=["meta"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    context: dict[str, object] = {
        "claims_dossier": {"tenant_id": "t1", "claims": [{"claim_id": "c1", "text": "Valid", "validation_status": "SUPPORTED"}]},
        "strategy_plan": {"tenant_id": "t1", "channels": ["meta"]},
    }
    with pytest.raises(PolicyViolationError, match="CreativePlan expanded channel scope"):
        await agent.run(grant, context)


@pytest.mark.asyncio
async def test_w_creat_qa_block_returns_fail_closed_envelope() -> None:
    """When QA reports BLOCK, W_CREAT returns zero-confidence blocked envelope with empty deliverables."""
    class BlockWorkflow:
        async def run(self, grant, plan, context):
            from app.orchestration.creative_content_workflow import CreativeWorkflowResult
            report = QAReport(
                tenant_id=grant.tenant_scope.tenant_id,
                task_id=grant.task_id,
                evaluated_artifact_hash="bad_hash" + "0" * 56,
                status=QAStatus.BLOCK,
                reason_code=QAReasonCode.EVIDENCE_MISSING,
                findings=[QAFinding(layer="grounding", severity="critical", message="Unsupported claim detected.")],
            )
            report.compute_artifact_hash()
            return CreativeWorkflowResult(plan=plan, qa_report=report, artifact_hashes={})

    agent = CreativeContentAgent(workflow=BlockWorkflow())  # type: ignore[arg-type]
    grant = TaskGrant(
        task_id="task-qa-block",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="t1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    context: dict[str, object] = {
        "claims_dossier": {"tenant_id": "t1", "claims": [{"claim_id": "c1", "text": "Valid", "validation_status": "SUPPORTED"}]},
        "strategy_plan": {"tenant_id": "t1", "channels": ["meta"]},
    }
    envelope = await agent.run(grant, context)
    assert envelope.confidence.point_estimate == 0.0
    assert envelope.proposed_state_changes["status"] == "blocked"
    assert envelope.generated_artifacts == []


@pytest.mark.asyncio
async def test_w_creat_packages_unchanged_approved_artifacts_with_matching_hashes() -> None:
    """W_CREAT packages workflow artifacts without post-QA mutation; artifact hashes remain identical."""
    agent = CreativeContentAgent()
    grant = TaskGrant(
        task_id="task-immutable-pkg",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="t1", allowed_channels=["meta"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    context: dict[str, object] = {
        "claims_dossier": {"tenant_id": "t1", "claims": [{"claim_id": "c1", "text": "Real metric", "validation_status": "SUPPORTED"}]},
        "strategy_plan": {"tenant_id": "t1", "channels": ["meta"]},
    }
    envelope = await agent.run(grant, context)
    pkg = agent.extract_creative_package(envelope)
    assert pkg is not None
    assert pkg.qa_status == "PASS"
    assert envelope.provenance["qa_status"] == "PASS"
    assert envelope.provenance["capability"] == "NONE"
    assert "qa_hash" in pkg.provenance
    assert pkg.provenance["qa_hash"] == envelope.provenance["qa_report_hash"]


def test_model_a_no_direct_rag_or_database_imports() -> None:
    """Model-A architectural invariant: W_CREAT must not import RAG or persistence modules."""
    import inspect

    import app.agents.creative_content as cc_module

    source = inspect.getsource(cc_module)

    assert "app.services.rag" not in source
    assert "app.persistence" not in source
    assert "app.orchestration.rag_query_dispatch" not in source
    assert "sqlalchemy" not in source
    assert "publish" not in source.lower() or "no publish" in source.lower() or "cadence" in source.lower()


class _ZeroSandboxWorker(BoundedWorkerAgent):
    """Test worker representing zero-capability coordinator (W_CREAT)."""

    capability = None

    def build_payload(self, grant: TaskGrant, context: dict) -> dict:
        return {"operation": "noop"}


@pytest.mark.asyncio
async def test_zero_sandbox_worker_fails_closed_on_sandbox_execution() -> None:
    """T1 boundary: BoundedWorkerAgent with capability=None fails closed on sandbox call."""
    fake_sandbox = FakeSandboxClient()
    agent = _ZeroSandboxWorker(sandbox_client=fake_sandbox)

    grant = TaskGrant(
        task_id="task-zero-sbx-01",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    with pytest.raises(PolicyViolationError, match="has no authorized sandbox capability"):
        await agent.run(grant, context={})

    assert len(fake_sandbox.invocations) == 0


@pytest.mark.asyncio
async def test_bounded_worker_missing_sandbox_client_fails_closed() -> None:
    """T1 boundary: BoundedWorkerAgent without sandbox_client fails closed on sandbox call."""
    class _WorkerWithCap(BoundedWorkerAgent):
        capability = SandboxCapability.COPY

        def build_payload(self, grant: TaskGrant, context: dict) -> dict:
            return {"operation": "generate_variants"}

    agent = _WorkerWithCap(sandbox_client=None)
    grant = TaskGrant(
        task_id="task-no-client-01",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    with pytest.raises(PolicyViolationError, match="has no sandbox client configured"):
        await agent.run(grant, context={})


def test_creative_contracts_scope_lineage_and_hashing() -> None:
    """T1 contracts: Typed contracts validate scope, lineage, and SHA-256 digests."""
    # 1. CreativePlan
    plan = CreativePlan(
        tenant_id="acme",
        task_id="task-creat-001",
        approved_objectives=["Q4 acquisition"],
        approved_channels=["meta", "linkedin"],
        required_deliverables=["copy_pack", "visual_pack", "adapted_pack"],
        evidence_manifest=["claim-hydra-01"],
        prohibited_scope=["tiktok", "unsupported_claims"],
        expected_artifact_types=["AdCopyVariant", "VisualBrief"],
    )
    plan_hash = plan.compute_artifact_hash()
    assert len(plan_hash) == 64
    assert plan.artifact_hash == plan_hash
    assert plan.approved_channels == ["meta", "linkedin"]

    # 2. ResearchBrief
    brief = ResearchBrief(
        tenant_id="acme",
        task_id="task-creat-001",
        objective="Platform specs research",
        platform_scope=["meta", "linkedin"],
        findings=[
            ResearchFindingItem(
                source_url="https://ads.meta.com/guidance",
                domain="ads.meta.com",
                publisher="Meta",
                extracted_finding="Meta recommends 9:16 vertical video for Reels.",
                citation="[Meta Guidance 2026]",
            )
        ],
        citations=["https://ads.meta.com/guidance"],
    )
    brief_hash = brief.compute_artifact_hash()
    assert len(brief_hash) == 64
    assert brief.findings[0].domain == "ads.meta.com"

    # 3. PlatformSpecSnapshot
    spec = PlatformSpecSnapshot(
        tenant_id="acme",
        task_id="task-creat-001",
        platform="meta",
        placement="reels",
        specs=[
            PlatformSpecItem(
                platform="meta",
                placement="reels",
                ratios=["9:16"],
                text_limits={"headline": 40, "primary_text": 125},
                safe_zone_requirements={"top_margin_px": 100, "bottom_margin_px": 250},
            )
        ],
    )
    spec_hash = spec.compute_artifact_hash()
    assert len(spec_hash) == 64
    assert spec.specs[0].ratios == ["9:16"]

    # 4. ConceptPack
    concept = ConceptPack(
        tenant_id="acme",
        task_id="task-creat-001",
        concepts=[
            ConceptItem(
                concept_id="cpt-1",
                territory="clinical efficacy",
                audience_tension="skepticism about synthetic moisturizers",
                message_angle="proven clinical turnaround",
                narrative_architecture="hook: clinical failure -> body: hydration -> cta: trial",
                approved_evidence_refs=["claim-hydra-01"],
            )
        ],
    )
    assert len(concept.compute_artifact_hash()) == 64

    # 5. CopyPack
    copy_pack = CopyPack(
        tenant_id="acme",
        task_id="task-creat-001",
        concept_ref="cpt-1",
        variants=[
            AdCopyVariant(
                variant_id="var-1",
                channel="meta",
                headline="Clinically Proven 42% Hydration",
                body_copy="See real results in 28 days.",
                cta="Shop Now",
                source_claim_ids=["claim-hydra-01"],
            )
        ],
        factual_claim_refs=["claim-hydra-01"],
    )
    assert len(copy_pack.compute_artifact_hash()) == 64

    # 6. VisualPack
    vis_pack = VisualPack(
        tenant_id="acme",
        task_id="task-creat-001",
        concept_ref="cpt-1",
        visual_territory="laboratory clean",
        composition="minimalist split-screen before/after",
        production_briefs=[
            VisualBrief(
                brief_id="vb-1",
                asset_title="Clinical Results 1:1",
                channel="meta",
                aspect_ratio="1:1",
            )
        ],
    )
    assert len(vis_pack.compute_artifact_hash()) == 64

    # 7. AdaptedCreativePack
    adapt_pack = AdaptedCreativePack(
        tenant_id="acme",
        task_id="task-creat-001",
        channel="meta",
        ad_copy_variants=copy_pack.variants,
        visual_briefs=vis_pack.production_briefs,
        calendar_proposal=[
            ContentScheduleItem(
                schedule_id="sch-1",
                day_or_week="Week 1 - Day 1",
                channel="meta",
                variant_ref="var-1",
                primary_objective="Cold audience clinical proof",
            )
        ],
    )
    assert len(adapt_pack.compute_artifact_hash()) == 64


def test_qa_report_status_and_fail_closed_unsupported_evidence() -> None:
    """T1 QA contract: QAReport enforces PASS/REVISE/BLOCK and fails closed on bad evidence."""
    # PASS
    pass_report = QAReport(
        tenant_id="acme",
        task_id="task-creat-001",
        evaluated_artifact_hash="a" * 64,
        status=QAStatus.PASS,
        passed_checks=["grounding_verified", "channel_scope_verified", "format_verified"],
    )
    assert pass_report.status == QAStatus.PASS
    assert pass_report.reason_code is None

    # REVISE with static reason code
    revise_report = QAReport(
        tenant_id="acme",
        task_id="task-creat-001",
        evaluated_artifact_hash="b" * 64,
        status=QAStatus.REVISE,
        reason_code=QAReasonCode.COPY,
        findings=[
            QAFinding(
                layer="platform",
                severity="high",
                reason_code=QAReasonCode.COPY,
                message="Headline exceeds LinkedIn 40-character limit.",
                affected_artifact_ids=["var-1"],
                recommended_responsible_stage="COPY",
            )
        ],
    )
    assert revise_report.status == QAStatus.REVISE
    assert revise_report.reason_code == QAReasonCode.COPY

    # BLOCK with unsupported evidence
    block_report = QAReport(
        tenant_id="acme",
        task_id="task-creat-001",
        evaluated_artifact_hash="c" * 64,
        status=QAStatus.BLOCK,
        reason_code=QAReasonCode.EVIDENCE_MISSING,
        missing_evidence_claims=["claim-unsupported-magic-cure"],
        findings=[
            QAFinding(
                layer="grounding",
                severity="critical",
                reason_code=QAReasonCode.EVIDENCE_MISSING,
                message="Factual claim has no approved T16 evidence ref; fail closed.",
                evidence_refs=[],
            )
        ],
    )
    assert block_report.status == QAStatus.BLOCK
    assert block_report.reason_code == QAReasonCode.EVIDENCE_MISSING
    assert "claim-unsupported-magic-cure" in block_report.missing_evidence_claims


def test_existing_workers_sandbox_capabilities_unaffected() -> None:
    """T1 boundary: Other worker classes retain their required sandbox capabilities."""
    from app.agents.competitor_intel_engine.competitor_intel import CompetitorIntelAgent
    from app.agents.customer_voice_engine.customer_voice import CustomerVoiceAgent
    from app.agents.development_engine.development import DevelopmentAgent
    from app.agents.learning_performance_engine.learning_performance import (
        LearningPerformanceAgent,
    )
    from app.agents.product_evidence_engine.product_evidence import ProductEvidenceAgent
    from app.agents.strategy_engine.strategy import StrategyAgent

    assert DevelopmentAgent.capability == SandboxCapability.CODE
    assert StrategyAgent.capability == SandboxCapability.ALLOC
    assert ProductEvidenceAgent.capability == SandboxCapability.VAL
    assert CompetitorIntelAgent.capability == SandboxCapability.SCRAPE
    assert CustomerVoiceAgent.capability == SandboxCapability.PARSE
    assert LearningPerformanceAgent.capability == SandboxCapability.ATTR


# =============================================================================
# T3: Creative Specialist Layer Verification Tests
# =============================================================================


@pytest.mark.asyncio
async def test_six_specialists_have_distinct_identities_and_independent_contexts() -> None:
    """T3: Prove six distinct specialist identities with independent injected dependencies."""
    from app.agents.creative_content_engine.subagents.research import CreativeResearchAgent
    from app.agents.creative_content_engine.subagents.concept import CreativeConceptAgent
    from app.agents.creative_content_engine.subagents.copy import CreativeCopyAgent
    from app.agents.creative_content_engine.subagents.visual import CreativeVisualAgent
    from app.agents.creative_content_engine.subagents.adaptation import CreativeAdaptationAgent
    from app.agents.creative_content_engine.subagents.quality import CreativeQualityAgent

    class DummyLlmClient:
        def __init__(self, name: str) -> None:
            self.name = name

    research = CreativeResearchAgent(llm_client=DummyLlmClient("llm-research"))
    concept = CreativeConceptAgent(llm_client=DummyLlmClient("llm-concept"))
    copy = CreativeCopyAgent(llm_client=DummyLlmClient("llm-copy"))
    visual = CreativeVisualAgent(llm_client=DummyLlmClient("llm-visual"))
    adapt = CreativeAdaptationAgent(llm_client=DummyLlmClient("llm-adapt"))
    qa = CreativeQualityAgent(llm_client=DummyLlmClient("llm-qa"))

    specialists = [research, concept, copy, visual, adapt, qa]
    identities = [s.specialist_id for s in specialists]

    assert len(identities) == 6
    assert len(set(identities)) == 6
    assert identities == [
        "CREAT-RESEARCH",
        "CREAT-CONCEPT",
        "CREAT-COPY",
        "CREAT-VISUAL",
        "CREAT-ADAPT",
        "CREAT-QA",
    ]


@pytest.mark.asyncio
async def test_specialists_typed_io_contract_compliance() -> None:
    """T3: Prove each specialist satisfies its typed input/output contract."""
    from app.agents.creative_content_engine.subagents.research import CreativeResearchAgent
    from app.agents.creative_content_engine.subagents.concept import CreativeConceptAgent
    from app.agents.creative_content_engine.subagents.copy import CreativeCopyAgent
    from app.agents.creative_content_engine.subagents.visual import CreativeVisualAgent
    from app.agents.creative_content_engine.subagents.adaptation import CreativeAdaptationAgent
    from app.agents.creative_content_engine.subagents.quality import CreativeQualityAgent

    grant = TaskGrant(
        task_id="task-t3-001",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="tenant_acme"),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        objective="Q4 Enterprise Performance Campaign",
    )

    plan = CreativePlan(
        tenant_id="tenant_acme",
        task_id="task-t3-001",
        approved_objectives=["Q4 Enterprise Performance Campaign"],
        approved_channels=["meta", "linkedin", "tiktok"],
        required_deliverables=["ad_copy", "visual_brief", "social_posts"],
        evidence_manifest=["claim-perf-42", "claim-soc2-certified"],
        prohibited_scope=["unverified", "cure"],
        target_audience="enterprise IT buyers",
    )
    plan.compute_artifact_hash()

    # 1. CREAT-RESEARCH -> (ResearchBrief, PlatformSpecSnapshot)
    research_agent = CreativeResearchAgent()
    brief, spec_snapshot = await research_agent.run(grant=grant, plan=plan)

    assert isinstance(brief, ResearchBrief)
    assert isinstance(spec_snapshot, PlatformSpecSnapshot)
    assert brief.producing_agent_id == "CREAT-RESEARCH"
    assert spec_snapshot.producing_agent_id == "CREAT-RESEARCH"
    assert brief.artifact_hash != ""
    assert spec_snapshot.artifact_hash != ""
    assert len(brief.findings) >= 3
    assert len(brief.citations) >= 3

    # 2. CREAT-CONCEPT -> ConceptPack
    concept_agent = CreativeConceptAgent()
    concept_pack = await concept_agent.run(grant=grant, plan=plan)

    assert isinstance(concept_pack, ConceptPack)
    assert concept_pack.producing_agent_id == "CREAT-CONCEPT"
    assert concept_pack.artifact_hash != ""
    assert len(concept_pack.concepts) >= 2
    for cpt in concept_pack.concepts:
        assert cpt.approved_evidence_refs == ["claim-perf-42", "claim-soc2-certified"]
        assert cpt.territory != ""
        assert cpt.audience_tension != ""

    # 3. CREAT-COPY -> CopyPack
    copy_agent = CreativeCopyAgent()
    copy_pack = await copy_agent.run(grant=grant, concept_pack=concept_pack, plan=plan)

    assert isinstance(copy_pack, CopyPack)
    assert copy_pack.producing_agent_id == "CREAT-COPY"
    assert copy_pack.artifact_hash != ""
    assert len(copy_pack.variants) == len(plan.approved_channels)
    for variant in copy_pack.variants:
        assert variant.source_claim_ids[0] in plan.evidence_manifest
        assert variant.hook_angle != ""
        assert variant.headline != ""

    # 4. CREAT-VISUAL -> VisualPack
    visual_agent = CreativeVisualAgent()
    visual_pack = await visual_agent.run(
        grant=grant, concept_pack=concept_pack, plan=plan, platform_specs=spec_snapshot
    )

    assert isinstance(visual_pack, VisualPack)
    assert visual_pack.producing_agent_id == "CREAT-VISUAL"
    assert visual_pack.artifact_hash != ""
    assert len(visual_pack.storyboard) >= 3
    assert len(visual_pack.production_briefs) == len(plan.approved_channels)

    # 5. CREAT-ADAPT -> AdaptedCreativePack
    adapt_agent = CreativeAdaptationAgent()
    adapted_pack = await adapt_agent.run(
        grant=grant,
        copy_pack=copy_pack,
        visual_pack=visual_pack,
        platform_specs=spec_snapshot,
        plan=plan,
    )

    assert isinstance(adapted_pack, AdaptedCreativePack)
    assert adapted_pack.producing_agent_id == "CREAT-ADAPT"
    assert adapted_pack.artifact_hash != ""
    assert len(adapted_pack.ad_copy_variants) == len(plan.approved_channels)
    assert len(adapted_pack.social_posts) == len(plan.approved_channels)
    assert len(adapted_pack.calendar_proposal) == len(plan.approved_channels)

    # 6. CREAT-QA -> QAReport
    qa_agent = CreativeQualityAgent()
    qa_report = await qa_agent.run(
        grant=grant,
        plan=plan,
        concept_pack=concept_pack,
        copy_pack=copy_pack,
        visual_pack=visual_pack,
        adapted_pack=adapted_pack,
    )

    assert isinstance(qa_report, QAReport)
    assert qa_report.producing_agent_id == "CREAT-QA"
    assert qa_report.artifact_hash != ""
    assert qa_report.status == QAStatus.PASS
    assert qa_report.reason_code is None
    assert len(qa_report.passed_checks) >= 3


@pytest.mark.asyncio
async def test_specialist_tool_requests_cannot_exceed_fixed_allowlists() -> None:
    """T3: Prove specialist sandbox requests cannot exceed fixed allowlists (DENY_ALL / fixed)."""
    from app.agents.creative_content_engine.subagents.research import CreativeResearchAgent
    from app.agents.creative_content_engine.subagents.concept import CreativeConceptAgent
    from app.agents.creative_content_engine.subagents.copy import CreativeCopyAgent
    from app.agents.creative_content_engine.subagents.visual import CreativeVisualAgent
    from app.agents.creative_content_engine.subagents.adaptation import CreativeAdaptationAgent
    from app.agents.creative_content_engine.subagents.quality import CreativeQualityAgent
    from app.schemas.sandbox import NetworkPolicy

    # CREAT-RESEARCH: allowlisted public egress only
    research = CreativeResearchAgent()
    valid_mandate = research.build_sandbox_mandate(
        task_id="t1",
        tenant_id="acme",
        operation="fetch_platform_specs",
        payload={"platform": "meta"},
    )
    assert valid_mandate.network_policy == NetworkPolicy.ALLOWLIST
    assert valid_mandate.capability == SandboxCapability.SCRAPE
    with pytest.raises(PolicyViolationError, match="not authorized"):
        research.build_sandbox_mandate(
            task_id="t1",
            tenant_id="acme",
            operation="unauthorized_exec",
            payload={},
        )

    # CREAT-COPY: s_copy_variant_gen only, NetworkPolicy.DISABLED
    copy = CreativeCopyAgent()
    copy_mandate = copy.build_sandbox_mandate(
        task_id="t1",
        tenant_id="acme",
        operation="s_copy_variant_gen",
        payload={"task_id": "t1"},
    )
    assert copy_mandate.network_policy == NetworkPolicy.DISABLED
    assert copy_mandate.capability == SandboxCapability.COPY
    with pytest.raises(PolicyViolationError, match="not authorized"):
        copy.build_sandbox_mandate(
            task_id="t1",
            tenant_id="acme",
            operation="execute_arbitrary_shell",
            payload={},
        )

    # CREAT-CONCEPT, CREAT-VISUAL, CREAT-ADAPT, CREAT-QA: DENY_ALL
    for specialist in [
        CreativeConceptAgent(),
        CreativeVisualAgent(),
        CreativeAdaptationAgent(),
        CreativeQualityAgent(),
    ]:
        assert specialist.allowed_operations == ()
        with pytest.raises(PolicyViolationError, match="DENY_ALL"):
            specialist.build_sandbox_mandate(
                task_id="t1",
                tenant_id="acme",
                operation="any_op",
                payload={},
            )


@pytest.mark.asyncio
async def test_unsupported_factual_claims_fail_closed() -> None:
    """T3: Prove missing or unsupported claims fail closed in concept, copy, and QA."""
    from app.agents.creative_content_engine.subagents.concept import CreativeConceptAgent
    from app.agents.creative_content_engine.subagents.copy import CreativeCopyAgent
    from app.agents.creative_content_engine.subagents.quality import CreativeQualityAgent

    # 1. Concept fails closed on missing evidence
    concept_agent = CreativeConceptAgent()
    empty_plan = CreativePlan(
        tenant_id="acme",
        task_id="t1",
        approved_objectives=["Awareness"],
        approved_channels=["meta"],
        evidence_manifest=[],
    )
    with pytest.raises(ValueError, match="Missing approved evidence"):
        await concept_agent.run(plan=empty_plan)

    # 2. Copy fails closed on missing evidence
    copy_agent = CreativeCopyAgent()
    with pytest.raises(ValueError, match="Missing authorized evidence"):
        await copy_agent.run(concept_pack=None, plan=empty_plan)

    # 3. QA blocks when unapproved claim is cited
    qa_agent = CreativeQualityAgent()
    valid_plan = CreativePlan(
        tenant_id="acme",
        task_id="t1",
        approved_objectives=["Awareness"],
        approved_channels=["meta"],
        evidence_manifest=["claim-real-01"],
    )
    unapproved_copy = CopyPack(
        tenant_id="acme",
        task_id="t1",
        concept_ref="cpt-1",
        variants=[
            AdCopyVariant(
                variant_id="var-1",
                channel="meta",
                headline="Ungrounded Magic Solution",
                body_copy="Completely fabricated 100% cure statement.",
                source_claim_ids=["claim-fake-unapproved"],
            )
        ],
        factual_claim_refs=["claim-fake-unapproved"],
        approved_channel_ids=["meta"],
    )
    unapproved_copy.compute_artifact_hash()

    qa_report = await qa_agent.run(plan=valid_plan, copy_pack=unapproved_copy)
    assert qa_report.status == QAStatus.BLOCK
    assert qa_report.reason_code == QAReasonCode.EVIDENCE_MISSING
    assert "claim-fake-unapproved" in qa_report.missing_evidence_claims


@pytest.mark.asyncio
async def test_qa_independent_evaluator_never_mutates_candidates() -> None:
    """T3: Prove CREAT-QA is strictly non-mutating and returns PASS | REVISE | BLOCK."""
    from app.agents.creative_content_engine.subagents.quality import CreativeQualityAgent

    plan = CreativePlan(
        tenant_id="acme",
        task_id="t1",
        approved_objectives=["Scale"],
        approved_channels=["meta"],
        evidence_manifest=["claim-1"],
        prohibited_scope=["guaranteed"],
    )

    copy_pack = CopyPack(
        tenant_id="acme",
        task_id="t1",
        concept_ref="cpt-1",
        variants=[
            AdCopyVariant(
                variant_id="var-1",
                channel="meta",
                headline="Scale With Certainty",
                body_copy="Tested benchmark performance.",
                source_claim_ids=["claim-1"],
            )
        ],
        factual_claim_refs=["claim-1"],
        approved_channel_ids=["meta"],
    )
    original_hash = copy_pack.compute_artifact_hash()
    original_headline = copy_pack.variants[0].headline

    qa_agent = CreativeQualityAgent()
    report = await qa_agent.run(plan=plan, copy_pack=copy_pack)

    # Assert candidate is completely untouched
    assert copy_pack.artifact_hash == original_hash
    assert copy_pack.variants[0].headline == original_headline
    assert report.status == QAStatus.PASS

    # Test policy block when prohibited scope is violated
    copy_pack_prohibited = CopyPack(
        tenant_id="acme",
        task_id="t1",
        concept_ref="cpt-1",
        variants=[
            AdCopyVariant(
                variant_id="var-1",
                channel="meta",
                headline="Guaranteed 100% Growth",
                body_copy="Violates prohibited scope.",
                source_claim_ids=["claim-1"],
            )
        ],
        factual_claim_refs=["claim-1"],
        approved_channel_ids=["meta"],
    )
    copy_pack_prohibited.compute_artifact_hash()
    prohibited_hash = copy_pack_prohibited.artifact_hash

    report_blocked = await qa_agent.run(plan=plan, copy_pack=copy_pack_prohibited)
    assert report_blocked.status == QAStatus.BLOCK
    assert report_blocked.reason_code == QAReasonCode.POLICY_BLOCK
    assert copy_pack_prohibited.artifact_hash == prohibited_hash


@pytest.mark.asyncio
async def test_model_a_data_isolation_and_no_scope_expansion() -> None:
    """T3: Prove Model-A data isolation and prevention of scope expansion."""
    from app.agents.creative_content_engine.subagents.research import CreativeResearchAgent
    from app.agents.creative_content_engine.subagents.quality import CreativeQualityAgent

    # 1. CREAT-RESEARCH rejects enterprise/internal data queries (Model-A isolation)
    research = CreativeResearchAgent()
    with pytest.raises(PolicyViolationError, match="strictly restricted to public reference research"):
        await research.run(context={"retrieve_internal_data": True})

    # 2. CREAT-QA blocks unapproved channels (Scope isolation)
    qa = CreativeQualityAgent()
    plan = CreativePlan(
        tenant_id="acme",
        task_id="t1",
        approved_channels=["meta"],
        evidence_manifest=["claim-1"],
    )
    unauthorized_channel_copy = CopyPack(
        tenant_id="acme",
        task_id="t1",
        variants=[
            AdCopyVariant(
                variant_id="var-1",
                channel="unapproved_tv_network",
                headline="TV Ad Headline",
                body_copy="Scope expansion.",
                source_claim_ids=["claim-1"],
            )
        ],
        approved_channel_ids=["unapproved_tv_network"],
    )
    unauthorized_channel_copy.compute_artifact_hash()

    report = await qa.run(plan=plan, copy_pack=unauthorized_channel_copy)
    assert report.status == QAStatus.BLOCK
    assert report.reason_code == QAReasonCode.SCOPE_VIOLATION



