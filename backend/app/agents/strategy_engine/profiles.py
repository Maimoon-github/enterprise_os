"""Authoritative cognitive profiles and session isolation for Strategy Engine (W_STRAT / S_ALLOC).

Provides an immutable specialist cognitive profile for S_ALLOC, with bounded sampling
parameters, strict data allowlists, disabled tool/network policies, and session factory
functions that guarantee isolated, non-leaking LLM clients.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.settings import LlmSettings
from app.integrations.llm.client import LlmClient
from app.schemas.sandbox import NetworkPolicy

S_ALLOC_SYSTEM_PROMPT = (
    "You are S_ALLOC, the Strategy Engine's media-and-budget reasoning specialist. "
    "Your reasoning is advisory only. You have no RAG, database, Intelligence Engine, "
    "internal API, campaign-platform, or credential access. You cannot grant permissions "
    "or tools. You cannot authorize spend, expand tenant or channel scope, change the "
    "supplied budget ceiling, or perform numerical allocation. Deterministic S_ALLOC "
    "tools own all calculations. Return only the declared structured schema; never "
    "expose private reasoning. Your role is to identify KPI priorities, bounded scenario "
    "emphasis, modeling assumptions, and risks for deterministic sandbox tools."
)


@dataclass(frozen=True)
class SpecialistModelProfile:
    """Immutable model, security, and capability profile for Strategy S_ALLOC specialist."""

    profile_id: str
    specialist_id: str
    profile_version: str = "1.0"
    prompt_version: str = "1.0.0"
    system_prompt: str = S_ALLOC_SYSTEM_PROMPT
    provider_adapter: str = "provider_neutral"
    model_id: str = "claude-3-5-sonnet"
    model_revision: str = "2024-10-22"
    reasoning_mode: str = "media_and_budget_allocation_reasoning"
    capabilities_required: tuple[str, ...] = ("text",)
    temperature_default: float = 0.0
    temperature_min: float = 0.0
    temperature_max: float = 0.5
    context_limit: int = 64000
    max_output_tokens: int = 4096
    timeout_ms: int = 45000
    max_attempts: int = 3
    data_classification_allowlist: tuple[str, ...] = ("internal", "public", "de_identified")
    allowed_tools: tuple[str, ...] = ()
    allowed_operations: tuple[str, ...] = ()
    network_policy: NetworkPolicy = NetworkPolicy.DISABLED
    endpoint_policy_ref: str = "policy:w_strat:s_alloc:v1"
    output_schema_name: str = "AllocationReasoningOutput"
    output_schema_version: str = "1.0"

    def compute_digest(self) -> str:
        """Compute deterministic SHA-256 canonical digest of this immutable profile."""
        payload: dict[str, Any] = {
            "allowed_operations": sorted(self.allowed_operations),
            "allowed_tools": sorted(self.allowed_tools),
            "capabilities_required": sorted(self.capabilities_required),
            "context_limit": self.context_limit,
            "data_classification_allowlist": sorted(self.data_classification_allowlist),
            "endpoint_policy_ref": self.endpoint_policy_ref,
            "max_attempts": self.max_attempts,
            "max_output_tokens": self.max_output_tokens,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "network_policy": (
                self.network_policy.value
                if isinstance(self.network_policy, NetworkPolicy)
                else str(self.network_policy)
            ),
            "output_schema_name": self.output_schema_name,
            "output_schema_version": self.output_schema_version,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "prompt_version": self.prompt_version,
            "provider_adapter": self.provider_adapter,
            "reasoning_mode": self.reasoning_mode,
            "specialist_id": self.specialist_id,
            "system_prompt": self.system_prompt,
            "temperature_default": self.temperature_default,
            "temperature_max": self.temperature_max,
            "temperature_min": self.temperature_min,
            "timeout_ms": self.timeout_ms,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def validate_temperature(self, temp: float) -> float:
        """Validate temperature is within profile allowed bounds."""
        if not (self.temperature_min <= temp <= self.temperature_max):
            raise ValueError(
                f"Temperature {temp} outside allowed bounds "
                f"[{self.temperature_min}, {self.temperature_max}] for {self.profile_id}"
            )
        return temp


S_ALLOC_PROFILE = SpecialistModelProfile(
    profile_id="w_strat.s_alloc.v1",
    specialist_id="s_alloc",
    system_prompt=S_ALLOC_SYSTEM_PROMPT,
    temperature_default=0.0,
    temperature_min=0.0,
    temperature_max=0.5,
    context_limit=64000,
    max_output_tokens=4096,
    timeout_ms=45000,
    network_policy=NetworkPolicy.DISABLED,
    allowed_tools=(),
    allowed_operations=(),
    output_schema_name="AllocationReasoningOutput",
    output_schema_version="1.0",
)


@dataclass(frozen=True)
class StrategyIdentityRecord:
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


def create_s_alloc_llm_client(
    profile: SpecialistModelProfile = S_ALLOC_PROFILE,
    *,
    base_settings: LlmSettings | None = None,
    tenant_id: str | None = None,
    client: httpx.AsyncClient | None = None,
    attempt_id: str | None = None,
    session_id: str | None = None,
    context_id: str | None = None,
    request_id: str | None = None,
) -> tuple[LlmClient, StrategyIdentityRecord]:
    """Instantiate a fresh, isolated LlmClient bound to the S_ALLOC specialist profile."""
    attempt = attempt_id or f"att-{uuid.uuid4().hex[:8]}"
    session = session_id or f"sess-{uuid.uuid4().hex[:8]}"
    ctx = context_id or f"ctx-{uuid.uuid4().hex[:8]}"
    req = request_id or f"req-{uuid.uuid4().hex[:8]}"
    client_inst = f"client-{uuid.uuid4().hex[:8]}"

    tenant_prefix = f"tenant-{tenant_id}." if tenant_id else ""
    agent_identity = f"{tenant_prefix}w_strat.{profile.specialist_id}.{client_inst}"

    settings = base_settings or LlmSettings(
        provider="local",
        model_name=profile.model_id,
        request_timeout_seconds=max(1, profile.timeout_ms // 1000),
    )

    llm_client = LlmClient(
        settings=settings,
        client=client,
        agent_identity=agent_identity,
        model_identity=profile.model_id,
        default_temperature=profile.temperature_default,
        default_max_output_tokens=profile.max_output_tokens,
    )

    identity_record = StrategyIdentityRecord(
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

    return llm_client, identity_record
