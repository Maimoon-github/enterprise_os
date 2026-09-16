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
from typing import Any

from app.core.exceptions import SandboxInvocationError
from app.schemas.governance import WorkerRole
from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxEgressGrant


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
        allowed_operations=(
            "parse_ast",
            "lint",
            "generate_diff",
            "execute_code",
            "validate_syntax",
            "inspect_files",
            "extract_symbols",
            "inspect_dependencies",
            "introspect_schema",
            "parse_manifest",
            "validate_cms_schema",
            "generate_schema_diff",
            "analyze_compatibility",
            "generate_migration",
            "simulate_migration",
            "generate_contracts",
            "validate_template",
            "format_ui_code",
            "compile_component",
            "render_ui_view",
            "capture_render_evidence",
            "scan_accessibility_wcag",
            "apply_code_patch",
            "format_code",
            "inspect_ast_symbols",
            "validate_syntax_compiler",
            "manage_packages",
            "generate_code",
            "verify_environment",
            "run_build",
            "run_lint_check",
            "run_format_check",
            "run_type_check",
            "run_automated_tests",
            "run_coverage_analysis",
            "scan_sast",
            "scan_secrets",
            "scan_dependencies_sca",
            "review_manifest_configs",
            "check_authorization_boundaries",
            "analyze_ast_dangerous_patterns",
            "package_release_bundle",
            "generate_cyclonedx_sbom",
            "generate_deployment_manifest",
            "generate_rollback_manifest",
            "simulate_migration_dry_run",
            "verify_release_integrity",
            "default",
        ),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=(
            "ast_parser",
            "code_linter",
            "diff_generator",
            "file_inspector",
            "symbol_extractor",
            "dependency_inspector",
            "schema_introspector",
            "manifest_parser",
            "cms_schema_validator",
            "schema_diff_engine",
            "migration_generator",
            "compatibility_analyzer",
            "contract_generator",
            "migration_simulator",
            "template_validator",
            "ui_formatter",
            "component_compiler",
            "sandbox_browser_renderer",
            "render_evidence_capture",
            "wcag_accessibility_scanner",
            "code_patcher",
            "code_formatter",
            "ast_symbol_inspector",
            "compiler_sanity_checker",
            "package_manager_proxy",
            "application_code_generator",
            "environment_verifier",
            "build_runner",
            "lint_checker",
            "format_checker",
            "type_checker",
            "test_runner",
            "coverage_analyzer",
            "sast_scanner",
            "secret_detector",
            "sca_scanner",
            "config_reviewer",
            "boundary_checker",
            "ast_pattern_analyzer",
            "bundle_packager",
            "sbom_generator",
            "deployment_manifest_builder",
            "rollback_manifest_builder",
            "migration_dry_run_tester",
            "integrity_hasher",
        ),
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
        allowed_operations=(
            "validate_claim",
            "lint_compliance",
            "check_schema",
            "validate_product_dossier",
            "default",
        ),
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
        allowed_operations=(
            "parse_sentiment",
            "cluster_objections",
            "extract_feedback",
            "analyze_customer_voice",
            "default",
        ),
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
    egress_grant: SandboxEgressGrant | None = None,
) -> CapabilityProfile:
    """Validate that a requested sandbox execution adheres to capability allowlisting.

    Enforces least privilege:
    1. Capability must be a registered SandboxCapability.
    2. If worker_role is provided, it must match the capability's authorized worker.
    3. Operation must be in the profile's allowed_operations.
    4. Requested network access must not exceed the capability's allowed network policy.
    5. If an egress grant is attached, its worker, capability, and expiry are strictly validated.

    Raises SandboxInvocationError on any policy breach (fail-closed).
    """
    if isinstance(capability, str):
        try:
            capability = SandboxCapability(capability)
        except ValueError:
            raise SandboxInvocationError(
                f"Unauthorized or invalid sandbox capability: {capability}"
            )

    if capability not in CAPABILITY_REGISTRY:
        raise SandboxInvocationError(f"Unauthorized or invalid sandbox capability: {capability}")

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

    if (
        requested_network != NetworkPolicy.DISABLED
        and profile.network_policy == NetworkPolicy.DISABLED
    ):
        raise SandboxInvocationError(
            f"Network access policy violation: capability '{capability.value}' does not permit "
            f"network access (requested: '{requested_network.value}')."
        )

    if egress_grant is not None:
        if egress_grant.is_expired():
            raise SandboxInvocationError(f"Egress grant '{egress_grant.grant_id}' has expired.")
        if worker_role is not None and egress_grant.worker_role != worker_role:
            raise SandboxInvocationError(
                f"Egress grant worker role mismatch: grant worker '{egress_grant.worker_role.value}' "
                f"does not match executing worker '{worker_role.value}'."
            )
        if egress_grant.capability != capability:
            raise SandboxInvocationError(
                f"Egress grant capability mismatch: grant capability '{egress_grant.capability.value}' "
                f"does not match executing capability '{capability.value}'."
            )

    return profile


def validate_egress_target(
    target: str,
    grant: SandboxEgressGrant | None,
    port: int | None = None,
) -> None:
    """Validate that a destination URL/domain is authorized under the active egress grant.

    Raises SandboxInvocationError if unauthorized, expired, or targeting SSRF destinations (fail-closed).
    """
    if grant is None:
        raise SandboxInvocationError(
            "Network egress denied: No active SandboxEgressGrant attached (DENY_ALL default)."
        )

    allowed, reason = grant.is_destination_allowed(target, port=port)
    if not allowed:
        raise SandboxInvocationError(f"Network egress policy violation: {reason}")


def validate_tool_access(
    requested_tool: str,
    capability: SandboxCapability | str,
    capability_grant: Any | None = None,
) -> None:
    """Enforce explicit per-attempt micro-tool allowlisting fail-closed.

    1. If capability_grant is provided, requested_tool must be in grant.allowed_tools.
    2. requested_tool must also be in the capability profile's authorized allowed_tools.
    """
    if isinstance(capability, str):
        capability = SandboxCapability(capability)
    profile = CAPABILITY_REGISTRY.get(capability)
    if profile is None:
        raise SandboxInvocationError(f"Unknown capability: {capability}")

    if requested_tool not in profile.allowed_tools:
        raise SandboxInvocationError(
            f"Tool '{requested_tool}' is not permitted for capability '{capability.value}'. "
            f"Permitted tools: {profile.allowed_tools}"
        )

    if capability_grant is not None and hasattr(capability_grant, "allowed_tools"):
        if requested_tool not in capability_grant.allowed_tools:
            raise SandboxInvocationError(
                f"Tool '{requested_tool}' is not authorized under the active capability grant. "
                f"Authorized tools: {capability_grant.allowed_tools}"
            )
