"""Authoritative specialist model profiles, scope validation, and routing for W_PROD / S_VAL."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

from app.core.exceptions import ConfigurationError, PolicyViolationError, SandboxInvocationError
from app.core.settings import LlmSettings
from app.integrations.llm.client import LlmClient
from app.schemas.governance import WorkerRole
from app.schemas.product_evidence import (
    ProductEvidenceTask,
    SpecialistRole,
    SpecialistResult,
    SpecialistResultStatus,
    SpecialistTask,
)
from app.schemas.sandbox import (
    NetworkPolicy,
    ResourceLimits,
    SandboxCapability,
    SandboxEgressGrant,
    SandboxInvocationMandate,
    SandboxResult,
)


@dataclass(frozen=True)
class SpecialistModelProfile:
    """Immutable model, security, budget, and capability profile for a W_PROD specialist."""

    profile_id: str
    role: SpecialistRole
    profile_version: str = "1.0"
    provider_adapter: str = "provider_neutral"
    model_id: str = "claude-3-5-sonnet"
    model_revision: str = "2024-10-22"
    reasoning_mode: str = "general_reasoning"
    capabilities_required: tuple[str, ...] = ("text",)
    context_limit: int = 64000
    max_output_tokens: int = 4096
    sampling_parameters: dict[str, Any] = field(default_factory=lambda: {"temperature": 0.0, "seed": 42})
    timeout_ms: int = 45000
    max_attempts: int = 2
    budget_limit: float = 3.0
    budget_limit_tokens: int = 6000
    data_classification_allowlist: tuple[str, ...] = ("public", "internal")
    endpoint_policy_ref: str = "policy:w_prod:offline:v1"
    credential_ref: str = "cred:vault:w_prod"
    fallback_profile_ids: tuple[str, ...] = ()
    prompt_version: str = "1.0.0"
    output_schema_version: str = "1.0"
    allowed_operations: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED

    def compute_digest(self) -> str:
        """Compute SHA-256 canonical digest of this profile."""
        payload = {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "role": self.role.value if isinstance(self.role, SpecialistRole) else str(self.role),
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
            "fallback_profile_ids": sorted(self.fallback_profile_ids),
            "prompt_version": self.prompt_version,
            "output_schema_version": self.output_schema_version,
            "allowed_operations": sorted(self.allowed_operations),
            "allowed_tools": sorted(self.allowed_tools),
            "network_policy": self.network_policy.value if isinstance(self.network_policy, NetworkPolicy) else str(self.network_policy),
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


DISCOVERY_PROFILE = SpecialistModelProfile(
    profile_id="w_prod.discovery.v1",
    role=SpecialistRole.DISCOVERY,
    profile_version="1.0",
    provider_adapter="provider_neutral",
    model_id="claude-3-5-sonnet",
    model_revision="2024-10-22",
    reasoning_mode="literature_extraction",
    capabilities_required=("text", "search"),
    context_limit=128000,
    max_output_tokens=4096,
    sampling_parameters={"temperature": 0.0, "seed": 42},
    timeout_ms=60000,
    max_attempts=3,
    budget_limit=5.0,
    budget_limit_tokens=10000,
    data_classification_allowlist=("public", "internal"),
    endpoint_policy_ref="policy:w_prod:egress:literature:v1",
    credential_ref="cred:vault:w_prod:discovery",
    fallback_profile_ids=("w_prod.discovery.v1.fallback",),
    prompt_version="1.0.0",
    output_schema_version="1.0",
    allowed_operations=(
        "research_literature",
        "fetch_official_rules",
        "acquire_source",
        "parse_metadata",
        "default",
    ),
    allowed_tools=("literature_search", "source_fetcher", "metadata_parser", "public_search"),
    network_policy=NetworkPolicy.ALLOWLIST,
)

APPRAISAL_PROFILE = SpecialistModelProfile(
    profile_id="w_prod.appraisal.v1",
    role=SpecialistRole.APPRAISAL,
    profile_version="1.0",
    provider_adapter="provider_neutral",
    model_id="claude-3-5-sonnet",
    model_revision="2024-10-22",
    reasoning_mode="methodological_appraisal",
    capabilities_required=("text",),
    context_limit=64000,
    max_output_tokens=4096,
    sampling_parameters={"temperature": 0.0, "seed": 42},
    timeout_ms=45000,
    max_attempts=2,
    budget_limit=3.0,
    budget_limit_tokens=6000,
    data_classification_allowlist=("public", "internal", "confidential_sanitized"),
    endpoint_policy_ref="policy:w_prod:offline:v1",
    credential_ref="cred:vault:w_prod:appraisal",
    fallback_profile_ids=("w_prod.appraisal.v1.fallback",),
    prompt_version="1.0.0",
    output_schema_version="1.0",
    allowed_operations=(
        "appraise_evidence",
        "assess_study_design",
        "grade_certainty",
        "default",
    ),
    allowed_tools=("bias_assessor", "methodology_appraiser", "certainty_grader"),
    network_policy=NetworkPolicy.DISABLED,
)

PRODUCT_LAB_PROFILE = SpecialistModelProfile(
    profile_id="w_prod.product_lab.v1",
    role=SpecialistRole.PRODUCT_LAB,
    profile_version="1.0",
    provider_adapter="provider_neutral",
    model_id="claude-3-5-sonnet",
    model_revision="2024-10-22",
    reasoning_mode="formulation_lab_audit",
    capabilities_required=("text",),
    context_limit=64000,
    max_output_tokens=4096,
    sampling_parameters={"temperature": 0.0, "seed": 42},
    timeout_ms=45000,
    max_attempts=2,
    budget_limit=3.0,
    budget_limit_tokens=6000,
    data_classification_allowlist=("internal", "confidential_sanitized"),
    endpoint_policy_ref="policy:w_prod:offline:v1",
    credential_ref="cred:vault:w_prod:product_lab",
    fallback_profile_ids=("w_prod.product_lab.v1.fallback",),
    prompt_version="1.0.0",
    output_schema_version="1.0",
    allowed_operations=(
        "validate_formulation",
        "audit_lab_report",
        "verify_test_methods",
        "default",
    ),
    allowed_tools=("formulation_validator", "lab_report_auditor", "test_method_verifier"),
    network_policy=NetworkPolicy.DISABLED,
)

SAFETY_PROFILE = SpecialistModelProfile(
    profile_id="w_prod.safety.v1",
    role=SpecialistRole.SAFETY,
    profile_version="1.0",
    provider_adapter="provider_neutral",
    model_id="claude-3-5-sonnet",
    model_revision="2024-10-22",
    reasoning_mode="toxicology_safety_evaluation",
    capabilities_required=("text",),
    context_limit=64000,
    max_output_tokens=4096,
    sampling_parameters={"temperature": 0.0, "seed": 42},
    timeout_ms=45000,
    max_attempts=2,
    budget_limit=3.0,
    budget_limit_tokens=6000,
    data_classification_allowlist=("internal", "confidential_sanitized"),
    endpoint_policy_ref="policy:w_prod:offline:v1",
    credential_ref="cred:vault:w_prod:safety",
    fallback_profile_ids=("w_prod.safety.v1.fallback",),
    prompt_version="1.0.0",
    output_schema_version="1.0",
    allowed_operations=(
        "assess_safety",
        "evaluate_hazards",
        "screen_adverse_signals",
        "default",
    ),
    allowed_tools=("hazard_evaluator", "safety_screener", "toxicology_analyzer"),
    network_policy=NetworkPolicy.DISABLED,
)

CLAIMS_PROFILE = SpecialistModelProfile(
    profile_id="w_prod.claims.v1",
    role=SpecialistRole.CLAIMS,
    profile_version="1.0",
    provider_adapter="provider_neutral",
    model_id="claude-3-5-sonnet",
    model_revision="2024-10-22",
    reasoning_mode="claim_evidence_mapping",
    capabilities_required=("text",),
    context_limit=64000,
    max_output_tokens=4096,
    sampling_parameters={"temperature": 0.0, "seed": 42},
    timeout_ms=45000,
    max_attempts=2,
    budget_limit=3.0,
    budget_limit_tokens=6000,
    data_classification_allowlist=("public", "internal"),
    endpoint_policy_ref="policy:w_prod:offline:v1",
    credential_ref="cred:vault:w_prod:claims",
    fallback_profile_ids=("w_prod.claims.v1.fallback",),
    prompt_version="1.0.0",
    output_schema_version="1.0",
    allowed_operations=(
        "extract_claims",
        "classify_claim",
        "map_claim_evidence",
        "inspect_claim_imagery",
        "validate_claim",
        "default",
    ),
    allowed_tools=("claim_extractor", "claim_classifier", "evidence_mapper", "vision_inspector", "claim_checker"),
    network_policy=NetworkPolicy.DISABLED,
)

REGULATORY_PROFILE = SpecialistModelProfile(
    profile_id="w_prod.regulatory.v1",
    role=SpecialistRole.REGULATORY,
    profile_version="1.0",
    provider_adapter="provider_neutral",
    model_id="claude-3-5-sonnet",
    model_revision="2024-10-22",
    reasoning_mode="regulatory_compliance_check",
    capabilities_required=("text", "search"),
    context_limit=128000,
    max_output_tokens=4096,
    sampling_parameters={"temperature": 0.0, "seed": 42},
    timeout_ms=60000,
    max_attempts=3,
    budget_limit=5.0,
    budget_limit_tokens=10000,
    data_classification_allowlist=("public", "internal"),
    endpoint_policy_ref="policy:w_prod:egress:official_rules:v1",
    credential_ref="cred:vault:w_prod:regulatory",
    fallback_profile_ids=("w_prod.regulatory.v1.fallback",),
    prompt_version="1.0.0",
    output_schema_version="1.0",
    allowed_operations=(
        "check_regulatory_rules",
        "verify_statutory_requirements",
        "parse_rule_context",
        "default",
    ),
    allowed_tools=("rule_checker", "statutory_linter", "rule_parser", "compliance_linter"),
    network_policy=NetworkPolicy.ALLOWLIST,
)

SPECIALIST_PROFILES: dict[SpecialistRole, SpecialistModelProfile] = {
    SpecialistRole.DISCOVERY: DISCOVERY_PROFILE,
    SpecialistRole.APPRAISAL: APPRAISAL_PROFILE,
    SpecialistRole.PRODUCT_LAB: PRODUCT_LAB_PROFILE,
    SpecialistRole.SAFETY: SAFETY_PROFILE,
    SpecialistRole.CLAIMS: CLAIMS_PROFILE,
    SpecialistRole.REGULATORY: REGULATORY_PROFILE,
}


def get_specialist_profile(role: SpecialistRole | str) -> SpecialistModelProfile:
    """Retrieve the authoritative immutable profile for ``role``."""
    if isinstance(role, str):
        role_clean = role.upper().replace("W_PROD.", "")
        try:
            parsed_role = SpecialistRole(role_clean)
        except ValueError:
            raise PolicyViolationError(f"Unknown or unauthorized specialist role: '{role}'")
    else:
        parsed_role = role

    if parsed_role not in SPECIALIST_PROFILES:
        raise PolicyViolationError(f"No registered model profile for specialist role: {parsed_role}")
    return SPECIALIST_PROFILES[parsed_role]


def validate_profile_binding(specialist_task: SpecialistTask, profile: SpecialistModelProfile) -> None:
    """Validate that the specialist task's profile reference and digest match the profile."""
    expected_digest = profile.compute_digest()
    role_name = specialist_task.specialist_role.value if hasattr(specialist_task.specialist_role, "value") else str(specialist_task.specialist_role)
    if specialist_task.profile_digest and specialist_task.profile_digest != expected_digest:
        raise PolicyViolationError(
            f"Profile digest mismatch for '{role_name}': "
            f"task specified '{specialist_task.profile_digest}', computed '{expected_digest}'."
        )
    if specialist_task.profile_ref and specialist_task.profile_ref != profile.profile_id:
        raise PolicyViolationError(
            f"Profile ref mismatch: task specified '{specialist_task.profile_ref}', "
            f"expected '{profile.profile_id}'."
        )


