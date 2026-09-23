"""Authoritative reasoning profiles and session isolation for W_VOICE and specialists.

Declares seven immutable specialist profiles (W_VOICE plus six domain specialists)
with purpose-separated prompt hashes, strict tool allowlists, budget bounds, and
session factory functions that guarantee fresh, isolated LLM sessions per attempt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any
import uuid

from app.core.settings import LlmSettings
from app.integrations.llm.client import LlmClient
from app.schemas.customer_voice import VoiceWorkflowStage
from app.schemas.sandbox import NetworkPolicy


@dataclass(frozen=True)
class SpecialistModelProfile:
    """Immutable model, security, budget, and capability profile for Customer Voice."""

    profile_id: str
    specialist_id: str
    role: VoiceWorkflowStage
    profile_version: str = "1.0"
    provider_adapter: str = "provider_neutral"
    model_id: str = "claude-3-5-sonnet"
    model_revision: str = "2024-10-22"
    reasoning_mode: str = "customer_voice_reasoning"
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
    endpoint_policy_ref: str = "policy:w_voice:bounded:v1"
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
            "network_policy": self.network_policy.value
            if isinstance(self.network_policy, NetworkPolicy)
            else str(self.network_policy),
            "output_schema_version": self.output_schema_version,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "prompt_version": self.prompt_version,
            "provider_adapter": self.provider_adapter,
            "reasoning_mode": self.reasoning_mode,
            "role": self.role.value if isinstance(self.role, VoiceWorkflowStage) else str(self.role),
            "sampling_parameters": self.sampling_parameters,
            "specialist_id": self.specialist_id,
            "timeout_ms": self.timeout_ms,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# 1. W_VOICE (Coordinator: Layer-5 zero-sandbox orchestration and sanitized synthesis)
COORDINATOR_PROFILE = SpecialistModelProfile(
    profile_id="w_voice.coordinator.v1",
    specialist_id="W_VOICE",
    role=VoiceWorkflowStage.SYNTHESIS,
    reasoning_mode="coordination_and_sanitized_synthesis",
    allowed_operations=("coordinate_workflow", "synthesize_envelope", "validate_scope"),
    allowed_tools=(),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 2. VOICE-DISCOVERY (Acquisition and preprocessing coordination; only specialist with network)
DISCOVERY_PROFILE = SpecialistModelProfile(
    profile_id="w_voice.discovery.v1",
    specialist_id="VOICE-DISCOVERY",
    role=VoiceWorkflowStage.DISCOVERY,
    reasoning_mode="source_acquisition_and_preprocessing",
    allowed_operations=("acquire_source", "de_identify", "deduplicate", "normalize_records"),
    allowed_tools=("dedupe_normalizer", "pii_redactor", "source_fetcher"),
    network_policy=NetworkPolicy.ALLOWLIST,
    data_classification_allowlist=("de_identified", "internal", "public"),
)

# 3. VOICE-THEMES (Thematic clustering, frequency, and observed share)
THEMES_PROFILE = SpecialistModelProfile(
    profile_id="w_voice.themes.v1",
    specialist_id="VOICE-THEMES",
    role=VoiceWorkflowStage.THEMES,
    reasoning_mode="thematic_clustering_and_frequency",
    allowed_operations=("cluster_embeddings", "compute_observed_share", "extract_topics"),
    allowed_tools=("embedding_clustering", "frequency_analyzer"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 4. VOICE-SENTIMENT (Aspect-level sentiment, emotion, and span grounding)
SENTIMENT_PROFILE = SpecialistModelProfile(
    profile_id="w_voice.sentiment.v1",
    specialist_id="VOICE-SENTIMENT",
    role=VoiceWorkflowStage.SENTIMENT,
    reasoning_mode="aspect_level_sentiment_and_emotion",
    allowed_operations=("detect_emotion", "ground_spans", "score_aspect_polarity"),
    allowed_tools=("absa_classifier", "span_grounder"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 5. VOICE-NEEDS (Needs, pains, and objections reasoning with customer vocabulary)
NEEDS_PROFILE = SpecialistModelProfile(
    profile_id="w_voice.needs.v1",
    specialist_id="VOICE-NEEDS",
    role=VoiceWorkflowStage.NEEDS,
    reasoning_mode="needs_pains_and_objections_reasoning",
    allowed_operations=("classify_objections", "extract_needs", "extract_vocabulary"),
    allowed_tools=("objection_extractor", "vocabulary_parser"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 6. VOICE-JOURNEY (Descriptive channel, touchpoint, and segment comparisons)
JOURNEY_PROFILE = SpecialistModelProfile(
    profile_id="w_voice.journey.v1",
    specialist_id="VOICE-JOURNEY",
    role=VoiceWorkflowStage.JOURNEY,
    reasoning_mode="descriptive_touchpoint_and_segment_comparison",
    allowed_operations=("aggregate_metrics", "compare_segments", "compare_touchpoints"),
    allowed_tools=("descriptive_aggregator", "journey_comparator"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

# 7. VOICE-QA (Independent quality, privacy, trace, bias, and coverage assurance)
QA_PROFILE = SpecialistModelProfile(
    profile_id="w_voice.qa.v1",
    specialist_id="VOICE-QA",
    role=VoiceWorkflowStage.QA,
    reasoning_mode="independent_quality_and_privacy_assurance",
    allowed_operations=("check_bias", "evaluate_privacy", "validate_schema", "verify_grounding"),
    allowed_tools=("hash_verifier", "privacy_auditor", "qa_validator"),
    network_policy=NetworkPolicy.DISABLED,
    data_classification_allowlist=("internal", "de_identified"),
)

ALL_VOICE_PROFILES: dict[str, SpecialistModelProfile] = {
    "W_VOICE": COORDINATOR_PROFILE,
    "VOICE-DISCOVERY": DISCOVERY_PROFILE,
    "VOICE-THEMES": THEMES_PROFILE,
    "VOICE-SENTIMENT": SENTIMENT_PROFILE,
    "VOICE-NEEDS": NEEDS_PROFILE,
    "VOICE-JOURNEY": JOURNEY_PROFILE,
    "VOICE-QA": QA_PROFILE,
}


def get_voice_profile(identity_or_stage: VoiceWorkflowStage | str) -> SpecialistModelProfile:
    """Retrieve immutable model profile for a Voice specialist identity or stage."""
    key = identity_or_stage.value if isinstance(identity_or_stage, VoiceWorkflowStage) else identity_or_stage
    if key not in ALL_VOICE_PROFILES:
        raise KeyError(f"Unknown Customer Voice specialist identity or stage: {identity_or_stage}")
    return ALL_VOICE_PROFILES[key]


def create_voice_llm_client(
    profile: SpecialistModelProfile,
    base_settings: LlmSettings | None = None,
    *,
    attempt_id: str | None = None,
    tenant_id: str | None = None,
) -> LlmClient:
    """Instantiate an independent request-local LlmClient bound to the specialist profile.

    Guarantees that every invocation receives a unique agent_identity and a distinct
    client instance, preventing cross-specialist or cross-tenant state leakage.
    Provider credentials remain in host settings and are never stored in profile state.
    """
    unique_instance_id = attempt_id or f"inst-{uuid.uuid4().hex[:8]}"
    tenant_prefix = f"tenant-{tenant_id}." if tenant_id else ""
    role_name = profile.specialist_id.lower().replace("-", "_")

    settings = base_settings or LlmSettings(
        provider="local",
        model_name=profile.model_id,
        request_timeout_seconds=max(1, profile.timeout_ms // 1000),
    )

    return LlmClient(
        settings=settings,
        agent_identity=f"{tenant_prefix}w_voice.{role_name}.{unique_instance_id}",
        model_identity=profile.model_id,
    )


async def dispatch_voice_specialist_attempt(
    sandbox_client: Any,
    specialist_id: str,
    tenant_id: str,
    task_id: str,
    step_id: str,
    operation: str,
    payload: dict[str, Any],
    *,
    egress_grant: Any = None,
    attempt_id: str | None = None,
) -> Any:
    """Execute a specialist attempt with fresh SandboxIdentity and ephemeral lifecycle.

    Enforces:
    1. Zero-sandbox coordinator: W_VOICE cannot invoke sandbox.
    2. Specialist authorization: Only the 6 authorized VOICE-* specialists.
    3. Ephemeral fresh runtime per attempt: SandboxIdentity -> Mandate -> Invoke -> Teardown.
    """
    from app.core.exceptions import SandboxInvocationError
    from app.schemas.governance import WorkerRole
    from app.schemas.sandbox import (
        NetworkPolicy as SandboxNetPolicy,
        ResourceLimits,
        SandboxCapability,
        SandboxIdentity,
        SandboxInvocationMandate,
    )

    if specialist_id in ("W_VOICE", "NONE", ""):
        raise SandboxInvocationError(
            "W_VOICE coordinator has zero sandbox authority; execution requires an authorized Voice specialist_id."
        )

    profile = get_voice_profile(specialist_id)
    attempt = attempt_id or f"att-{uuid.uuid4().hex[:8]}"

    identity = SandboxIdentity.generate(
        tenant_id=tenant_id,
        task_id=task_id,
        step_id=step_id,
        attempt_id=attempt,
        engine_id="W_VOICE",
        specialist_id=specialist_id,
    )

    req_network = (
        SandboxNetPolicy.ALLOWLIST
        if profile.network_policy == NetworkPolicy.ALLOWLIST
        else SandboxNetPolicy.DISABLED
    )

    mandate = SandboxInvocationMandate(
        task_id=task_id,
        stage_attempt_id=attempt,
        worker_role=WorkerRole.CUSTOMER_VOICE,
        worker_id=specialist_id,
        tenant_id=tenant_id,
        capability=SandboxCapability.PARSE,
        specialist_id=specialist_id,
        specialist_agent=specialist_id,
        operation=operation,
        payload=payload,
        allowed_tools=list(profile.allowed_tools),
        network_policy=req_network,
        egress_grant=egress_grant,
        resource_limits=ResourceLimits(timeout_seconds=max(1, profile.timeout_ms // 1000)),
    )

    return await sandbox_client.invoke(mandate)

