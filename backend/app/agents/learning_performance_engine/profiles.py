"""Authoritative reasoning profiles, identity isolation, and session factories for W_LEARN and specialists."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any
import uuid

from app.core.exceptions import SandboxInvocationError
from app.core.settings import LlmSettings
from app.integrations.llm.client import LlmClient
from app.schemas.learning_performance import LearningWorkflowStage
from app.schemas.sandbox import NetworkPolicy


@dataclass(frozen=True)
class SpecialistModelProfile:
    """Immutable model, security, budget, and capability profile for Learning & Performance."""

    profile_id: str
    specialist_id: str
    role: LearningWorkflowStage
    profile_version: str = "1.0"
    provider_adapter: str = "provider_neutral"
    model_id: str = "claude-3-5-sonnet"
    model_revision: str = "2024-10-22"
    reasoning_mode: str = "learning_measurement_reasoning"
    capabilities_required: tuple[str, ...] = ("text",)
    context_limit: int = 64000
    max_output_tokens: int = 4096
    sampling_parameters: dict[str, Any] = field(
        default_factory=lambda: {"temperature": 0.0, "seed": 42}
    )
    timeout_ms: int = 45000
    max_attempts: int = 3
    budget_limit: float = 3.0
    budget_limit_tokens: int = 8000
    data_classification_allowlist: tuple[str, ...] = ("internal", "de_identified")
    endpoint_policy_ref: str = "policy:w_learn:bounded:v1"
    fallback_profile_ids: tuple[str, ...] = ()
    prompt_version: str = "1.0.0"
    output_schema_version: str = "1.0"
    allowed_operations: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED

    def compute_digest(self) -> str:
        """Compute SHA-256 canonical digest of this immutable profile."""
        payload = {
            "allowed_operations": sorted(self.allowed_operations),
            "allowed_tools": sorted(self.allowed_tools),
            "budget_limit": self.budget_limit,
            "budget_limit_tokens": self.budget_limit_tokens,
            "capabilities_required": sorted(self.capabilities_required),
            "context_limit": self.context_limit,
            "data_classification_allowlist": sorted(self.data_classification_allowlist),
            "endpoint_policy_ref": self.endpoint_policy_ref,
            "fallback_profile_ids": sorted(self.fallback_profile_ids),
            "max_attempts": self.max_attempts,
            "max_output_tokens": self.max_output_tokens,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "network_policy": (
                self.network_policy.value
                if isinstance(self.network_policy, NetworkPolicy)
                else str(self.network_policy)
            ),
            "output_schema_version": self.output_schema_version,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "prompt_version": self.prompt_version,
            "provider_adapter": self.provider_adapter,
            "reasoning_mode": self.reasoning_mode,
            "role": self.role.value if isinstance(self.role, LearningWorkflowStage) else str(self.role),
            "sampling_parameters": self.sampling_parameters,
            "specialist_id": self.specialist_id,
            "timeout_ms": self.timeout_ms,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# 1. W_LEARN (Coordinator: Layer-5 zero-sandbox synthesis and delta formulation)
PARENT_PROFILE = SpecialistModelProfile(
    profile_id="learn.parent.v1",
    specialist_id="W_LEARN",
    role=LearningWorkflowStage.SYNTHESIS,
    reasoning_mode="evidence_synthesis_and_learning_delta_proposal",
    allowed_operations=("synthesize_learning_delta", "summarize_evidence", "validate_qa_bundle"),
    allowed_tools=(),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 2. LEARN-TELEMETRY (Specialist: validation and dataset normalization)
TELEMETRY_PROFILE = SpecialistModelProfile(
    profile_id="learn.telemetry.v1",
    specialist_id="LEARN-TELEMETRY",
    role=LearningWorkflowStage.TELEMETRY,
    reasoning_mode="telemetry_integrity_and_normalization",
    allowed_operations=("validate_telemetry", "normalize_telemetry", "summarize_quality"),
    allowed_tools=("telemetry_validator", "dataset_normalizer"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 3. LEARN-ATTRIBUTION (Specialist: observational attribution, MMM, ROAS)
ATTRIBUTION_PROFILE = SpecialistModelProfile(
    profile_id="learn.attribution.v1",
    specialist_id="LEARN-ATTRIBUTION",
    role=LearningWorkflowStage.ATTRIBUTION,
    reasoning_mode="observational_attribution_and_roas_modeling",
    allowed_operations=("estimate_attribution", "fit_mmm", "calculate_roas"),
    allowed_tools=("attribution_engine", "mmm_fitter", "roas_calculator"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 4. LEARN-INCREMENTALITY (Specialist: experiment validation, ITT lift, calibration)
INCREMENTALITY_PROFILE = SpecialistModelProfile(
    profile_id="learn.incrementality.v1",
    specialist_id="LEARN-INCREMENTALITY",
    role=LearningWorkflowStage.INCREMENTALITY,
    reasoning_mode="experimental_design_and_causal_lift_evaluation",
    allowed_operations=("validate_experiment", "estimate_lift", "propose_calibration"),
    allowed_tools=("experiment_validator", "itt_lift_estimator", "calibration_builder"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 5. LEARN-FATIGUE (Specialist: wearout and audience saturation analysis)
FATIGUE_PROFILE = SpecialistModelProfile(
    profile_id="learn.fatigue.v1",
    specialist_id="LEARN-FATIGUE",
    role=LearningWorkflowStage.FATIGUE,
    reasoning_mode="creative_wearout_and_saturation_diagnostics",
    allowed_operations=("analyze_wearout", "analyze_saturation"),
    allowed_tools=("wearout_analyzer", "saturation_modeler"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 6. LEARN-DECAY (Specialist: adstock, Hill response, half-life parameter estimation)
DECAY_PROFILE = SpecialistModelProfile(
    profile_id="learn.decay.v1",
    specialist_id="LEARN-DECAY",
    role=LearningWorkflowStage.DECAY,
    reasoning_mode="lag_kernel_fitting_and_half_life_estimation",
    allowed_operations=("estimate_adstock", "estimate_half_life", "diagnose_decay"),
    allowed_tools=("adstock_kernel", "half_life_estimator"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 7. LEARN-QA (Specialist: independent quality gating and reconciliation)
QUALITY_PROFILE = SpecialistModelProfile(
    profile_id="learn.quality.v1",
    specialist_id="LEARN-QA",
    role=LearningWorkflowStage.QA,
    reasoning_mode="evidence_bundle_critique_and_quality_sealing",
    allowed_operations=("validate_learning_bundle", "reconcile_estimates", "verify_provenance"),
    allowed_tools=("qa_bundle_verifier", "claim_reconciler"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)


LEARNING_PROFILES: dict[str, SpecialistModelProfile] = {
    PARENT_PROFILE.specialist_id: PARENT_PROFILE,
    PARENT_PROFILE.profile_id: PARENT_PROFILE,
    TELEMETRY_PROFILE.specialist_id: TELEMETRY_PROFILE,
    TELEMETRY_PROFILE.profile_id: TELEMETRY_PROFILE,
    ATTRIBUTION_PROFILE.specialist_id: ATTRIBUTION_PROFILE,
    ATTRIBUTION_PROFILE.profile_id: ATTRIBUTION_PROFILE,
    INCREMENTALITY_PROFILE.specialist_id: INCREMENTALITY_PROFILE,
    INCREMENTALITY_PROFILE.profile_id: INCREMENTALITY_PROFILE,
    FATIGUE_PROFILE.specialist_id: FATIGUE_PROFILE,
    FATIGUE_PROFILE.profile_id: FATIGUE_PROFILE,
    DECAY_PROFILE.specialist_id: DECAY_PROFILE,
    DECAY_PROFILE.profile_id: DECAY_PROFILE,
    QUALITY_PROFILE.specialist_id: QUALITY_PROFILE,
    QUALITY_PROFILE.profile_id: QUALITY_PROFILE,
}


def get_learning_profile(principal_or_id: str) -> SpecialistModelProfile:
    """Retrieve an immutable specialist profile fail-closed."""
    profile = LEARNING_PROFILES.get(principal_or_id)
    if profile is None:
        raise KeyError(
            f"Unauthorized or unknown Learning principal/profile identifier: '{principal_or_id}'."
        )
    return profile


@dataclass(frozen=True)
class LearningIdentityRecord:
    """Auditable runtime identity record binding specialist, session, and LLM context."""

    principal: str
    profile_id: str
    profile_version: str
    profile_digest: str
    client_instance_id: str
    session_id: str
    context_id: str
    request_id: str
    attempt_id: str
    provider: str
    model_id: str
    model_revision: str | None = None


def create_learning_llm_client(
    profile: SpecialistModelProfile,
    *,
    base_settings: LlmSettings | None = None,
    tenant_id: str | None = None,
    attempt_id: str | None = None,
    session_id: str | None = None,
    context_id: str | None = None,
    request_id: str | None = None,
) -> tuple[LlmClient, LearningIdentityRecord]:
    """Instantiate a fresh, isolated LlmClient bound to the specialist profile.

    Guarantees that every attempt/invocation receives a distinct client instance,
    unique agent_identity, and isolated context, preventing cross-specialist or
    cross-tenant state leakage.
    """
    attempt = attempt_id or f"att-{uuid.uuid4().hex[:8]}"
    session = session_id or f"sess-{uuid.uuid4().hex[:8]}"
    ctx = context_id or f"ctx-{uuid.uuid4().hex[:8]}"
    req = request_id or f"req-{uuid.uuid4().hex[:8]}"
    client_inst = f"client-{uuid.uuid4().hex[:8]}"

    tenant_prefix = f"tenant-{tenant_id}." if tenant_id else ""
    role_name = profile.specialist_id.lower().replace("-", "_")

    settings = base_settings or LlmSettings(
        provider="local",
        model_name=profile.model_id,
        request_timeout_seconds=max(1, profile.timeout_ms // 1000),
    )

    client = LlmClient(
        settings=settings,
        agent_identity=f"{tenant_prefix}w_learn.{role_name}.{client_inst}",
        model_identity=profile.model_id,
    )

    identity_record = LearningIdentityRecord(
        principal=profile.specialist_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        profile_digest=profile.compute_digest(),
        client_instance_id=client_inst,
        session_id=session,
        context_id=ctx,
        request_id=req,
        attempt_id=attempt,
        provider=settings.provider,
        model_id=profile.model_id,
        model_revision=profile.model_revision,
    )

    return client, identity_record


async def dispatch_learning_specialist_attempt(
    sandbox_client: Any,
    specialist_id: str,
    tenant_id: str,
    task_id: str,
    step_id: str,
    operation: str,
    payload: dict[str, Any],
    *,
    attempt_id: str | None = None,
) -> Any:
    """Execute a specialist attempt with fresh SandboxIdentity and ephemeral lifecycle.

    Enforces:
    1. Zero-sandbox coordinator: W_LEARN cannot invoke sandbox.
    2. Specialist authorization: Only the 6 authorized LEARN-* specialists.
    3. Ephemeral fresh runtime per attempt: SandboxIdentity -> Mandate -> Invoke -> Teardown.
    """
    if specialist_id in ("W_LEARN", "NONE", ""):
        raise SandboxInvocationError(
            "W_LEARN coordinator has zero sandbox authority; execution requires an authorized Learning specialist_id."
        )

    profile = get_learning_profile(specialist_id)
    if operation not in profile.allowed_operations:
        raise SandboxInvocationError(
            f"Operation '{operation}' is not permitted for specialist '{specialist_id}'. Allowed: {profile.allowed_operations}"
        )

    from app.schemas.governance import WorkerRole
    from app.schemas.sandbox import (
        NetworkPolicy as SandboxNetPolicy,
        ResourceLimits,
        SandboxCapability,
        SandboxIdentity,
        SandboxInvocationMandate,
    )

    attempt = attempt_id or f"att-{uuid.uuid4().hex[:8]}"

    identity = SandboxIdentity.generate(
        tenant_id=tenant_id,
        task_id=task_id,
        step_id=step_id,
        attempt_id=attempt,
        engine_id="W_LEARN",
        specialist_id=specialist_id,
    )

    mandate = SandboxInvocationMandate(
        task_id=task_id,
        stage_attempt_id=attempt,
        worker_role=WorkerRole.LEARNING_PERFORMANCE,
        worker_id=specialist_id,
        tenant_id=tenant_id,
        capability=SandboxCapability.ATTR,
        specialist_id=specialist_id,
        specialist_agent=specialist_id,
        operation=operation,
        payload=payload,
        allowed_tools=list(profile.allowed_tools),
        network_policy=SandboxNetPolicy.DISABLED,
        resource_limits=ResourceLimits(timeout_seconds=max(1, profile.timeout_ms // 1000)),
    )

    return await sandbox_client.invoke(mandate)