def validate_delegated_scope(
    parent_task: ProductEvidenceTask,
    specialist_task: SpecialistTask,
    profile: SpecialistModelProfile,
    egress_grant: SandboxEgressGrant | None = None,
) -> None:
    """Verify that every delegated scope is a strict subset of the parent grant."""
    # 1. Tenant match
    if specialist_task.tenant_id != parent_task.tenant_id:
        raise PolicyViolationError(
            f"Tenant isolation failure: delegated task tenant '{specialist_task.tenant_id}' "
            f"does not match parent tenant '{parent_task.tenant_id}'."
        )

    # 2. Parent task ID match
    if specialist_task.parent_task_id != parent_task.task_id:
        raise PolicyViolationError(
            f"Parent task ID mismatch: delegated task cites '{specialist_task.parent_task_id}', "
            f"parent is '{parent_task.task_id}'."
        )

    # 3. Operation subset
    if parent_task.allowed_s_val_operations and specialist_task.operation not in parent_task.allowed_s_val_operations:
        raise PolicyViolationError(
            f"Operation '{specialist_task.operation}' is not within parent task allowed S_VAL operations: "
            f"{parent_task.allowed_s_val_operations}"
        )

    if specialist_task.operation not in profile.allowed_operations:
        raise PolicyViolationError(
            f"Operation '{specialist_task.operation}' is not authorized for specialist profile '{profile.profile_id}'. "
            f"Authorized operations: {profile.allowed_operations}"
        )

    # 4. Budget limit attenuation
    if specialist_task.delegated_token_limit > parent_task.budget_limit_tokens:
        raise PolicyViolationError(
            f"Budget limit violation: delegated tokens {specialist_task.delegated_token_limit} "
            f"exceeds parent budget limit {parent_task.budget_limit_tokens}."
        )
    if specialist_task.delegated_token_limit > profile.budget_limit_tokens:
        raise PolicyViolationError(
            f"Budget limit violation: delegated tokens {specialist_task.delegated_token_limit} "
            f"exceeds profile budget limit {profile.budget_limit_tokens}."
        )

    # 5. Deadline attenuation
    if specialist_task.deadline_utc and parent_task.deadline_utc:
        spec_dl = specialist_task.deadline_utc if specialist_task.deadline_utc.tzinfo else specialist_task.deadline_utc.replace(tzinfo=UTC)
        parent_dl = parent_task.deadline_utc if parent_task.deadline_utc.tzinfo else parent_task.deadline_utc.replace(tzinfo=UTC)
        if spec_dl > parent_dl:
            raise PolicyViolationError(
                f"Deadline violation: delegated deadline {spec_dl} exceeds parent deadline {parent_dl}."
            )

    # 6. Least privilege network policy per role
    if profile.network_policy == NetworkPolicy.DISABLED:
        if egress_grant is not None:
            raise PolicyViolationError(
                f"Network grant violation: Specialist '{profile.role.value}' is strictly offline; "
                "no egress grant may be attached."
            )
    else:
        if egress_grant is not None:
            if egress_grant.worker_role != WorkerRole.PRODUCT_EVIDENCE:
                raise PolicyViolationError(
                    f"Egress grant worker role mismatch: {egress_grant.worker_role} != {WorkerRole.PRODUCT_EVIDENCE}"
                )
            if egress_grant.is_expired():
                raise PolicyViolationError(f"Attached egress grant '{egress_grant.grant_id}' has expired.")

    # 7. Claims vision requirement
    if specialist_task.operation == "inspect_claim_imagery":
        vision_allowed = specialist_task.context_slice.get("vision_granted", False)
        if not vision_allowed:
            raise PolicyViolationError(
                "Operation 'inspect_claim_imagery' requires explicit vision grant in context slice; fail closed."
            )


