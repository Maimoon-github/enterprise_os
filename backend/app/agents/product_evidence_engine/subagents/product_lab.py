"""w_prod.product_lab: Formulation and Laboratory Audit Specialist Sub-Agent.

Validates finished product formulation specifications, audits analytical lab certificates,
and verifies test method accreditation.
Strictly offline execution under network_policy: DISABLED.
Zero direct access to database, CMS, RAG, or parent runtime.
"""

from __future__ import annotations

from typing import Any

from app.agents.product_evidence_engine.product_evidence import (
    PRODUCT_LAB_PROFILE,
    SpecialistModelProfile,
)
from app.schemas.product_evidence import SpecialistRole, SpecialistTask


class ProductLabAgent:
    """Specialist sub-agent for formulation and lab verification (w_prod.product_lab)."""

    SPECIALIST_ROLE = SpecialistRole.PRODUCT_LAB
    SPECIALIST_ID = "w_prod.product_lab"

    def __init__(
        self,
        profile: SpecialistModelProfile | None = None,
        llm_client: Any = None,
        sandbox_client: Any = None,
    ) -> None:
        self._profile = profile or PRODUCT_LAB_PROFILE
        self._llm_client = llm_client
        self._sandbox_client = sandbox_client

    @property
    def role(self) -> SpecialistRole:
        return self.SPECIALIST_ROLE

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    @property
    def profile(self) -> SpecialistModelProfile:
        return self._profile

    @property
    def allowed_operations(self) -> tuple[str, ...]:
        return self._profile.allowed_operations

    @property
    def allowed_tools(self) -> tuple[str, ...]:
        return self._profile.allowed_tools

    @property
    def llm_client(self) -> Any:
        return self._llm_client

    @property
    def sandbox_client(self) -> Any:
        return self._sandbox_client

    def build_task(
        self,
        task_id: str,
        tenant_id: str,
        parent_task_id: str,
        operation: str = "validate_formulation",
        context_slice: dict[str, Any] | None = None,
        input_manifest: list[str] | None = None,
        delegated_token_limit: int = 4000,
        policy_refs: list[str] | None = None,
        attempt_id: str = "1",
    ) -> SpecialistTask:
        """Construct strongly typed SpecialistTask for S_VAL execution."""
        return SpecialistTask(
            task_id=task_id,
            tenant_id=tenant_id,
            parent_task_id=parent_task_id,
            specialist_role=self.SPECIALIST_ROLE,
            operation=operation,
            input_manifest=input_manifest or [],
            context_slice=context_slice or {},
            profile_ref=self._profile.profile_id,
            profile_version=self._profile.profile_version,
            profile_digest=self._profile.compute_digest(),
            delegated_token_limit=min(delegated_token_limit, self._profile.budget_limit_tokens),
            policy_refs=policy_refs or [self._profile.endpoint_policy_ref],
            attempt_id=attempt_id,
        )
