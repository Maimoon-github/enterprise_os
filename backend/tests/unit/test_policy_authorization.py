"""Verifies policy decisions and monotonic attenuation."""

from __future__ import annotations

import pytest

from app.core.exceptions import AuthorizationError
from app.orchestration.policy_evaluator import PolicyEvaluator
from app.schemas.governance import Directive, RiskLevel, TenantScope
from app.schemas.task_state import CanonicalTaskState
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity


def test_delegation_within_scope_and_risk_is_allowed(sample_directive: Directive) -> None:
    evaluator = PolicyEvaluator()

    decision = evaluator.evaluate_delegation(
        sample_directive, sample_directive.scope, RiskLevel.LOW
    )

    assert decision.allowed is True


def test_delegation_exceeding_risk_ceiling_is_denied(sample_directive: Directive) -> None:
    evaluator = PolicyEvaluator()

    decision = evaluator.evaluate_delegation(
        sample_directive, sample_directive.scope, RiskLevel.CRITICAL
    )

    assert decision.allowed is False
    assert "exceeds" in decision.reason


def test_delegation_outside_scope_is_denied(sample_directive: Directive) -> None:
    evaluator = PolicyEvaluator()
    broader_scope = TenantScope(
        tenant_id=sample_directive.tenant_id,
        brand_ids=[*sample_directive.scope.brand_ids, "unauthorized-brand"],
        allowed_channels=sample_directive.scope.allowed_channels,
    )

    decision = evaluator.evaluate_delegation(sample_directive, broader_scope, RiskLevel.LOW)

    assert decision.allowed is False
    assert "scope" in decision.reason.lower()


def test_risk_level_rank_is_monotonic() -> None:
    assert RiskLevel.LOW.rank < RiskLevel.MEDIUM.rank
    assert RiskLevel.MEDIUM.rank < RiskLevel.HIGH.rank
    assert RiskLevel.HIGH.rank < RiskLevel.CRITICAL.rank
    assert RiskLevel.HIGH.exceeds(RiskLevel.MEDIUM)
    assert not RiskLevel.MEDIUM.exceeds(RiskLevel.HIGH)


def test_authorization_boundary_allows_caller_within_delegation(
    sample_tenant_scope: TenantScope,
) -> None:
    boundary = AuthorizationBoundary()
    caller = CallerIdentity(
        subject="ie", tenant_scope=sample_tenant_scope, risk_ceiling=RiskLevel.HIGH
    )

    boundary.authorize(caller, requested_scope=sample_tenant_scope, requested_risk=RiskLevel.LOW)


def test_authorization_boundary_rejects_risk_above_ceiling(
    sample_tenant_scope: TenantScope,
) -> None:
    boundary = AuthorizationBoundary()
    caller = CallerIdentity(
        subject="ie", tenant_scope=sample_tenant_scope, risk_ceiling=RiskLevel.LOW
    )

    with pytest.raises(AuthorizationError):
        boundary.authorize(
            caller, requested_scope=sample_tenant_scope, requested_risk=RiskLevel.HIGH
        )


def test_authorization_boundary_rejects_scope_outside_delegation(
    sample_tenant_scope: TenantScope,
) -> None:
    boundary = AuthorizationBoundary()
    caller = CallerIdentity(
        subject="ie", tenant_scope=sample_tenant_scope, risk_ceiling=RiskLevel.HIGH
    )
    other_tenant_scope = TenantScope(tenant_id="other-tenant")

    with pytest.raises(AuthorizationError):
        boundary.authorize(
            caller, requested_scope=other_tenant_scope, requested_risk=RiskLevel.LOW
        )


def test_autonomy_tier_monotonic_attenuation() -> None:
    from app.schemas.governance import AutonomyTier

    assert AutonomyTier.TIER_0_INFORMATIONAL.rank < AutonomyTier.TIER_1_ASSISTED.rank
    assert AutonomyTier.TIER_1_ASSISTED.rank < AutonomyTier.TIER_2_AUTONOMOUS.rank
    assert AutonomyTier.TIER_2_AUTONOMOUS.rank < AutonomyTier.TIER_3_HIGH_RISK_GATED.rank
    assert AutonomyTier.TIER_3_HIGH_RISK_GATED.exceeds(AutonomyTier.TIER_2_AUTONOMOUS)
    assert not AutonomyTier.TIER_1_ASSISTED.exceeds(AutonomyTier.TIER_2_AUTONOMOUS)


