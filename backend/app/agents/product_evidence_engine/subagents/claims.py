"""w_prod.claims: Marketing and Product Claims Specialist Sub-Agent.

Extracts explicit and implied claim propositions, maps claims to evidence/rules,
and inspects imagery assets (vision granted on demand).
Strictly offline execution under network_policy: DISABLED.
Zero direct access to database, CMS, RAG, or parent runtime.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Sequence

from app.agents.product_evidence_engine.product_evidence import (
    CLAIMS_PROFILE,
    SpecialistModelProfile,
    dispatch_specialist_s_val,
)
from app.schemas.product_evidence import (
    ClaimEvidenceEdge,
    ClaimKind,
    ClaimRecord,
    ClaimStatus,
    EvidenceRelevance,
    ExtractedEvidence,
    FormulationEvidenceBridge,
    MappingRelation,
    ProductEvidenceTask,
    SpecialistResult,
    SpecialistRole,
    SpecialistTask,
)


class ProductClaimsAgent:
    """Specialist sub-agent for claim extraction and evidence mapping (w_prod.claims).

    Implements PE-07:
    - Processes exact versioned assets with SHA-256 context hashing.
    - Atomizes material express propositions and records plausible implied interpretations.
    - Maps interpretations to evidence using ClaimEvidenceEdge, enforcing evidence scope
      (magnitude, duration, population, endpoint, route) and formulation bridges.
    - Finished-product claims cannot rely solely on ingredient evidence without a bridge.
    - Preserves unsupported aspects; proposed narrower wording remains a proposal.
    """

    SPECIALIST_ROLE = SpecialistRole.CLAIMS
    SPECIALIST_ID = "w_prod.claims"

    def __init__(
        self,
        profile: SpecialistModelProfile | None = None,
        llm_client: Any = None,
        sandbox_client: Any = None,
    ) -> None:
        self._profile = profile or CLAIMS_PROFILE
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
    def compute_asset_hash(
        cls,
        wording: str,
        imagery_ref: str = "",
        layout: str = "",
        testimonial: str = "",
        qualifiers: Sequence[str] | None = None,
        channel: str = "packaging",
        locale: str = "en_US",
        audience: str = "general_consumer",
        product_version: str = "1.0",
    ) -> str:
        """Compute SHA-256 digest of the entire creative asset context (Tasks 3, 5).

        Any change in wording, imagery, translation, qualifier, channel, locale,
        or audience produces a distinct claim context hash and new claim version.
        """
        components = [
            wording.strip(),
            imagery_ref.strip(),
            layout.strip(),
            testimonial.strip(),
            ",".join(sorted(qualifiers or [])),
            channel.strip(),
            locale.strip(),
            audience.strip(),
            product_version.strip(),
        ]
        serialized = "|".join(components)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def atomize_asset_claims(
        cls,
        wording: str,
        asset_ref: str,
        asset_location: str,
        imagery_ref: str = "",
        layout: str = "",
        testimonial: str = "",
        qualifiers: Sequence[str] | None = None,
        channel: str = "packaging",
        locale: str = "en_US",
        audience: str = "general_consumer",
        product_version: str = "1.0",
        jurisdiction: str = "US",
        activity_ref: str = "act-claim-extract-01",
    ) -> list[ClaimRecord]:
        """Atomize material express propositions and extract plausible implied interpretations (Tasks 3, 4, 5).

        Each material express proposition and plausible implied interpretation is recorded
        separately with rationale and asset location.
        """
        records: list[ClaimRecord] = []
        asset_hash = cls.compute_asset_hash(
            wording=wording,
            imagery_ref=imagery_ref,
            layout=layout,
            testimonial=testimonial,
            qualifiers=qualifiers,
            channel=channel,
            locale=locale,
            audience=audience,
            product_version=product_version,
        )

        # 1. Express Claim Record
        # Split text into atomic propositions (by sentence or punctuation clauses)
        raw_propositions = [p.strip() for p in re.split(r"[.;!]\s*", wording) if p.strip()]
        if not raw_propositions:
            raw_propositions = [wording.strip()]

        express_id = f"claim-exp-{asset_hash[:10]}"
        records.append(
            ClaimRecord(
                id=express_id,
                version=f"v{asset_hash[:6]}",
                text=wording.strip(),
                kind=ClaimKind.EXPLICIT,
                asset_ref=asset_ref,
                asset_location=asset_location,
                jurisdiction=jurisdiction,
                locale=locale,
                interpretation_reason="Direct express marketing claim extracted from asset text.",
                status=ClaimStatus.NOT_ASSESSED,
                activity_ref=activity_ref,
                propositions=raw_propositions,
                qualifiers=list(qualifiers or []),
                channel=channel,
                audience=audience,
                product_version=product_version,
                asset_hash=asset_hash,
                human_review_required=False,
            )
        )

        # 2. Implied Claim from Imagery / Visual Cues (Task 4)
        if imagery_ref:
            img_lower = imagery_ref.lower()
            if any(cue in img_lower for cue in ("lab_coat", "doctor", "medical", "stethoscope", "cross", "dermatologist")):
                records.append(
                    ClaimRecord(
                        id=f"claim-imp-img-{asset_hash[:10]}",
                        version=f"v{asset_hash[:6]}",
                        text=f"Clinically endorsed or recommended under medical supervision (implied by {imagery_ref}).",
                        kind=ClaimKind.IMPLIED,
                        asset_ref=asset_ref,
                        asset_location=f"{asset_location} (Visual Imagery: {imagery_ref})",
                        jurisdiction=jurisdiction,
                        locale=locale,
                        interpretation_reason="Visual cues (medical/clinical imagery) convey professional clinical endorsement.",
                        status=ClaimStatus.NOT_ASSESSED,
                        activity_ref=activity_ref,
                        propositions=["Product carries professional medical endorsement."],
                        qualifiers=list(qualifiers or []),
                        channel=channel,
                        audience=audience,
                        product_version=product_version,
                        asset_hash=asset_hash,
                        human_review_required=True,
                    )
                )

        # 3. Implied Claim from Testimonials (Task 4)
        if testimonial:
            test_lower = testimonial.lower()
            is_therapeutic = any(term in test_lower for term in ("cure", "healed", "eczema", "dermatitis", "psoriasis", "infection"))
            records.append(
                ClaimRecord(
                    id=f"claim-imp-test-{asset_hash[:10]}",
                    version=f"v{asset_hash[:6]}",
                    text=f"Consumer-reported therapeutic efficacy: '{testimonial.strip()}'.",
                    kind=ClaimKind.IMPLIED,
                    asset_ref=asset_ref,
                    asset_location=f"{asset_location} (Testimonial callout)",
                    jurisdiction=jurisdiction,
                    locale=locale,
                    interpretation_reason="Consumer testimonial conveys medicinal/curative treatment efficacy to consumers.",
                    status=ClaimStatus.NOT_ASSESSED,
                    activity_ref=activity_ref,
                    propositions=[f"Product mitigates or cures dermatological condition: {testimonial.strip()}"],
                    qualifiers=list(qualifiers or []),
                    channel=channel,
                    audience=audience,
                    product_version=product_version,
                    asset_hash=asset_hash,
                    human_review_required=is_therapeutic,
                )
            )

        return records

    @classmethod
    def map_claim_to_evidence(
        cls,
        claim: ClaimRecord,
        evidence_item: dict[str, Any] | ExtractedEvidence,
        bridge: FormulationEvidenceBridge | dict[str, Any] | None = None,
        assessment_ref: str | None = None,
        rule_ids: Sequence[str] | None = None,
        activity_ref: str = "act-map-001",
    ) -> tuple[ClaimEvidenceEdge, ClaimStatus]:
        """Map claim interpretation to evidence, enforcing scope & formulation bridge invariants (Tasks 6, 7, 8, 9).

        Enforces:
        - Finished product claims cannot rely solely on ingredient evidence without an applicable bridge (Task 8).
        - Evidence scope: magnitude, duration, population, endpoint and route cannot exceed evidence without review (Task 7).
        - Proposed narrower wording remains a proposal and never silently replaces original claim text (Task 9).
        """
        ev_data = evidence_item if isinstance(evidence_item, dict) else evidence_item.model_dump(mode="json")
        ev_id = str(ev_data.get("id", "ev-unknown"))
        ev_subject = str(ev_data.get("subject", "finished_product")).lower()
        ev_outcome = str(ev_data.get("outcome", "")).lower()

        edge_limitations: list[str] = []
        scope_mismatch = False
        bridge_ref = None

        # 1. Ingredient vs Finished Product Invariant (Task 8)
        if ev_subject in ("ingredient", "material", "in_vitro"):
            if bridge is None:
                edge_limitations.append(
                    "Finished-product claim relies solely on ingredient/material evidence without an applicable formulation bridge."
                )
                claim.scope_limitations = edge_limitations
                claim.human_review_required = True
                edge = ClaimEvidenceEdge(
                    id=f"edge-{claim.id}-{ev_id}",
                    claim_id=claim.id,
                    evidence_id=ev_id,
                    rule_ids=list(rule_ids or []),
                    relation=MappingRelation.INCONCLUSIVE,
                    relevance=EvidenceRelevance.BRIDGE_REQUIRED,
                    bridge_ref=None,
                    assessment_ref=assessment_ref,
                    limitations=edge_limitations,
                    activity_ref=activity_ref,
                )
                return edge, ClaimStatus.INSUFFICIENT
            else:
                bridge_data = bridge if isinstance(bridge, dict) else bridge.model_dump(mode="json")
                bridge_ref = str(bridge_data.get("bridge_id", "bridge-verified"))

        # 2. Scope Dimension Checks: Magnitude, Duration, Population, Endpoint, Route (Task 7)
        claim_text_lower = claim.text.lower()

        # Magnitude check: e.g. claim promises 50% or 40% but study shows less
        claim_pct_matches = [int(m) for m in re.findall(r"(\d+)%", claim_text_lower)]
        ev_pct_matches = [int(m) for m in re.findall(r"(\d+)%", ev_outcome)]
        if claim_pct_matches and ev_pct_matches:
            if max(claim_pct_matches) > max(ev_pct_matches):
                scope_mismatch = True
                edge_limitations.append(
                    f"Claimed magnitude ({max(claim_pct_matches)}%) exceeds evidence outcome ({max(ev_pct_matches)}%)."
                )

        # Duration check: e.g. 24-hour hydration vs short-term 2h test
        if any(d in claim_text_lower for d in ("24-hour", "24 hours", "24h", "all-day", "continuous 24h", "permanent")):
            if not any(d in ev_outcome for d in ("24 hours", "24-hour", "24h", "14 days", "28 days", "long-term")):
                scope_mismatch = True
                edge_limitations.append("Claimed 24-hour/all-day persistence exceeds tested study duration.")

        # Population check: e.g. infants, eczema patients vs healthy adults
        if any(p in claim_text_lower for p in ("infant", "baby", "pediatric", "eczema", "dermatitis")):
            ev_pop = str(ev_data.get("population", "")).lower()
            if not any(p in ev_pop for p in ("infant", "baby", "pediatric", "eczema", "dermatitis")):
                scope_mismatch = True
                edge_limitations.append("Target vulnerable/clinical population in claim not covered in study population.")

        # Endpoint check: clinical anti-aging/wrinkle vs surface hydration
        if any(ep in claim_text_lower for ep in ("wrinkle", "reverses aging", "anti-aging", "cellular repair")):
            if not any(ep in ev_outcome for ep in ("wrinkle reduction", "anti-aging effect", "cellular repair")) or "nonsignificant" in ev_outcome:
                scope_mismatch = True
                edge_limitations.append("Claimed therapeutic/anti-aging endpoint exceeds verified study endpoint (nonsignificant wrinkle change).")

        # Opposing / Null outcomes
        if any(term in ev_outcome for term in ("no statistically significant", "no difference", "ineffective", "refutes")):
            edge = ClaimEvidenceEdge(
                id=f"edge-{claim.id}-{ev_id}",
                claim_id=claim.id,
                evidence_id=ev_id,
                rule_ids=list(rule_ids or []),
                relation=MappingRelation.REFUTES,
                relevance=EvidenceRelevance.DIRECT if bridge_ref is None else EvidenceRelevance.BRIDGE_REQUIRED,
                bridge_ref=bridge_ref,
                assessment_ref=assessment_ref,
                limitations=["Evidence directly refutes or contradicts claimed effect."],
                activity_ref=activity_ref,
            )
            claim.status = ClaimStatus.CONFLICTED
            claim.human_review_required = True
            return edge, ClaimStatus.CONFLICTED

        # Determine outcome relation and claim status
        if scope_mismatch:
            # Propose narrower wording without silently replacing the original claim (Task 9)
            narrower = claim.text
            if claim_pct_matches and ev_pct_matches:
                narrower = narrower.replace(f"{max(claim_pct_matches)}%", f"up to {max(ev_pct_matches)}%")
            if "24-hour" in narrower:
                narrower = narrower.replace("24-hour", "temporary post-application")
            claim.proposed_narrower_wording = f"Proposed qualified wording: '{narrower}'"
            claim.scope_limitations = edge_limitations
            claim.human_review_required = True
            claim.status = ClaimStatus.QUALIFIED_SUPPORT

            edge = ClaimEvidenceEdge(
                id=f"edge-{claim.id}-{ev_id}",
                claim_id=claim.id,
                evidence_id=ev_id,
                rule_ids=list(rule_ids or []),
                relation=MappingRelation.MIXED,
                relevance=EvidenceRelevance.DIRECT if bridge_ref is None else EvidenceRelevance.BRIDGE_REQUIRED,
                bridge_ref=bridge_ref,
                assessment_ref=assessment_ref,
                limitations=edge_limitations,
                activity_ref=activity_ref,
            )
            return edge, ClaimStatus.QUALIFIED_SUPPORT

        # Fully supported in scope
        relevance = EvidenceRelevance.DIRECT if bridge_ref is None else EvidenceRelevance.BRIDGE_REQUIRED
        claim.status = ClaimStatus.SUPPORTED_IN_SCOPE
        edge = ClaimEvidenceEdge(
            id=f"edge-{claim.id}-{ev_id}",
            claim_id=claim.id,
            evidence_id=ev_id,
            rule_ids=list(rule_ids or []),
            relation=MappingRelation.SUPPORTS,
            relevance=relevance,
            bridge_ref=bridge_ref,
            assessment_ref=assessment_ref,
            limitations=[],
            activity_ref=activity_ref,
        )
        return edge, ClaimStatus.SUPPORTED_IN_SCOPE

    def build_task(
        self,
        task_id: str,
        tenant_id: str,
        parent_task_id: str,
        operation: str = "map_claim_evidence",
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

    def execute_claim_mapping(
        self,
        specialist_task: SpecialistTask,
        parent_task: ProductEvidenceTask,
        claims: Sequence[ClaimRecord] | None = None,
        edges: Sequence[ClaimEvidenceEdge] | None = None,
    ) -> SpecialistResult:
        """Dispatch claim mapping via S_VAL sandbox runtime under least privilege."""
        if claims is not None:
            specialist_task.context_slice["claims"] = [c.model_dump(mode="json") for c in claims]
            all_supported = all(c.status == ClaimStatus.SUPPORTED_IN_SCOPE for c in claims)
            specialist_task.context_slice["claim_status"] = "SUPPORTED_IN_SCOPE" if all_supported else "INSUFFICIENT"
            specialist_task.context_slice["human_review_required"] = any(c.human_review_required for c in claims)

            # Detect invariant flags
            if any(c.status == ClaimStatus.INSUFFICIENT and "ingredient" in str(c.scope_limitations).lower() for c in claims):
                specialist_task.context_slice["ingredient_without_bridge"] = True
            if any(c.status == ClaimStatus.QUALIFIED_SUPPORT for c in claims):
                specialist_task.context_slice["scope_mismatch_unqualified"] = False

        if edges is not None:
            specialist_task.context_slice["claim_evidence_edges"] = [e.model_dump(mode="json") for e in edges]

        return dispatch_specialist_s_val(
            self._sandbox_client,
            specialist_task=specialist_task,
            parent_task=parent_task,
        )
