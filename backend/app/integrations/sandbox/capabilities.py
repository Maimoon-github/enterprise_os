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
            "assemble_dossier",
            "validate_trace_bundle",
            "default",
        ),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=(
            "compliance_linter",
            "claim_checker",
            "dossier_assembler",
            "schema_validator",
        ),
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
            "acquire_source",
            "normalize_records",
            "de_identify",
            "deduplicate",
            "cluster_embeddings",
            "extract_topics",
            "compute_observed_share",
            "score_aspect_polarity",
            "detect_emotion",
            "ground_spans",
            "extract_needs",
            "classify_objections",
            "extract_vocabulary",
            "compare_touchpoints",
            "compare_segments",
            "aggregate_metrics",
            "evaluate_privacy",
            "verify_grounding",
            "check_bias",
            "validate_schema",
            "default",
        ),
        network_policy=NetworkPolicy.DISABLED,
        default_timeout_seconds=120,
        allowed_tools=(
            "nlp_classifier",
            "sentiment_analyzer",
            "source_fetcher",
            "pii_redactor",
            "dedupe_normalizer",
            "embedding_clustering",
            "frequency_analyzer",
            "absa_classifier",
            "span_grounder",
            "objection_extractor",
            "vocabulary_parser",
            "journey_comparator",
            "descriptive_aggregator",
            "qa_validator",
            "privacy_auditor",
            "hash_verifier",
        ),
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

AUTHORIZED_VOICE_SPECIALISTS = frozenset(
    {
        "VOICE-DISCOVERY",
        "VOICE-THEMES",
        "VOICE-SENTIMENT",
        "VOICE-NEEDS",
        "VOICE-JOURNEY",
        "VOICE-QA",
    }
)