def test_authorization_boundary_enforces_autonomy_tier(sample_tenant_scope: TenantScope) -> None:
    from app.schemas.governance import AutonomyTier

    boundary = AuthorizationBoundary()
    caller = CallerIdentity(
        subject="worker-1",
        tenant_scope=sample_tenant_scope,
        risk_ceiling=RiskLevel.MEDIUM,
        autonomy_tier=AutonomyTier.TIER_1_ASSISTED,
    )

    # Within autonomy tier
    boundary.authorize(
        caller,
        requested_scope=sample_tenant_scope,
        requested_risk=RiskLevel.LOW,
        requested_autonomy=AutonomyTier.TIER_1_ASSISTED,
    )

    # Exceeds autonomy tier
    with pytest.raises(AuthorizationError) as exc_info:
        boundary.authorize(
            caller,
            requested_scope=sample_tenant_scope,
            requested_risk=RiskLevel.LOW,
            requested_autonomy=AutonomyTier.TIER_2_AUTONOMOUS,
        )
    assert "autonomy tier" in str(exc_info.value).lower()


def test_authorization_boundary_enforces_capabilities(sample_tenant_scope: TenantScope) -> None:
    boundary = AuthorizationBoundary()
    caller = CallerIdentity(
        subject="worker-scrape",
        tenant_scope=sample_tenant_scope,
        risk_ceiling=RiskLevel.MEDIUM,
        allowed_capabilities=frozenset({"S_SCRAPE", "S_PARSE"}),
    )

    # Permitted capability
    boundary.authorize(
        caller,
        requested_scope=sample_tenant_scope,
        requested_risk=RiskLevel.LOW,
        requested_capability="S_SCRAPE",
    )

    # Denied capability
    with pytest.raises(AuthorizationError) as exc_info:
        boundary.authorize(
            caller,
            requested_scope=sample_tenant_scope,
            requested_risk=RiskLevel.LOW,
            requested_capability="S_CODE",
        )
    assert "lacks capability" in str(exc_info.value).lower()


def test_authorization_boundary_enforces_delegation_chain(sample_tenant_scope: TenantScope) -> None:
    boundary = AuthorizationBoundary()
    caller = CallerIdentity(
        subject="worker-sub",
        tenant_scope=sample_tenant_scope,
        risk_ceiling=RiskLevel.MEDIUM,
        delegation_chain=("root", "portfolio-owner", "ie", "worker-sub"),
    )

    # Valid delegation parent
    boundary.authorize(
        caller,
        requested_scope=sample_tenant_scope,
        requested_risk=RiskLevel.LOW,
        delegation_parent="ie",
    )

    # Invalid delegation parent
    with pytest.raises(AuthorizationError) as exc_info:
        boundary.authorize(
            caller,
            requested_scope=sample_tenant_scope,
            requested_risk=RiskLevel.LOW,
            delegation_parent="unauthorized-agent",
        )
    assert "delegation parent" in str(exc_info.value).lower()


def test_authorization_boundary_verifies_cryptographic_signatures(sample_tenant_scope: TenantScope) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from app.security.cryptographic_validator import CryptographicValidator, sign_payload

    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    validator = CryptographicValidator(public_key_pem=public_pem)
    boundary = AuthorizationBoundary(crypto_validator=validator)

    payload = b"grant-task-12345"
    valid_sig = sign_payload(payload, private_key)

    caller = CallerIdentity(
        subject="ie",
        tenant_scope=sample_tenant_scope,
        risk_ceiling=RiskLevel.HIGH,
        signature=valid_sig,
    )

    # Valid signature
    boundary.authorize(
        caller,
        requested_scope=sample_tenant_scope,
        requested_risk=RiskLevel.LOW,
        verification_payload=payload,
    )

    # Tampered payload fails
    with pytest.raises(AuthorizationError):
        boundary.authorize(
            caller,
            requested_scope=sample_tenant_scope,
            requested_risk=RiskLevel.LOW,
            verification_payload=b"tampered-payload",
        )


def test_versioned_policy_envelope_and_evaluation(sample_directive: Directive) -> None:
    from app.schemas.governance import AutonomyTier
    from app.services.policy_engine import PolicyEngine

    engine = PolicyEngine()
    directive = sample_directive.model_copy(
        update={
            "permitted_claims": ["Clinically backed", "Organic ingredients"],
            "prohibited_actions": ["direct_db_write", "bypass_pab"],
            "autonomy_limit": AutonomyTier.TIER_2_AUTONOMOUS,
        }
    )

    versioned = engine.build_versioned_envelope(directive, directive.scope, version="1.0.0")
    assert versioned.version == "1.0.0"
    assert engine.get_envelope(directive.tenant_id, "1.0.0") is not None

    evaluator = PolicyEvaluator(policy_engine=engine)

    # Prohibited action is rejected
    decision = evaluator.evaluate_delegation(
        directive, directive.scope, RiskLevel.LOW, requested_action="direct_db_write"
    )
    assert decision.allowed is False
    assert "prohibited" in decision.reason

    # Non-permitted claim is rejected
    decision = evaluator.evaluate_delegation(
        directive, directive.scope, RiskLevel.LOW, requested_claim="Cures all diseases"
    )
    assert decision.allowed is False
    assert "not permitted" in decision.reason

    # Permitted claim is allowed
    decision = evaluator.evaluate_delegation(
        directive, directive.scope, RiskLevel.LOW, requested_claim="Clinically backed formula"
    )
    assert decision.allowed is True
    assert decision.decision == "allow"
    assert decision.reason_code == "ALLOW"
    assert decision.policy_id is not None
    assert decision.policy_hash is not None


