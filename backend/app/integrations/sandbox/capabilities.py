"""Authoritative capability registry and allowlisting for the sandbox boundary.

Enforces least-privilege capability mapping:
W_DEV   -> S_CODE
W_STRAT -> S_ALLOC
W_CREAT -> S_COPY
W_PROD  -> S_VAL
W_COMP  -> S_SCRAPE
W_VOICE -> S_PARSE
W_LEARN -> S_ATTR

Validates worker role, operation name, and network policy fail-closed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import SandboxInvocationError
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import NetworkPolicy, SandboxCapability


@dataclass(frozen=True)
class CapabilityProfile:
    """Security and capability specification for a specialist sub-agent."""

    capability: SandboxCapability
    specialist_name: str
    allowed_worker: WorkerRole
    allowed_operations: tuple[str, ...]
    network_policy: NetworkPolicy
    default_timeout_seconds: int
    allowed_tools: tuple[str, ...]


CAPABILITY_REGISTRY: dict[SandboxCapability, CapabilityProfile] = {
    SandboxCapability.CODE: CapabilityProfile(
        capability=SandboxCapability.CODE,
        specialist_name="Component Coder & Linter",
        allowed_worker=WorkerRole.DEVELOPMENT,
        allowed_operations=("parse_ast", "lint", "generate_diff", "execute_code", "validate_syntax", "default"),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=("ast_parser", "code_linter", "diff_generator"),
    ),
    SandboxCapability.ALLOC: CapabilityProfile(
        capability=SandboxCapability.ALLOC,
        specialist_name="Media & Budget Allocator",
        allowed_worker=WorkerRole.STRATEGY,
        allowed_operations=("optimize_budget", "simulate_scenarios", "calculate_roas", "default"),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=("allocation_solver", "diminishing_returns_model"),
    ),
    SandboxCapability.COPY: CapabilityProfile(
        capability=SandboxCapability.COPY,
        specialist_name="Copy Drafter & Hook Critic",
        allowed_worker=WorkerRole.CREATIVE_CONTENT,
        allowed_operations=("generate_variants", "score_hooks", "format_validation", "default"),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=("variant_generator", "hook_critic"),
    ),
    SandboxCapability.VAL: CapabilityProfile(
        capability=SandboxCapability.VAL,
        specialist_name="Claim & Schema Validator",
        allowed_worker=WorkerRole.PRODUCT_EVIDENCE,
        allowed_operations=("validate_claim", "lint_compliance", "check_schema", "default"),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=("compliance_linter", "claim_checker"),
    ),
    SandboxCapability.SCRAPE: CapabilityProfile(
        capability=SandboxCapability.SCRAPE,
        specialist_name="Price & Ad Scraper",
        allowed_worker=WorkerRole.COMPETITOR_INTEL,
        allowed_operations=("scrape_prices", "parse_dom", "track_ads", "default"),
        network_policy=NetworkPolicy.CONTROLLED,
        default_timeout_seconds=180,
        allowed_tools=("dom_parser", "price_tracker", "browser_automation"),
    ),
    SandboxCapability.PARSE: CapabilityProfile(
        capability=SandboxCapability.PARSE,
        specialist_name="Sentiment & Review Parser",
        allowed_worker=WorkerRole.CUSTOMER_VOICE,
        allowed_operations=("parse_sentiment", "cluster_objections", "extract_feedback", "default"),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=("nlp_classifier", "sentiment_analyzer"),
    ),
    SandboxCapability.ATTR: CapabilityProfile(
        capability=SandboxCapability.ATTR,
        specialist_name="Attribution Modeler",
        allowed_worker=WorkerRole.LEARNING_PERFORMANCE,
        allowed_operations=("calculate_attribution", "score_decay", "fatigue_scoring", "default"),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=("attribution_engine", "decay_scorer"),
    ),
}

WORKER_CAPABILITY_MAP: dict[WorkerRole, SandboxCapability] = {
    profile.allowed_worker: profile.capability for profile in CAPABILITY_REGISTRY.values()
}


def get_capability_for_role(role: WorkerRole) -> SandboxCapability:
    """Return the single sandbox capability authorized for ``role``."""
    if role not in WORKER_CAPABILITY_MAP:
        raise SandboxInvocationError(f"No sandbox capability authorized for worker role: {role}")
    return WORKER_CAPABILITY_MAP[role]


def validate_capability_access(
    capability: SandboxCapability | str,
    worker_role: WorkerRole | str | None = None,
    operation: str = "default",
    *,
    requested_network: NetworkPolicy | str = NetworkPolicy.DISABLED,
) -> CapabilityProfile:
    """Validate that a requested sandbox execution adheres to capability allowlisting.

    Enforces least privilege:
    1. Capability must be a registered SandboxCapability.
    2. If worker_role is provided, it must match the capability's authorized worker.
    3. Operation must be in the profile's allowed_operations.
    4. Requested network access must not exceed the capability's allowed network policy.

    Raises SandboxInvocationError on any policy breach (fail-closed).
    """
    if isinstance(capability, str):
        try:
            capability = SandboxCapability(capability)
        except ValueError:
            raise SandboxInvocationError(f"Unknown sandbox capability: {capability}")

    if capability not in CAPABILITY_REGISTRY:
        raise SandboxInvocationError(f"Unauthorized or unregistered sandbox capability: {capability}")

    profile = CAPABILITY_REGISTRY[capability]

    if worker_role is not None:
        if isinstance(worker_role, str):
            try:
                worker_role = WorkerRole(worker_role)
            except ValueError:
                raise SandboxInvocationError(f"Unknown worker role: {worker_role}")

        if worker_role != profile.allowed_worker:
            raise SandboxInvocationError(
                f"Capability access denied: worker '{worker_role.value}' is not authorized to request "
                f"'{capability.value}' (authorized worker is '{profile.allowed_worker.value}')."
            )

    if operation not in profile.allowed_operations:
        raise SandboxInvocationError(
            f"Operation '{operation}' is not permitted for capability '{capability.value}'. "
            f"Permitted operations: {profile.allowed_operations}"
        )

    # Validate network egress permissions
    if isinstance(requested_network, str):
        requested_network = NetworkPolicy(requested_network)

    if requested_network != NetworkPolicy.DISABLED and profile.network_policy == NetworkPolicy.DISABLED:
        raise SandboxInvocationError(
            f"Network access policy violation: capability '{capability.value}' does not permit "
            f"network access (requested: '{requested_network.value}')."
        )

    return profile