VOICE_SPECIALIST_POLICIES: dict[str, dict[str, Any]] = {
    "VOICE-DISCOVERY": {
        "allowed_capabilities": (SandboxCapability.PARSE,),
        "allowed_operations": (
            "acquire_source",
            "normalize_records",
            "de_identify",
            "deduplicate",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("source_fetcher", "pii_redactor", "dedupe_normalizer"),
    },
    "VOICE-THEMES": {
        "allowed_capabilities": (SandboxCapability.PARSE,),
        "allowed_operations": (
            "cluster_embeddings",
            "extract_topics",
            "compute_observed_share",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("embedding_clustering", "frequency_analyzer"),
    },
    "VOICE-SENTIMENT": {
        "allowed_capabilities": (SandboxCapability.PARSE,),
        "allowed_operations": (
            "score_aspect_polarity",
            "detect_emotion",
            "ground_spans",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("absa_classifier", "span_grounder"),
    },
    "VOICE-NEEDS": {
        "allowed_capabilities": (SandboxCapability.PARSE,),
        "allowed_operations": (
            "extract_needs",
            "classify_objections",
            "extract_vocabulary",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("objection_extractor", "vocabulary_parser"),
    },
    "VOICE-JOURNEY": {
        "allowed_capabilities": (SandboxCapability.PARSE,),
        "allowed_operations": (
            "compare_touchpoints",
            "compare_segments",
            "aggregate_metrics",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("journey_comparator", "descriptive_aggregator"),
    },
    "VOICE-QA": {
        "allowed_capabilities": (SandboxCapability.PARSE,),
        "allowed_operations": (
            "evaluate_privacy",
            "verify_grounding",
            "check_bias",
            "validate_schema",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("qa_validator", "privacy_auditor", "hash_verifier"),
    },
}

for key, val in list(VOICE_SPECIALIST_POLICIES.items()):
    short_key = key.replace("VOICE-", "").lower()
    VOICE_SPECIALIST_POLICIES[short_key] = val
    VOICE_SPECIALIST_POLICIES[f"w_voice.{short_key}"] = val

AUTHORIZED_CREATIVE_SPECIALISTS = frozenset(
    {
        "CREAT-RESEARCH",
        "CREAT-CONCEPT",
        "CREAT-COPY",
        "CREAT-VISUAL",
        "CREAT-ADAPT",
        "CREAT-QA",
    }
)

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
        "allowed_tools": (
            "public_search",
            "fetch_platform_specs",
            "dom_parser",
            "browser_automation",
        ),
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

AUTHORIZED_PRODUCT_SPECIALISTS = frozenset(
    {
        "w_prod.discovery",
        "w_prod.regulatory",
        "w_prod.claims",
        "w_prod.appraisal",
        "w_prod.product_lab",
        "w_prod.safety",
        "DISCOVERY",
        "REGULATORY",
        "CLAIMS",
        "APPRAISAL",
        "PRODUCT_LAB",
        "SAFETY",
        "S_VAL",
    }
)

AUTHORIZED_COMPETITOR_SPECIALISTS = frozenset(
    {
        "w_comp.discovery",
        "w_comp.advertising",
        "w_comp.ads",
        "w_comp.pricing",
        "w_comp.price",
        "w_comp.search_intel",
        "w_comp.search",
        "w_comp.positioning",
        "w_comp.position",
        "w_comp.synthesis",
        "w_comp.synth",
        "COMP-DISCOVERY",
        "COMP-ADS",
        "COMP-PRICE",
        "COMP-SEARCH",
        "COMP-POSITION",
        "COMP-SYNTH",
    }
)

COMPETITOR_SPECIALIST_POLICIES: dict[str, dict[str, Any]] = {
    # Discovery
    "w_comp.discovery": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": (
            "public_page_capture",
            "transparency_query",
            "serp_query",
            "entity_normalize",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("public_search", "official_transparency", "dom_parser"),
    },
    "COMP-DISCOVERY": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": (
            "public_page_capture",
            "transparency_query",
            "serp_query",
            "entity_normalize",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("public_search", "official_transparency", "dom_parser"),
    },
    # Ads
    "w_comp.ads": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": (
            "transparency_query",
            "public_page_capture",
            "ad_extract_compare",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("official_transparency", "dom_parser", "browser_automation"),
    },
    "w_comp.advertising": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": (
            "transparency_query",
            "public_page_capture",
            "ad_extract_compare",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("official_transparency", "dom_parser", "browser_automation"),
    },
    "COMP-ADS": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": (
            "transparency_query",
            "public_page_capture",
            "ad_extract_compare",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("official_transparency", "dom_parser", "browser_automation"),
    },
    # Price
    "w_comp.price": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": ("public_page_capture", "price_extract_compare", "default"),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("dom_parser", "price_tracker", "browser_automation"),
    },
    "w_comp.pricing": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": ("public_page_capture", "price_extract_compare", "default"),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("dom_parser", "price_tracker", "browser_automation"),
    },
    "COMP-PRICE": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": ("public_page_capture", "price_extract_compare", "default"),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("dom_parser", "price_tracker", "browser_automation"),
    },
    # Search
    "w_comp.search": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": (
            "serp_query",
            "public_page_capture",
            "serp_normalize_compare",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("public_search", "serp_extractor", "browser_automation"),
    },
    "w_comp.search_intel": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": (
            "serp_query",
            "public_page_capture",
            "serp_normalize_compare",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("public_search", "serp_extractor", "browser_automation"),
    },
    "COMP-SEARCH": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": (
            "serp_query",
            "public_page_capture",
            "serp_normalize_compare",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("public_search", "serp_extractor", "browser_automation"),
    },
    # Position
    "w_comp.position": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": ("public_page_capture", "position_extract_compare", "default"),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("dom_parser", "browser_automation"),
    },
    "w_comp.positioning": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": ("public_page_capture", "position_extract_compare", "default"),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("dom_parser", "browser_automation"),
    },
    "COMP-POSITION": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": ("public_page_capture", "position_extract_compare", "default"),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("dom_parser", "browser_automation"),
    },
    # Synthesis (OFFLINE ONLY - Zero Research-Network Egress)
    "w_comp.synthesis": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": ("evidence_synthesize", "default"),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("evidence_synthesizer",),
    },
    "w_comp.synth": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": ("evidence_synthesize", "default"),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("evidence_synthesizer",),
    },
    "COMP-SYNTH": {
        "allowed_capabilities": (SandboxCapability.SCRAPE,),
        "allowed_operations": ("evidence_synthesize", "default"),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("evidence_synthesizer",),
    },
}