def test_policy_decision_review_flow(sample_directive: Directive) -> None:
    evaluator = PolicyEvaluator()
    decision = evaluator.evaluate_delegation(
        sample_directive, sample_directive.scope, RiskLevel.LOW, requires_review=True
    )
    assert decision.allowed is False
    assert decision.decision == "review"
    assert decision.reason_code == "REVIEW_REQUIRED"


def test_immutable_policy_envelope_registration(sample_directive: Directive) -> None:
    from app.core.exceptions import PolicyViolationError
    from app.services.policy_engine import PolicyEngine

    engine = PolicyEngine()
    env1 = engine.build_versioned_envelope(sample_directive, sample_directive.scope, version="1.0.0")
    # Idempotent re-registration of identical envelope is allowed
    engine.register_envelope(env1)

    # Mutation of existing versioned envelope is strictly rejected
    tampered_env = env1.model_copy(update={"spending_limit": 999999.0})
    with pytest.raises(PolicyViolationError) as exc_info:
        engine.register_envelope(tampered_env)
    assert "immutable" in str(exc_info.value).lower()


def test_directive_tenant_consistency(sample_tenant_scope: TenantScope) -> None:
    # Matching tenant passes
    d1 = Directive(
        directive_id="d-1",
        tenant_id="acme",
        objective="Valid",
        budget_cap=100.0,
        scope=TenantScope(tenant_id="acme"),
    )
    assert d1.validate_tenant_consistency() is True

    # Mismatched tenant fails
    d2 = Directive(
        directive_id="d-2",
        tenant_id="acme",
        objective="Invalid",
        budget_cap=100.0,
        scope=TenantScope(tenant_id="other"),
    )
    assert d2.validate_tenant_consistency() is False


@pytest.mark.asyncio
async def test_operational_directive_immutability(sample_directive: Directive) -> None:
    from app.core.exceptions import PolicyViolationError
    from app.persistence.repositories.operational import OperationalRepository

    class FakeSession:
        def __init__(self, store: dict) -> None:
            self._store = store

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def scalar(self, stmt):
            return "found" if sample_directive.directive_id in self._store else None

        async def execute(self, stmt):
            class Row:
                def __init__(self, doc):
                    self._doc = doc

                def scalar_one_or_none(self):
                    return self._doc

            return Row(self._store.get(sample_directive.directive_id))

        async def commit(self):
            pass

    store: dict = {}

    def session_factory():
        return FakeSession(store)

    repo = OperationalRepository(session_factory)  # type: ignore[arg-type]
    store[sample_directive.directive_id] = sample_directive.model_dump(mode="json")

    # Saving same data is idempotent
    await repo.save_directive(sample_directive)

    # Overwriting with altered directive is rejected
    altered = sample_directive.model_copy(update={"budget_cap": 99999.0})
    with pytest.raises(PolicyViolationError) as exc_info:
        await repo.save_directive(altered)
    assert "immutable" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_atomic_budget_reservation_and_commitment(sample_task: CanonicalTaskState) -> None:
    from app.services.task_state import TaskStateService

    class FakeTaskRepo:
        def __init__(self, task: CanonicalTaskState) -> None:
            self.task = task

        async def require(self, task_id: str) -> CanonicalTaskState:
            return self.task

        async def save_state(self, tenant_id: str, state: CanonicalTaskState) -> None:
            self.task = state

    repo = FakeTaskRepo(sample_task)
    service = TaskStateService(repo)

    # 1. Successful reservation within cap
    assert await service.reserve_budget("acme", sample_task.task_id, 300.0, 500.0) is True
    assert repo.task.cts_state["reserved_budget"] == 300.0

    # 2. Exceeding cap rejected
    assert await service.reserve_budget("acme", sample_task.task_id, 250.0, 500.0) is False
    assert repo.task.cts_state["reserved_budget"] == 300.0

    # 3. Successful commitment
    assert await service.commit_budget("acme", sample_task.task_id, 200.0) is True
    assert repo.task.cts_state["reserved_budget"] == 100.0
    assert repo.task.cts_state["committed_budget"] == 200.0