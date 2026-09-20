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
        allowed_operations=(
            "model_media_mix",
            "optimize_budget",
            "simulate_funnel",
            "simulate_scenarios",
            "calculate_roas",
            "default",
        ),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=(
            "media_mix_modeler",
            "budget_allocator_tool",
            "funnel_simulator",
            "optimization_modeler",
            "allocation_solver",
            "diminishing_returns_model",
        ),
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

AUTHORIZED_CREATIVE_SPECIALISTS = frozenset({
    "CREAT-RESEARCH",
    "CREAT-CONCEPT",
    "CREAT-COPY",
    "CREAT-VISUAL",
    "CREAT-ADAPT",
    "CREAT-QA",
})

CREATIVE_SPECIALIST_POLICIES: dict[str, dict[str, Any]] = {
    "CREAT-RESEARCH": {
        "allowed_capabilities": (SandboxCapability.SCRAPE, SandboxCapability.COPY),
        "allowed_operations": (
            "public_search",
            "fetch_platform_specs",
            "scrape_prices",
            "parse_dom",
            "track_ads",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("public_search", "fetch_platform_specs", "dom_parser", "browser_automation"),
    },
    "CREAT-COPY": {
        "allowed_capabilities": (SandboxCapability.COPY,),
        "allowed_operations": (
            "s_copy_variant_gen",
            "generate_variants",
            "score_hooks",
            "format_validation",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("variant_generator", "hook_critic", "s_copy_variant_gen"),
    },
    "CREAT-CONCEPT": {
        "allowed_capabilities": (SandboxCapability.COPY,),
        "allowed_operations": ("default",),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": (),
    },
    "CREAT-VISUAL": {
        "allowed_capabilities": (SandboxCapability.COPY,),
        "allowed_operations": ("default",),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": (),
    },
    "CREAT-ADAPT": {
        "allowed_capabilities": (SandboxCapability.COPY,),
        "allowed_operations": ("default",),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": (),
    },
    "CREAT-QA": {
        "allowed_capabilities": (SandboxCapability.COPY,),
        "allowed_operations": ("default",),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": (),
    },
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
    specialist_id: str | None = None,
    stage_attempt_id: str | None = None,
    worker_id: str | None = None,
    requested_network: NetworkPolicy | str = NetworkPolicy.DISABLED,
    egress_grant: SandboxEgressGrant | None = None,
) -> CapabilityProfile:
    """Validate that a requested sandbox execution adheres to capability allowlisting.

    Enforces least privilege:
    1. Capability must be a registered SandboxCapability.
    2. W_CREAT coordinator has zero sandbox authority (fails closed if specialist_id missing or W_CREAT).
    3. Creative specialist executions require authorized specialist_id and adhere to per-specialist policy.
    4. If worker_role is provided, it must match the capability's authorized worker.
    5. Operation must be in the profile's allowed_operations.
    6. Requested network access must not exceed the capability's allowed network policy.
    7. If an egress grant is attached, its worker, specialist, capability, and expiry are strictly validated.

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

    # Convert string worker role if provided
    parsed_role: WorkerRole | None = None
    if worker_role is not None:
        if isinstance(worker_role, str):
            if worker_role == "W_CREAT":
                parsed_role = WorkerRole.CREATIVE_CONTENT
            else:
                try:
                    parsed_role = WorkerRole(worker_role)
                except ValueError:
                    raise SandboxInvocationError(f"Unknown worker role: {worker_role}")
        else:
            parsed_role = worker_role

    # 1. Creative Context Enforcement
    is_creative = (
        worker_id == "W_CREAT"
        or parsed_role == WorkerRole.CREATIVE_CONTENT
        or (specialist_id is not None and (specialist_id.startswith("CREAT-") or specialist_id in ("W_CREAT", "NONE")))
    )

    if is_creative:
        # Zero-sandbox enforcement for W_CREAT coordinator
        if specialist_id in ("W_CREAT", "NONE", "") or (worker_id == "W_CREAT" and not specialist_id):
            raise SandboxInvocationError(
                "W_CREAT coordinator has zero sandbox authority; execution requires an authorized Creative specialist_id."
            )

        # If specialist_id is provided, evaluate Creative specialist policy
        if specialist_id is not None and specialist_id != "S_COPY":
            if specialist_id not in AUTHORIZED_CREATIVE_SPECIALISTS:
                raise SandboxInvocationError(
                    f"Unauthorized or unknown Creative specialist: '{specialist_id}'. Fail closed."
                )

            spec_policy = CREATIVE_SPECIALIST_POLICIES[specialist_id]
            if capability not in spec_policy["allowed_capabilities"]:
                raise SandboxInvocationError(
                    f"Specialist '{specialist_id}' is not authorized for capability '{capability.value}'."
                )

            if operation not in spec_policy["allowed_operations"]:
                raise SandboxInvocationError(
                    f"Operation '{operation}' is not permitted for Creative specialist '{specialist_id}'. "
                    f"Permitted operations: {spec_policy['allowed_operations']}"
                )

            req_net = NetworkPolicy(requested_network) if isinstance(requested_network, str) else requested_network

            if req_net != NetworkPolicy.DISABLED:
                if spec_policy["network_policy"] == NetworkPolicy.DISABLED:
                    raise SandboxInvocationError(
                        f"Network access denied: Creative specialist '{specialist_id}' is restricted to DENY_ALL (disabled) network policy."
                    )
                if req_net != NetworkPolicy.ALLOWLIST:
                    raise SandboxInvocationError(
                        f"Creative specialist '{specialist_id}' only permits explicit allowlist egress (requested: '{req_net.value}')."
                    )
                if egress_grant is None:
                    raise SandboxInvocationError(
                        f"Network access denied: Creative specialist '{specialist_id}' requested network without an authorized SandboxEgressGrant."
                    )
                if egress_grant.specialist_id and egress_grant.specialist_id != specialist_id:
                    raise SandboxInvocationError(
                        f"Egress grant specialist mismatch: grant issued for '{egress_grant.specialist_id}' cannot be used by '{specialist_id}'."
                    )
            elif egress_grant is not None and spec_policy["network_policy"] == NetworkPolicy.DISABLED:
                raise SandboxInvocationError(
                    f"Egress grant cannot be attached to Creative specialist '{specialist_id}' under DENY_ALL network policy."
                )

            if egress_grant is not None:
                if egress_grant.is_expired():
                    raise SandboxInvocationError(f"Egress grant '{egress_grant.grant_id}' has expired.")
                if egress_grant.specialist_id and egress_grant.specialist_id != specialist_id:
                    raise SandboxInvocationError(
                        f"Egress grant specialist mismatch: grant issued for '{egress_grant.specialist_id}' cannot be used by '{specialist_id}'."
                    )

            return CapabilityProfile(
                capability=capability,
                specialist_name=f"{specialist_id} Specialist",
                allowed_worker=WorkerRole.CREATIVE_CONTENT,
                allowed_operations=spec_policy["allowed_operations"],
                network_policy=spec_policy["network_policy"],
                default_timeout_seconds=profile.default_timeout_seconds,
                allowed_tools=spec_policy["allowed_tools"],
            )

    # 2. Standard worker role vs capability compatibility
    if parsed_role is not None:
        if parsed_role != profile.allowed_worker:
            raise SandboxInvocationError(
                f"Capability access denied: worker '{parsed_role.value}' is not authorized to request "
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
        if parsed_role is not None and egress_grant.worker_role != parsed_role:
            raise SandboxInvocationError(
                f"Egress grant worker role mismatch: grant worker '{egress_grant.worker_role.value}' "
                f"does not match executing worker '{parsed_role.value}'."
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
    specialist_id: str | None = None,
) -> None:
    """Enforce explicit per-attempt micro-tool allowlisting fail-closed.

    1. If specialist_id is a known Creative specialist, enforce its scoped tools.
    2. If capability_grant is provided, requested_tool must be in grant.allowed_tools.
    3. requested_tool must also be in the capability profile's authorized allowed_tools.
    """
    if specialist_id and specialist_id in CREATIVE_SPECIALIST_POLICIES:
        allowed_tools = CREATIVE_SPECIALIST_POLICIES[specialist_id]["allowed_tools"]
        if requested_tool not in allowed_tools:
            raise SandboxInvocationError(
                f"Tool '{requested_tool}' is not permitted for Creative specialist '{specialist_id}'. "
                f"Permitted tools: {allowed_tools}"
            )
        return

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