PRODUCT_SPECIALIST_POLICIES: dict[str, dict[str, Any]] = {
    "w_prod.discovery": {
        "allowed_capabilities": (SandboxCapability.VAL,),
        "allowed_operations": (
            "research_literature",
            "fetch_official_rules",
            "acquire_source",
            "parse_metadata",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": (
            "literature_search",
            "source_fetcher",
            "metadata_parser",
            "public_search",
        ),
    },
    "w_prod.regulatory": {
        "allowed_capabilities": (SandboxCapability.VAL,),
        "allowed_operations": (
            "check_regulatory_rules",
            "verify_statutory_requirements",
            "parse_rule_context",
            "default",
        ),
        "network_policy": NetworkPolicy.ALLOWLIST,
        "allowed_tools": ("rule_checker", "statutory_linter", "rule_parser", "compliance_linter"),
    },
    "w_prod.claims": {
        "allowed_capabilities": (SandboxCapability.VAL,),
        "allowed_operations": (
            "extract_claims",
            "classify_claim",
            "map_claim_evidence",
            "inspect_claim_imagery",
            "validate_claim",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": (
            "claim_extractor",
            "claim_classifier",
            "evidence_mapper",
            "vision_inspector",
            "claim_checker",
        ),
    },
    "w_prod.appraisal": {
        "allowed_capabilities": (SandboxCapability.VAL,),
        "allowed_operations": (
            "appraise_evidence",
            "assess_study_design",
            "grade_certainty",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("bias_assessor", "methodology_appraiser", "certainty_grader"),
    },
    "w_prod.product_lab": {
        "allowed_capabilities": (SandboxCapability.VAL,),
        "allowed_operations": (
            "validate_formulation",
            "audit_lab_report",
            "verify_test_methods",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("formulation_validator", "lab_report_auditor", "test_method_verifier"),
    },
    "w_prod.safety": {
        "allowed_capabilities": (SandboxCapability.VAL,),
        "allowed_operations": (
            "assess_safety",
            "evaluate_hazards",
            "screen_adverse_signals",
            "default",
        ),
        "network_policy": NetworkPolicy.DISABLED,
        "allowed_tools": ("hazard_evaluator", "safety_screener", "toxicology_analyzer"),
    },
}

for key, val in list(PRODUCT_SPECIALIST_POLICIES.items()):
    short_key = key.replace("w_prod.", "").upper()
    PRODUCT_SPECIALIST_POLICIES[short_key] = val

WORKER_CAPABILITY_MAP: dict[WorkerRole, SandboxCapability] = {
    profile.allowed_worker: profile.capability
    for profile in CAPABILITY_REGISTRY.values()
    if profile.allowed_worker not in (WorkerRole.CREATIVE_CONTENT, WorkerRole.CUSTOMER_VOICE)
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
        or (
            specialist_id is not None
            and (specialist_id.startswith("CREAT-") or specialist_id in ("W_CREAT", "NONE"))
        )
    )

    if is_creative:
        # Zero-sandbox enforcement for W_CREAT coordinator
        if specialist_id in ("W_CREAT", "NONE", "") or (
            worker_id == "W_CREAT" and not specialist_id
        ):
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

            req_net = (
                NetworkPolicy(requested_network)
                if isinstance(requested_network, str)
                else requested_network
            )

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
            elif (
                egress_grant is not None and spec_policy["network_policy"] == NetworkPolicy.DISABLED
            ):
                raise SandboxInvocationError(
                    f"Egress grant cannot be attached to Creative specialist '{specialist_id}' under DENY_ALL network policy."
                )

            if egress_grant is not None:
                if egress_grant.is_expired():
                    raise SandboxInvocationError(
                        f"Egress grant '{egress_grant.grant_id}' has expired."
                    )
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

    # 2. Product Evidence Specialist Context Enforcement
    is_prod_evidence = (
        worker_id == "W_PROD"
        or parsed_role == WorkerRole.PRODUCT_EVIDENCE
        or (
            specialist_id is not None
            and (
                specialist_id.startswith("w_prod.")
                or specialist_id in AUTHORIZED_PRODUCT_SPECIALISTS
            )
        )
    )

    if is_prod_evidence and specialist_id is not None and specialist_id != "S_VAL":
        if specialist_id not in AUTHORIZED_PRODUCT_SPECIALISTS:
            raise SandboxInvocationError(
                f"Unauthorized or unknown Product Evidence specialist: '{specialist_id}'. Fail closed."
            )

        spec_policy = PRODUCT_SPECIALIST_POLICIES[specialist_id]
        if capability not in spec_policy["allowed_capabilities"]:
            raise SandboxInvocationError(
                f"Specialist '{specialist_id}' is not authorized for capability '{capability.value}'."
            )

        if operation not in spec_policy["allowed_operations"]:
            raise SandboxInvocationError(
                f"Operation '{operation}' is not permitted for Product Evidence specialist '{specialist_id}'. "
                f"Permitted operations: {spec_policy['allowed_operations']}"
            )

        req_net = (
            NetworkPolicy(requested_network)
            if isinstance(requested_network, str)
            else requested_network
        )

        if req_net != NetworkPolicy.DISABLED:
            if spec_policy["network_policy"] == NetworkPolicy.DISABLED:
                raise SandboxInvocationError(
                    f"Network access denied: Product Evidence specialist '{specialist_id}' is restricted to DENY_ALL (disabled) network policy."
                )
            if req_net not in (NetworkPolicy.ALLOWLIST, NetworkPolicy.CONTROLLED):
                raise SandboxInvocationError(
                    f"Product Evidence specialist '{specialist_id}' only permits explicit allowlist/controlled egress (requested: '{req_net.value}')."
                )
            if egress_grant is None:
                raise SandboxInvocationError(
                    f"Network access denied: Product Evidence specialist '{specialist_id}' requested network without an authorized SandboxEgressGrant."
                )
            if egress_grant.specialist_id and egress_grant.specialist_id != specialist_id:
                raise SandboxInvocationError(
                    f"Egress grant specialist mismatch: grant issued for '{egress_grant.specialist_id}' cannot be used by '{specialist_id}'."
                )
        elif egress_grant is not None and spec_policy["network_policy"] == NetworkPolicy.DISABLED:
            raise SandboxInvocationError(
                f"Egress grant cannot be attached to Product Evidence specialist '{specialist_id}' under DENY_ALL network policy."
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
            allowed_worker=WorkerRole.PRODUCT_EVIDENCE,
            allowed_operations=spec_policy["allowed_operations"],
            network_policy=spec_policy["network_policy"],
            default_timeout_seconds=profile.default_timeout_seconds,
            allowed_tools=spec_policy["allowed_tools"],
        )

    # 3. Competitor Intel Specialist Context Enforcement
    is_competitor = (
        worker_id == "W_COMP"
        or parsed_role == WorkerRole.COMPETITOR_INTEL
        or (
            specialist_id is not None
            and (
                specialist_id.startswith("w_comp.")
                or specialist_id.startswith("COMP-")
                or specialist_id in ("W_COMP", "NONE")
            )
        )
    )

    if is_competitor:
        # Zero-sandbox enforcement for W_COMP coordinator
        if specialist_id in ("W_COMP", "NONE", "") or (worker_id == "W_COMP" and not specialist_id):
            raise SandboxInvocationError(
                "W_COMP coordinator has zero sandbox authority; execution requires an authorized Competitor specialist_id."
            )

        if specialist_id is not None and specialist_id != "S_SCRAPE":
            if specialist_id not in AUTHORIZED_COMPETITOR_SPECIALISTS:
                raise SandboxInvocationError(
                    f"Unauthorized or unknown Competitor specialist: '{specialist_id}'. Fail closed."
                )

            spec_policy = COMPETITOR_SPECIALIST_POLICIES[specialist_id]
            if capability not in spec_policy["allowed_capabilities"]:
                raise SandboxInvocationError(
                    f"Specialist '{specialist_id}' is not authorized for capability '{capability.value}'."
                )

            if operation not in spec_policy["allowed_operations"]:
                raise SandboxInvocationError(
                    f"Operation '{operation}' is not permitted for Competitor specialist '{specialist_id}'. "
                    f"Permitted operations: {spec_policy['allowed_operations']}"
                )

            req_net = (
                NetworkPolicy(requested_network)
                if isinstance(requested_network, str)
                else requested_network
            )

            if req_net != NetworkPolicy.DISABLED:
                if spec_policy["network_policy"] == NetworkPolicy.DISABLED:
                    raise SandboxInvocationError(
                        f"Network access denied: Competitor specialist '{specialist_id}' is restricted to DENY_ALL (disabled) network policy."
                    )
                if req_net != NetworkPolicy.ALLOWLIST:
                    raise SandboxInvocationError(
                        f"Competitor specialist '{specialist_id}' only permits explicit allowlist egress (requested: '{req_net.value}')."
                    )
                if egress_grant is None:
                    raise SandboxInvocationError(
                        f"Network access denied: Competitor specialist '{specialist_id}' requested network without an authorized SandboxEgressGrant."
                    )
                if egress_grant.specialist_id and egress_grant.specialist_id != specialist_id:
                    raise SandboxInvocationError(
                        f"Egress grant specialist mismatch: grant issued for '{egress_grant.specialist_id}' cannot be used by '{specialist_id}'."
                    )
            elif (
                egress_grant is not None and spec_policy["network_policy"] == NetworkPolicy.DISABLED
            ):
                raise SandboxInvocationError(
                    f"Egress grant cannot be attached to Competitor specialist '{specialist_id}' under DENY_ALL network policy."
                )

            if egress_grant is not None:
                if egress_grant.is_expired():
                    raise SandboxInvocationError(
                        f"Egress grant '{egress_grant.grant_id}' has expired."
                    )
                if egress_grant.specialist_id and egress_grant.specialist_id != specialist_id:
                    raise SandboxInvocationError(
                        f"Egress grant specialist mismatch: grant issued for '{egress_grant.specialist_id}' cannot be used by '{specialist_id}'."
                    )

            return CapabilityProfile(
                capability=capability,
                specialist_name=f"{specialist_id} Specialist",
                allowed_worker=WorkerRole.COMPETITOR_INTEL,
                allowed_operations=spec_policy["allowed_operations"],
                network_policy=spec_policy["network_policy"],
                default_timeout_seconds=profile.default_timeout_seconds,
                allowed_tools=spec_policy["allowed_tools"],
            )

    # 4. Customer Voice Specialist Context Enforcement & Zero-Sandbox Coordinator Boundary
    is_voice = (
        worker_id == "W_VOICE"
        or parsed_role == WorkerRole.CUSTOMER_VOICE
        or (
            specialist_id is not None
            and (
                specialist_id.startswith("VOICE-")
                or specialist_id.startswith("w_voice.")
                or specialist_id in ("W_VOICE", "NONE")
                or specialist_id in AUTHORIZED_VOICE_SPECIALISTS
                or specialist_id in VOICE_SPECIALIST_POLICIES
            )
        )
    )

    if is_voice:
        # Zero-sandbox enforcement for W_VOICE coordinator
        if specialist_id in ("W_VOICE", "NONE", "") or (
            worker_id == "W_VOICE" and not specialist_id
        ):
            raise SandboxInvocationError(
                "W_VOICE coordinator has zero sandbox authority; execution requires an authorized Voice specialist_id."
            )

        if specialist_id is not None and specialist_id != "S_PARSE":
            if specialist_id not in AUTHORIZED_VOICE_SPECIALISTS and specialist_id not in VOICE_SPECIALIST_POLICIES:
                raise SandboxInvocationError(
                    f"Unauthorized or unknown Customer Voice specialist: '{specialist_id}'. Fail closed."
                )

            spec_policy = VOICE_SPECIALIST_POLICIES[specialist_id]
            if capability not in spec_policy["allowed_capabilities"]:
                raise SandboxInvocationError(
                    f"Specialist '{specialist_id}' is not authorized for capability '{capability.value}'."
                )

            if operation not in spec_policy["allowed_operations"]:
                raise SandboxInvocationError(
                    f"Operation '{operation}' is not permitted for Customer Voice specialist '{specialist_id}'. "
                    f"Permitted operations: {spec_policy['allowed_operations']}"
                )

            req_net = (
                NetworkPolicy(requested_network)
                if isinstance(requested_network, str)
                else requested_network
            )

            if req_net != NetworkPolicy.DISABLED:
                if spec_policy["network_policy"] == NetworkPolicy.DISABLED:
                    raise SandboxInvocationError(
                        f"Network access denied: Customer Voice specialist '{specialist_id}' is restricted to DENY_ALL (disabled) network policy."
                    )
                if req_net != NetworkPolicy.ALLOWLIST:
                    raise SandboxInvocationError(
                        f"Customer Voice specialist '{specialist_id}' only permits explicit allowlist egress (requested: '{req_net.value}')."
                    )
                if egress_grant is None:
                    raise SandboxInvocationError(
                        f"Network access denied: Customer Voice specialist '{specialist_id}' requested network without an authorized SandboxEgressGrant."
                    )
                if egress_grant.specialist_id and egress_grant.specialist_id != specialist_id:
                    raise SandboxInvocationError(
                        f"Egress grant specialist mismatch: grant issued for '{egress_grant.specialist_id}' cannot be used by '{specialist_id}'."
                    )
            elif (
                egress_grant is not None and spec_policy["network_policy"] == NetworkPolicy.DISABLED
            ):
                raise SandboxInvocationError(
                    f"Egress grant cannot be attached to Customer Voice specialist '{specialist_id}' under DENY_ALL network policy."
                )

            if egress_grant is not None:
                if egress_grant.is_expired():
                    raise SandboxInvocationError(
                        f"Egress grant '{egress_grant.grant_id}' has expired."
                    )
                if egress_grant.specialist_id and egress_grant.specialist_id != specialist_id:
                    raise SandboxInvocationError(
                        f"Egress grant specialist mismatch: grant issued for '{egress_grant.specialist_id}' cannot be used by '{specialist_id}'."
                    )

            return CapabilityProfile(
                capability=capability,
                specialist_name=f"{specialist_id} Specialist",
                allowed_worker=WorkerRole.CUSTOMER_VOICE,
                allowed_operations=spec_policy["allowed_operations"],
                network_policy=spec_policy["network_policy"],
                default_timeout_seconds=profile.default_timeout_seconds,
                allowed_tools=spec_policy["allowed_tools"],
            )

    # 5. Standard worker role vs capability compatibility
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
    2. If specialist_id is a known Product Evidence specialist, enforce its scoped tools.
    3. If specialist_id is a known Competitor specialist, enforce its scoped tools.
    4. If capability_grant is provided, requested_tool must be in grant.allowed_tools.
    5. requested_tool must also be in the capability profile's authorized allowed_tools.
    """
    if specialist_id and specialist_id in CREATIVE_SPECIALIST_POLICIES:
        allowed_tools = CREATIVE_SPECIALIST_POLICIES[specialist_id]["allowed_tools"]
        if requested_tool not in allowed_tools:
            raise SandboxInvocationError(
                f"Tool '{requested_tool}' is not permitted for Creative specialist '{specialist_id}'. "
                f"Permitted tools: {allowed_tools}"
            )
        return

    if specialist_id and specialist_id in PRODUCT_SPECIALIST_POLICIES:
        allowed_tools = PRODUCT_SPECIALIST_POLICIES[specialist_id]["allowed_tools"]
        if requested_tool not in allowed_tools:
            raise SandboxInvocationError(
                f"Tool '{requested_tool}' is not permitted for Product Evidence specialist '{specialist_id}'. "
                f"Permitted tools: {allowed_tools}"
            )
        return

    if specialist_id and specialist_id in COMPETITOR_SPECIALIST_POLICIES:
        allowed_tools = COMPETITOR_SPECIALIST_POLICIES[specialist_id]["allowed_tools"]
        if requested_tool not in allowed_tools:
            raise SandboxInvocationError(
                f"Tool '{requested_tool}' is not permitted for Competitor specialist '{specialist_id}'. "
                f"Permitted tools: {allowed_tools}"
            )
        return

    if specialist_id and specialist_id in VOICE_SPECIALIST_POLICIES:
        allowed_tools = VOICE_SPECIALIST_POLICIES[specialist_id]["allowed_tools"]
        if requested_tool not in allowed_tools:
            raise SandboxInvocationError(
                f"Tool '{requested_tool}' is not permitted for Customer Voice specialist '{specialist_id}'. "
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