def resolve_effective_model(
    profile: SpecialistModelProfile,
    llm_settings: LlmSettings | None = None,
    fallback_id: str | None = None,
    available_capabilities: tuple[str, ...] = ("text",),
) -> tuple[str, str, dict[str, Any]]:
    """Resolve requested and effective model configuration with audit metadata."""
    for cap in profile.capabilities_required:
        if cap not in available_capabilities:
            raise PolicyViolationError(
                f"Capability rejection: Profile '{profile.profile_id}' requires capability '{cap}' "
                f"which is not available in provided environment ({available_capabilities}). "
                "No silent fallback."
            )

    requested_model = profile.model_id
    effective_model = profile.model_id
    effective_provider = profile.provider_adapter
    effective_revision = profile.model_revision

    is_fallback = False
    if fallback_id is not None:
        if fallback_id not in profile.fallback_profile_ids:
            raise PolicyViolationError(
                f"Explicit fallback rejection: fallback '{fallback_id}' is not permitted for "
                f"profile '{profile.profile_id}'. Allowed fallbacks: {profile.fallback_profile_ids}"
            )
        effective_model = fallback_id
        is_fallback = True

    metadata = {
        "role": profile.role.value,
        "profile_id": profile.profile_id,
        "profile_digest": profile.compute_digest(),
        "requested_model": requested_model,
        "effective_model": effective_model,
        "provider_adapter": effective_provider,
        "model_revision": effective_revision,
        "is_fallback": is_fallback,
        "reasoning_mode": profile.reasoning_mode,
        "context_limit": profile.context_limit,
        "max_output_tokens": profile.max_output_tokens,
        "timeout_ms": profile.timeout_ms,
        "budget_limit": profile.budget_limit,
        "endpoint_policy_ref": profile.endpoint_policy_ref,
        "credential_ref": profile.credential_ref,
        "data_classification": list(profile.data_classification_allowlist),
    }
    return requested_model, effective_model, metadata


