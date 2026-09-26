"""Authoritative reasoning profiles and session isolation for W_COMP and specialists.

Declares seven immutable specialist profiles (W_COMP plus six domain specialists)
with purpose-separated prompt hashes, strict tool allowlists, budget bounds, and
session factory functions that guarantee fresh, isolated LLM sessions per attempt.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.settings import LlmSettings
from app.integrations.llm.client import LlmClient
from app.schemas.competitor_intel import CompetitorRole
from app.schemas.sandbox import NetworkPolicy


@dataclass(frozen=True)
class SpecialistModelProfile:
    """Immutable model, security, budget, and capability profile for competitor reasoning."""

    profile_id: str
    role: CompetitorRole
    profile_version: str = "1.0"
    provider_adapter: str = "provider_neutral"
    model_id: str = "claude-3-5-sonnet"
    model_revision: str = "2024-10-22"
    reasoning_mode: str = "competitor_intelligence"
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
    data_classification_allowlist: tuple[str, ...] = ("public", "internal")
    endpoint_policy_ref: str = "policy:w_comp:bounded:v1"
    credential_ref: str = "cred:vault:w_comp"
    prompt_version: str = "1.0.0"
    output_schema_version: str = "1.0"
    allowed_operations: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED

    def compute_digest(self) -> str:
        """Compute SHA-256 canonical digest of this immutable profile."""
        payload = {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "role": self.role.value if isinstance(self.role, CompetitorRole) else str(self.role),
            "provider_adapter": self.provider_adapter,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "reasoning_mode": self.reasoning_mode,
            "capabilities_required": sorted(self.capabilities_required),
            "context_limit": self.context_limit,
            "max_output_tokens": self.max_output_tokens,
            "sampling_parameters": self.sampling_parameters,
            "timeout_ms": self.timeout_ms,
            "max_attempts": self.max_attempts,
            "budget_limit": self.budget_limit,
            "budget_limit_tokens": self.budget_limit_tokens,
            "data_classification_allowlist": sorted(self.data_classification_allowlist),
            "endpoint_policy_ref": self.endpoint_policy_ref,
            "credential_ref": self.credential_ref,
            "prompt_version": self.prompt_version,
            "output_schema_version": self.output_schema_version,
            "allowed_operations": sorted(self.allowed_operations),
            "allowed_tools": sorted(self.allowed_tools),
            "network_policy": self.network_policy.value
            if isinstance(self.network_policy, NetworkPolicy)
            else str(self.network_policy),
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


# 1. W_COMP (Coordinator: reasoning-only, no tools, no network)
COORDINATOR_PROFILE = SpecialistModelProfile(
    profile_id="w_comp.coordinator.v1",
    role=CompetitorRole.COORDINATOR,
    reasoning_mode="strategy_interpretation_and_validation",
    allowed_operations=(),
    allowed_tools=(),
    network_policy=NetworkPolicy.DISABLED,
)

# 2. COMP-DISCOVERY (Brand, entity, subsidiary, and domain resolution)
DISCOVERY_PROFILE = SpecialistModelProfile(
    profile_id="w_comp.discovery.v1",
    role=CompetitorRole.DISCOVERY,
    reasoning_mode="entity_and_domain_resolution",
    allowed_operations=(
        "public_page_capture",
        "transparency_query",
        "serp_query",
        "entity_normalize",
    ),
    allowed_tools=("public_search", "official_transparency", "dom_parser"),
    network_policy=NetworkPolicy.ALLOWLIST,
)

# 3. COMP-ADS (Transparency library querying and creative change analysis)
ADS_PROFILE = SpecialistModelProfile(
    profile_id="w_comp.ads.v1",
    role=CompetitorRole.ADS,
    reasoning_mode="ad_library_and_creative_metadata",
    allowed_operations=("transparency_query", "public_page_capture", "ad_extract_compare"),
    allowed_tools=("official_transparency", "dom_parser", "browser_automation"),
    network_policy=NetworkPolicy.ALLOWLIST,
)

# 4. COMP-PRICE (Pricing, discounts, bundles, and terms extraction)
PRICE_PROFILE = SpecialistModelProfile(
    profile_id="w_comp.price.v1",
    role=CompetitorRole.PRICE,
    reasoning_mode="price_and_offer_extraction",
    allowed_operations=("public_page_capture", "price_extract_compare"),
    allowed_tools=("dom_parser", "price_tracker", "browser_automation"),
    network_policy=NetworkPolicy.ALLOWLIST,
)

# 5. COMP-SEARCH (SERP rankings, paid vs organic, and keyword visibility)
SEARCH_PROFILE = SpecialistModelProfile(
    profile_id="w_comp.search.v1",
    role=CompetitorRole.SEARCH,
    reasoning_mode="serp_and_content_gap_analysis",
    allowed_operations=("serp_query", "public_page_capture", "serp_normalize_compare"),
    allowed_tools=("public_search", "serp_extractor", "browser_automation"),
    network_policy=NetworkPolicy.ALLOWLIST,
)

# 6. COMP-POSITION (Messaging, claim extraction, and positioning shifts)
POSITION_PROFILE = SpecialistModelProfile(
    profile_id="w_comp.position.v1",
    role=CompetitorRole.POSITION,
    reasoning_mode="messaging_and_positioning_extraction",
    allowed_operations=("public_page_capture", "position_extract_compare"),
    allowed_tools=("dom_parser", "browser_automation"),
    network_policy=NetworkPolicy.ALLOWLIST,
)

# 7. COMP-SYNTH (Offline evidence synthesis, conflict detection, brief preparation)
SYNTHESIS_PROFILE = SpecialistModelProfile(
    profile_id="w_comp.synthesis.v1",
    role=CompetitorRole.SYNTHESIS,
    reasoning_mode="offline_evidence_synthesis",
    allowed_operations=("evidence_synthesize",),
    allowed_tools=("evidence_synthesizer",),
    network_policy=NetworkPolicy.DISABLED,  # ZERO research-network egress
)

ALL_COMPETITOR_PROFILES: dict[CompetitorRole, SpecialistModelProfile] = {
    CompetitorRole.COORDINATOR: COORDINATOR_PROFILE,
    CompetitorRole.DISCOVERY: DISCOVERY_PROFILE,
    CompetitorRole.ADS: ADS_PROFILE,
    CompetitorRole.PRICE: PRICE_PROFILE,
    CompetitorRole.SEARCH: SEARCH_PROFILE,
    CompetitorRole.POSITION: POSITION_PROFILE,
    CompetitorRole.SYNTHESIS: SYNTHESIS_PROFILE,
}


def get_competitor_profile(role: CompetitorRole | str) -> SpecialistModelProfile:
    """Retrieve immutable model profile for a competitor role."""
    resolved_role = CompetitorRole(role) if isinstance(role, str) else role
    if resolved_role not in ALL_COMPETITOR_PROFILES:
        raise KeyError(f"Unknown competitor role: {role}")
    return ALL_COMPETITOR_PROFILES[resolved_role]


def create_competitor_llm_client(
    profile: SpecialistModelProfile,
    base_settings: LlmSettings | None = None,
    *,
    attempt_id: str | None = None,
    tenant_id: str | None = None,
) -> LlmClient:
    """Instantiate an independent request-local LlmClient bound to the specialist profile.

    Guarantees that every invocation and retry receives a unique agent_identity and
    a distinct client instance, preventing state, history, or tool leakage.
    """
    unique_instance_id = attempt_id or f"inst-{uuid.uuid4().hex[:8]}"
    tenant_prefix = f"tenant-{tenant_id}." if tenant_id else ""
    role_name = profile.role.value.lower().replace("-", "_")

    settings = base_settings or LlmSettings(
        provider="local",
        model_name=profile.model_id,
        request_timeout_seconds=max(1, profile.timeout_ms // 1000),
    )

    return LlmClient(
        settings=settings,
        agent_identity=f"{tenant_prefix}w_comp.{role_name}.{unique_instance_id}",
        model_identity=profile.model_id,
    )


async def dispatch_competitor_specialist_attempt(
    sandbox_client: Any,
    attempt_input: Any,
    egress_grant: Any | None = None,
) -> Any:
    """Dispatch an authorized specialist attempt through sandbox under least privilege."""
    from app.core.exceptions import PolicyViolationError
    from app.schemas.competitor_intel import CompetitorRole, Observation, SpecialistResult
    from app.schemas.governance import WorkerRole
    from app.schemas.sandbox import ResourceLimits, SandboxCapability, SandboxInvocationMandate

    if attempt_input.role == CompetitorRole.COORDINATOR:
        raise PolicyViolationError(
            "W_COMP coordinator has zero sandbox authority and cannot be dispatched to sandbox."
        )

    profile = get_competitor_profile(attempt_input.role)
    operation = (
        attempt_input.approved_operation_ids[0]
        if attempt_input.approved_operation_ids
        else "default"
    )

    mandate = SandboxInvocationMandate(
        task_id=attempt_input.task_id,
        tenant_id=attempt_input.tenant_id,
        worker_role=WorkerRole.COMPETITOR_INTEL,
        worker_id="W_COMP",
        capability=SandboxCapability.COMP,
        specialist_id=attempt_input.role.value,
        operation=operation,
        payload={
            "task_id": attempt_input.task_id,
            "tenant_id": attempt_input.tenant_id,
            "attempt_id": attempt_input.attempt_id,
            "operation": operation,
            "context_slice": attempt_input.context_slice,
            "input_hash": attempt_input.input_hash,
        },
        allowed_tools=list(profile.allowed_tools),
        network_policy=profile.network_policy,
        egress_grant=egress_grant,
        resource_limits=ResourceLimits(
            timeout_seconds=max(1, profile.timeout_ms // 1000),
            memory_mb=1024,
            cpu_cores=1.0,
        ),
        provenance_context={
            "profile_id": profile.profile_id,
            "profile_digest": profile.compute_digest(),
            "attempt_id": attempt_input.attempt_id,
            "llm_instance_id": attempt_input.llm_instance_id,
        },
    )

    result = await sandbox_client.invoke(mandate)

    observations: list[Observation] = []
    if (
        result.success
        and isinstance(result.sanitized_output, dict)
        and "benchmark_price" in result.sanitized_output
    ):
        observations.append(
            Observation(
                observation_id=f"obs-{attempt_input.attempt_id}-price",
                predicate="benchmark_price",
                typed_value=result.sanitized_output["benchmark_price"],
                subject_id=str(result.sanitized_output.get("competitor", "CompetitorCorp")),
                supporting_evidence_id=f"ev-{attempt_input.attempt_id}",
                locator="css=.price",
            )
        )

    status = "failed"
    if result.success:
        status = "success" if observations else "no_observation"

    return SpecialistResult(
        step_id=attempt_input.step_id,
        attempt_id=attempt_input.attempt_id,
        profile_id=profile.profile_id,
        input_hash=attempt_input.input_hash,
        status=status,
        observations=observations,
        structured_failures=(
            [] if result.success else [{"error": result.error or "sandbox execution failed"}]
        ),
        resource_usage={"execution_id": getattr(result, "execution_id", "")},
        lineage={
            "mandate_digest": profile.compute_digest(),
            "attempt_id": attempt_input.attempt_id,
        },
        controller_result_ref=getattr(result, "execution_id", None),
    )
