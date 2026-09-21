"""w_prod.regulatory: Regulatory Intelligence and Compliance Rules Specialist Sub-Agent.

Validates statutory requirements, verifies compliance rules across jurisdictions,
and maps rules to finished product propositions.
Governed under least privilege: official-rule web egress granted only via authorized SandboxEgressGrant.
Zero direct access to database, CMS, RAG, or parent runtime.
"""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

from app.agents.product_evidence_engine.product_evidence import (
    REGULATORY_PROFILE,
    SpecialistModelProfile,
    dispatch_specialist_s_val,
)
from app.schemas.product_evidence import (
    ClaimRecord,
    ProductEvidenceTask,
    RegulatoryRule,
    RuleApplication,
    RuleApplicationResult,
    RuleForce,
    RuleStatus,
    SpecialistResult,
    SpecialistRole,
    SpecialistTask,
)


class ProductRegulatoryAgent:
    """Specialist sub-agent for regulatory rules and statutory compliance (w_prod.regulatory).

    Implements PE-07:
    - Resolves authority, jurisdiction, product class, legal force, effective/transition/repeal dates.
    - Tags regulations, guidance, standards and organizational policy separately; guidance is never promoted to statute.
    - An unverified, superseded, future, or out-of-period rule cannot yield meets_checked_requirement.
    - Strict classification boundary: medicinal/disease claims on cosmetics yield does_not_meet_checked_requirement.
    - Scientific substantiation and regulatory compliance remain independent status axes.
    - Escalates therapeutic implications, apparent prohibitions, and legal uncertainty through HITL.
    """

    SPECIALIST_ROLE = SpecialistRole.REGULATORY
    SPECIALIST_ID = "w_prod.regulatory"

    def __init__(
        self,
        profile: SpecialistModelProfile | None = None,
        llm_client: Any = None,
        sandbox_client: Any = None,
    ) -> None:
        self._profile = profile or REGULATORY_PROFILE
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
    def verify_rule_currency_and_applicability(
        cls,
        rule: RegulatoryRule | dict[str, Any],
        target_jurisdiction: str,
        target_product_class: str,
        assessment_date: str = "2026-09-21",
    ) -> tuple[bool, str, RuleApplicationResult]:
        """Verify statutory currency, territory and product classification applicability (Tasks 10, 11, 12, 14, 15).

        Returns (is_applicable, reason, preliminary_outcome).
        """
        r_data = rule if isinstance(rule, dict) else rule.model_dump(mode="json")
        r_jurisdiction = str(r_data.get("jurisdiction", "")).upper()
        r_class = str(r_data.get("product_class", "cosmetics")).lower()
        r_status = str(r_data.get("status", "verified_applicable")).lower()
        r_force = str(r_data.get("force", "regulation")).lower()
        effective_from = r_data.get("effective_from")
        effective_to = r_data.get("effective_to")
        repeal_date = r_data.get("repeal_date")

        # 1. Jurisdiction match (Task 15)
        if r_jurisdiction != target_jurisdiction.upper() and r_jurisdiction != "GLOBAL":
            return False, f"Jurisdiction mismatch: rule applies to '{r_jurisdiction}', not target '{target_jurisdiction}'.", RuleApplicationResult.NOT_APPLICABLE

        # 2. Product class match (Task 12)
        if r_class != target_product_class.lower() and r_class != "all":
            return False, f"Product class mismatch: rule governs '{r_class}', not target '{target_product_class}'.", RuleApplicationResult.NOT_APPLICABLE

        # 3. Superseded status (Task 14)
        if r_status in ("superseded", "rule_status.superseded"):
            return False, "Rule is superseded and no longer in force; cannot produce a compliance pass.", RuleApplicationResult.NOT_APPLICABLE

        # 4. Temporal boundaries: Effective from (Future/Commencement) and Repeal Date (Task 14)
        if effective_from and effective_from > assessment_date:
            return False, f"Rule commencement date '{effective_from}' is in the future relative to assessment date '{assessment_date}'. Publication does not equal commencement.", RuleApplicationResult.UNKNOWN

        if (repeal_date and repeal_date <= assessment_date) or (effective_to and effective_to <= assessment_date):
            return False, f"Rule was repealed or expired prior to assessment date '{assessment_date}'.", RuleApplicationResult.NOT_APPLICABLE

        # 5. Unverified / Pending status (Task 14)
        if r_status in ("unverified", "pending"):
            return False, "Rule text or legal currency is unverified; cannot produce a compliance pass.", RuleApplicationResult.UNKNOWN

        return True, "Rule is operative, verified, and applicable.", RuleApplicationResult.MEETS_CHECKED_REQUIREMENT

    @classmethod
    def apply_rule_to_claim(
        cls,
        rule: RegulatoryRule | dict[str, Any],
        claim: ClaimRecord | dict[str, Any],
        target_jurisdiction: str = "US",
        target_product_class: str = "cosmetics",
        assessment_date: str = "2026-09-21",
        evidence_refs: Sequence[str] | None = None,
        intended_use: str = "Topical leave-on cosmetic skin conditioning",
    ) -> RuleApplication:
        """Apply regulatory rule to a specific claim or product (Tasks 12, 13, 14, 16, 17, 18).

        Returns RuleApplication with outcome restricted strictly to:
        meets_checked_requirement, does_not_meet_checked_requirement, unknown, not_applicable.
        """
        r_data = rule if isinstance(rule, dict) else rule.model_dump(mode="json")
        c_data = claim if isinstance(claim, dict) else claim.model_dump(mode="json")

        rule_id = str(r_data.get("id", "rule-unknown"))
        claim_id = str(c_data.get("id", "claim-unknown"))
        claim_text = str(c_data.get("text", "")).lower()
        rule_force = str(r_data.get("force", "regulation")).lower()

        app_id = f"app-{hashlib.sha256(f'{rule_id}:{claim_id}'.encode()).hexdigest()[:10]}"

        # Step 1: Currency and applicability check
        is_applicable, check_reason, prelim_outcome = cls.verify_rule_currency_and_applicability(
            rule=r_data,
            target_jurisdiction=target_jurisdiction,
            target_product_class=target_product_class,
            assessment_date=assessment_date,
        )

        if not is_applicable:
            return RuleApplication(
                application_id=app_id,
                target_id=claim_id,
                rule_id=rule_id,
                jurisdiction=target_jurisdiction,
                product_class=target_product_class,
                outcome=prelim_outcome,
                assessment_date=assessment_date,
                intended_use=intended_use,
                escalation_required=prelim_outcome == RuleApplicationResult.UNKNOWN,
                evidence_refs=list(evidence_refs or []),
                reason=check_reason,
                severity_if_breached="low",
            )

        # Step 2: Legal Force distinction (Task 11) - Guidance vs Statute
        if rule_force == "guidance" or rule_force == "ruleforce.guidance":
            # Tagged as guidance; non-binding guidance cannot be promoted to statute
            guidance_note = "Evaluated against non-binding administrative guidance; does not establish statutory obligation."
        else:
            guidance_note = "Evaluated against legally binding statute/regulation."

        # Step 3: Disease / Therapeutic Claim on Cosmetic Class (Tasks 10, 18)
        # Cosmetics regulations strictly prohibit treating, curing, or preventing disease
        disease_terms = ("treats eczema", "cures psoriasis", "heals dermatitis", "prevents infection", "reverses acne vulgaris", "curative")
        if target_product_class.lower() == "cosmetics" and any(d in claim_text for d in disease_terms):
            return RuleApplication(
                application_id=app_id,
                target_id=claim_id,
                rule_id=rule_id,
                jurisdiction=target_jurisdiction,
                product_class=target_product_class,
                outcome=RuleApplicationResult.DOES_NOT_MEET_CHECKED_REQUIREMENT,
                assessment_date=assessment_date,
                intended_use=intended_use,
                escalation_required=True,
                evidence_refs=list(evidence_refs or []),
                reason=(
                    f"Statutory border violation: Claim '{c_data.get('text')}' conveys medicinal/disease mitigation properties "
                    f"prohibited for cosmetic product classification under {r_data.get('source_id', 'applicable regulation')}."
                ),
                severity_if_breached="critical",
            )

        # Step 4: Evidential substantiation check (EU 655/2013 Criterion 3 or US FTC/FDA substantiation)
        # If claim status is INSUFFICIENT or CONFLICTED, it fails the checked substantiation requirement
        c_status = str(c_data.get("status", "supported_in_scope")).lower()
        if "insufficient" in c_status or "conflicted" in c_status:
            return RuleApplication(
                application_id=app_id,
                target_id=claim_id,
                rule_id=rule_id,
                jurisdiction=target_jurisdiction,
                product_class=target_product_class,
                outcome=RuleApplicationResult.DOES_NOT_MEET_CHECKED_REQUIREMENT,
                assessment_date=assessment_date,
                intended_use=intended_use,
                escalation_required=True,
                evidence_refs=list(evidence_refs or []),
                reason="Claim lacks adequate and verifiable scientific substantiation required by statutory standard.",
                severity_if_breached="high",
            )

        # Step 5: Conforms to checked requirement
        return RuleApplication(
            application_id=app_id,
            target_id=claim_id,
            rule_id=rule_id,
            jurisdiction=target_jurisdiction,
            product_class=target_product_class,
            outcome=RuleApplicationResult.MEETS_CHECKED_REQUIREMENT,
            assessment_date=assessment_date,
            intended_use=intended_use,
            escalation_required=False,
            evidence_refs=list(evidence_refs or []),
            reason=f"Claim meets verified requirement under {r_data.get('source_id', 'statute')}. {guidance_note}",
            severity_if_breached="medium",
        )

    def build_task(
        self,
        task_id: str,
        tenant_id: str,
        parent_task_id: str,
        operation: str = "check_regulatory_rules",
        context_slice: dict[str, Any] | None = None,
        input_manifest: list[str] | None = None,
        delegated_token_limit: int = 5000,
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

    def execute_regulatory_check(
        self,
        specialist_task: SpecialistTask,
        parent_task: ProductEvidenceTask,
        rules: Sequence[RegulatoryRule] | None = None,
        applications: Sequence[RuleApplication] | None = None,
    ) -> SpecialistResult:
        """Dispatch regulatory rules check via S_VAL sandbox runtime under least privilege."""
        if rules is not None:
            specialist_task.context_slice["regulatory_rules"] = [r.model_dump(mode="json") for r in rules]

        if applications is not None:
            specialist_task.context_slice["rule_applications"] = [a.model_dump(mode="json") for a in applications]
            all_passed = all(a.outcome == RuleApplicationResult.MEETS_CHECKED_REQUIREMENT for a in applications)
            specialist_task.context_slice["regulatory_status"] = (
                "MEETS_CHECKED_REQUIREMENT" if all_passed else "DOES_NOT_MEET_CHECKED_REQUIREMENT"
            )
            specialist_task.context_slice["escalation_required"] = any(a.escalation_required for a in applications)

            # Detect regulatory invariant violation flags
            if any(a.outcome == RuleApplicationResult.DOES_NOT_MEET_CHECKED_REQUIREMENT and a.severity_if_breached == "critical" for a in applications):
                specialist_task.context_slice["disease_claim_on_cosmetic"] = True

        return dispatch_specialist_s_val(
            self._sandbox_client,
            specialist_task=specialist_task,
            parent_task=parent_task,
        )