def create_specialist_llm_client(
    profile: SpecialistModelProfile,
    base_settings: LlmSettings | None = None,
) -> LlmClient:
    """Instantiate an independent request-local LlmClient bound to the specialist profile."""
    settings = base_settings or LlmSettings(
        provider="local",
        model_name=profile.model_id,
        request_timeout_seconds=max(1, profile.timeout_ms // 1000),
    )
    role_name = profile.role.value.lower()
    return LlmClient(
        settings=settings,
        agent_identity=f"w_prod.{role_name}",
        model_identity=profile.model_id,
    )


def dispatch_specialist_s_val(
    sandbox_client: Any,
    specialist_task: SpecialistTask,
    parent_task: ProductEvidenceTask,
    egress_grant: SandboxEgressGrant | None = None,
) -> SpecialistResult:
    """Dispatch specialist task through existing S_VAL sandbox client under least privilege."""
    profile = get_specialist_profile(specialist_task.specialist_role)

    # 1. Validate profile digest and bindings
    validate_profile_binding(specialist_task, profile)

    # 2. Validate delegated scope attenuation
    validate_delegated_scope(parent_task, specialist_task, profile, egress_grant)

    # 3. Construct bounded payload
    role_str = specialist_task.specialist_role.value if hasattr(specialist_task.specialist_role, "value") else str(specialist_task.specialist_role)
    payload: dict[str, Any] = {
        "task_id": specialist_task.task_id,
        "tenant_id": specialist_task.tenant_id,
        "operation": specialist_task.operation,
        "specialist_role": role_str,
        "input_manifest": specialist_task.input_manifest,
        "context_slice": specialist_task.context_slice,
        "delegated_token_limit": specialist_task.delegated_token_limit,
    }

    if isinstance(specialist_task.context_slice, dict):
        for k, v in specialist_task.context_slice.items():
            if k not in payload:
                payload[k] = v

    if specialist_task.context_slice.get("vision_granted"):
        payload["vision_granted"] = True

    # 4. Formulate SandboxInvocationMandate
    mandate = SandboxInvocationMandate(
        task_id=specialist_task.task_id,
        tenant_id=specialist_task.tenant_id,
        worker_role=WorkerRole.PRODUCT_EVIDENCE,
        worker_id="W_PROD",
        capability=SandboxCapability.VAL,
        specialist_id=f"w_prod.{role_str.lower()}",
        specialist_agent=f"w_prod.{role_str.lower()}",
        operation=specialist_task.operation,
        payload=payload,
        allowed_tools=list(profile.allowed_tools),
        network_policy=NetworkPolicy.CONTROLLED if egress_grant else NetworkPolicy.DISABLED,
        egress_grant=egress_grant,
        resource_limits=ResourceLimits(
            timeout_seconds=max(1, profile.timeout_ms // 1000),
            memory_mb=512,
            cpu_cores=1.0,
        ),
        provenance_context={
            "profile_id": profile.profile_id,
            "profile_digest": profile.compute_digest(),
            "attempt_id": specialist_task.attempt_id,
        },
    )

    # 5. Invoke Sandbox
    try:
        import asyncio
        if hasattr(sandbox_client, "invoke"):
            try:
                loop = asyncio.get_running_loop()
                res = sandbox_client._execute_specialist(mandate)
            except RuntimeError:
                res = asyncio.run(sandbox_client.invoke(mandate))
        elif callable(sandbox_client):
            res = sandbox_client(mandate)
        else:
            raise SandboxInvocationError("Invalid sandbox client provided")
    except Exception as exc:
        return SpecialistResult(
            task_id=specialist_task.task_id,
            attempt_id=specialist_task.attempt_id,
            tenant_id=specialist_task.tenant_id,
            specialist_role=specialist_task.specialist_role,
            operation=specialist_task.operation,
            status=SpecialistResultStatus.FAILED,
            error_or_review_reasons=[str(exc)],
        )

    # Parse response
    structured_findings: dict[str, Any] = {}
    if isinstance(res, dict):
        raw_tf = res.get("typed_findings")
        if isinstance(raw_tf, str):
            try:
                structured_findings = json.loads(raw_tf)
            except Exception:
                structured_findings = {"raw": raw_tf}
        elif isinstance(raw_tf, dict):
            structured_findings = raw_tf
        else:
            structured_findings = res
    elif hasattr(res, "sanitized_payload"):
        structured_findings = res.sanitized_payload

    status = (
        SpecialistResultStatus.COMPLETED
        if (isinstance(res, dict) and res.get("status") in ("success", "completed", "compliance_warning")) or getattr(res, "success", False)
        else SpecialistResultStatus.FAILED
    )

    return SpecialistResult(
        task_id=specialist_task.task_id,
        attempt_id=specialist_task.attempt_id,
        tenant_id=specialist_task.tenant_id,
        specialist_role=specialist_task.specialist_role,
        operation=specialist_task.operation,
        status=status,
        typed_findings=structured_findings,
        usage={"attempt_id": specialist_task.attempt_id, "token_limit": specialist_task.delegated_token_limit},
        provenance_fragments={"profile_digest": profile.compute_digest(), "specialist_id": mandate.specialist_id},
    )
