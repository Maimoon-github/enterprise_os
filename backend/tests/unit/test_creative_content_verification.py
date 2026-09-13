"""Unit tests for T20: Creative Content Generation & Channel Adaptation (W_CREAT + S_COPY)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.agents.creative_content import CreativeContentAgent
from app.core.exceptions import SandboxInvocationError
from app.integrations.sandbox.capabilities import validate_capability_access
from app.integrations.sandbox.client import SandboxClient
from app.integrations.sandbox.micro_tools import execute_s_copy
from app.schemas.agent_contracts import (
    AdCopyVariant,
    ContentScheduleItem,
    CreativePackage,
    SocialPostVariant,
    TaskGrant,
    VisualBrief,
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
    agent = CreativeContentAgent(SandboxClient())

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
    assert envelope.provenance["capability"] == "S_COPY"
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
    agent = CreativeContentAgent(SandboxClient())
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
    agent = CreativeContentAgent(SandboxClient())
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
    agent = CreativeContentAgent(SandboxClient())
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
    agent = CreativeContentAgent(SandboxClient())
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
    agent = CreativeContentAgent(SandboxClient())

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

    payload = agent.build_payload(grant, context)
    prohibited_in_payload = payload["prohibited_terms"].split(",")

    # Policy terms must be present in payload
    assert "miracle" in prohibited_in_payload
    assert "cure" in prohibited_in_payload
    assert "boring" in prohibited_in_payload


def test_unauthorized_capability_access_rejection() -> None:
    """Requesting COPY capability with unauthorized worker role fails closed."""
    # WorkerRole.STRATEGY is only allowed ALLOC, not COPY
    with pytest.raises(SandboxInvocationError, match="Capability access denied"):
        validate_capability_access(
            capability=SandboxCapability.COPY,
            worker_role=WorkerRole.STRATEGY,
            operation="generate_variants",
        )


@pytest.mark.asyncio
async def test_sandbox_failure_returns_risk_envelope() -> None:
    """When sandbox execution fails, CreativeContentAgent returns risk envelope with 0.0 confidence."""
    failing_client = FakeSandboxClient(should_fail=True)
    agent = CreativeContentAgent(failing_client)

    grant = TaskGrant(
        task_id="task-fail-exec",
        worker_role=WorkerRole.CREATIVE_CONTENT,
        tenant_scope=TenantScope(tenant_id="t1"),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )

    context: dict[str, object] = {
        "claims_dossier": {"tenant_id": "t1", "claims": [{"validation_status": "SUPPORTED"}]},
        "strategy_plan": {"tenant_id": "t1", "channels": ["meta"]},
    }

    envelope = await agent.run(grant, context)

    assert envelope.confidence.point_estimate == 0.0
    assert len(envelope.unresolved_risks_or_assumptions) >= 1
    assert "simulated sandbox failure" in envelope.unresolved_risks_or_assumptions[0]


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
