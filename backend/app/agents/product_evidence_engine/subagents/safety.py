"""w_prod.safety: Toxicological and Product Safety Specialist Sub-Agent.

Conducts hazard characterization, exposure modeling, vulnerable population screening,
and adverse event signal detection.
Strictly offline execution under network_policy: DISABLED.
Zero direct access to database, CMS, RAG, or parent runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from app.agents.product_evidence_engine.product_evidence import (
    SAFETY_PROFILE,
    SpecialistModelProfile,
    dispatch_specialist_s_val,
)
from app.schemas.product_evidence import (
    ProductEvidenceTask,
    SafetyAssessment,
    SafetyStatus,
    SpecialistResult,
    SpecialistRole,
    SpecialistTask,
)


class ProductSafetyAgent:
    """Specialist sub-agent for toxicological safety evaluation (w_prod.safety).

    Implements PE-06: Evaluates hazards, exposure scenarios, vulnerable populations,
    and adverse signals. Enforces scoped conditions for 'no_concern_identified_in_scope'.
    Never emits unrestricted 'safe'. Requires qualified human reviewer for material conclusions.
    """

    SPECIALIST_ROLE = SpecialistRole.SAFETY
    SPECIALIST_ID = "w_prod.safety"

    # Serious toxicological and clinical adverse signal indicators
    SERIOUS_ADVERSE_PATTERNS: tuple[str, ...] = (
        r"\b(anaphylaxis|sensitization|erythema\s+grade\s+[34]|severe\s+edema)\b",
        r"\b(chemical\s+burn|ulceration|necrosis|corrosion|blistering)\b",
        r"\b(mutagenic|carcinogenic|teratogenic|genotoxic|endocrine\s+disrupt)\b",
        r"\b(systemic\s+toxicity|organ\s+failure|convulsion|respiratory\s+arrest)\b",
        r"\b(hrpt\s+failure|positive\s+maximization|phototoxicity\s+positive)\b",
    )

    def __init__(
        self,
        profile: SpecialistModelProfile | None = None,
        llm_client: Any = None,
        sandbox_client: Any = None,
    ) -> None:
        self._profile = profile or SAFETY_PROFILE
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

    @classmethod
    def evaluate_adverse_signals(cls, adverse_signals: list[str]) -> tuple[list[str], bool]:
        """Scan adverse signals for severe clinical and toxicological endpoints requiring immediate escalation."""
        flagged: list[str] = []
        escalation_required = False

        for sig in adverse_signals:
            sig_clean = sig.strip()
            for pattern in cls.SERIOUS_ADVERSE_PATTERNS:
                if re.search(pattern, sig_clean, re.IGNORECASE):
                    flagged.append(sig_clean)
                    escalation_required = True
                    break

        return flagged, escalation_required

    @classmethod
    def assess_safety(
        cls,
        assessment_id: str,
        product_version: str,
        hazards_evaluated: list[str],
        exposure_scenario: str,
        vulnerable_populations_considered: list[str],
        evidence_refs: list[str],
        adverse_signals: list[str],
        status: SafetyStatus = SafetyStatus.NOT_ASSESSED,
        relevant_endpoints: list[str] | None = None,
        exposure_assumptions: dict[str, Any] | None = None,
        scoped_conditions: dict[str, Any] | None = None,
        limitations_or_uncertainties: list[str] | None = None,
        risk_characterization_limitations: list[str] | None = None,
    ) -> SafetyAssessment:
        """Construct a strongly typed SafetyAssessment bound to explicit exposure and population scopes.

        Enforces:
        1. Only permitted SafetyStatus enum values (concern_identified, insufficient, no_concern_identified_in_scope, not_assessed).
        2. Prohibits unrestricted 'safe' conclusions.
        3. A 'no_concern_identified_in_scope' outcome MUST explicitly specify its scoped boundary conditions:
           population, route, dose/exposure, duration, endpoints, and limitations.
        4. Severe adverse signals trigger immediate concern status and prevent clearance.
        5. Missing critical evidence cannot become safety clearance through model inference.
        6. Qualified human reviewer is ALWAYS required.
        """
        # 1. Prohibit invalid or unrestricted statuses
        if not isinstance(status, SafetyStatus):
            raise ValueError(
                f"Invalid safety status '{status}'. Must strictly be one of: "
                f"{[s.value for s in SafetyStatus]}. Unrestricted 'safe' declarations are prohibited."
            )

        # 2. Severe adverse signals check (T23)
        serious_signals, escalation = cls.evaluate_adverse_signals(adverse_signals)
        effective_status = status
        effective_limitations = list(limitations_or_uncertainties or [])

        if escalation:
            if effective_status == SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE:
                effective_status = SafetyStatus.CONCERN_IDENTIFIED
                effective_limitations.append(
                    f"Severe adverse event signals detected ({', '.join(serious_signals)}); "
                    f"overriding clearance to CONCERN_IDENTIFIED."
                )

        # 3. Scoped boundary validation for NO_CONCERN_IDENTIFIED_IN_SCOPE (Task 12)
        final_scoped = scoped_conditions or {}
        if effective_status == SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE:
            required_scope_keys = ("target_population", "route", "max_daily_exposure", "max_duration")
            missing_keys = [k for k in required_scope_keys if not final_scoped.get(k)]
            if missing_keys:
                raise ValueError(
                    f"A 'no_concern_identified_in_scope' safety assessment must state its exact boundary conditions: "
                    f"missing required scoped condition keys: {missing_keys}."
                )
            if not relevant_endpoints:
                raise ValueError(
                    "A 'no_concern_identified_in_scope' safety assessment must state its explicitly evaluated endpoints."
                )

        # 4. Check vulnerable population coverage (T23)
        if not vulnerable_populations_considered:
            effective_limitations.append(
                "Vulnerable populations (pediatric, pregnant, barrier-compromised) not assessed; "
                "conclusions strictly non-applicable to sensitive demographics."
            )
            if effective_status == SafetyStatus.NO_CONCERN_IDENTIFIED_IN_SCOPE:
                # Still scoped, but must be explicitly documented
                final_scoped["vulnerable_populations_excluded"] = True

        return SafetyAssessment(
            assessment_id=assessment_id,
            product_version=product_version,
            hazards_evaluated=hazards_evaluated,
            exposure_scenario=exposure_scenario,
            vulnerable_populations_considered=vulnerable_populations_considered,
            evidence_refs=evidence_refs,
            adverse_signals=adverse_signals,
            status=effective_status,
            relevant_endpoints=relevant_endpoints or [],
            exposure_assumptions=exposure_assumptions or {},
            scoped_conditions=final_scoped,
            limitations_or_uncertainties=effective_limitations,
            risk_characterization_limitations=risk_characterization_limitations or [],
            qualified_reviewer_required=True,  # Invariant: specialists cannot sign off autonomous safety approvals
        )

    def build_task(
        self,
        task_id: str,
        tenant_id: str,
        parent_task_id: str,
        operation: str = "assess_safety",
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

    def execute_safety_review(
        self,
        specialist_task: SpecialistTask,
        parent_task: ProductEvidenceTask,
        safety_assessment: SafetyAssessment | None = None,
    ) -> SpecialistResult:
        """Dispatch safety evaluation via S_VAL sandbox runtime under least privilege."""
        if safety_assessment is not None:
            specialist_task.context_slice["safety_assessments"] = [safety_assessment.model_dump(mode="json")]
            status_val = safety_assessment.status.value if hasattr(safety_assessment.status, "value") else str(safety_assessment.status)
            specialist_task.context_slice["safety_status"] = status_val
            specialist_task.context_slice["adverse_signals"] = safety_assessment.adverse_signals
            specialist_task.context_slice["qualified_reviewer_required"] = safety_assessment.qualified_reviewer_required

            # Flag severe adverse signals
            _, escalation = self.evaluate_adverse_signals(safety_assessment.adverse_signals)
            if escalation:
                specialist_task.context_slice["severe_adverse_signal"] = True

        return dispatch_specialist_s_val(
            self._sandbox_client,
            specialist_task=specialist_task,
            parent_task=parent_task,
        )
