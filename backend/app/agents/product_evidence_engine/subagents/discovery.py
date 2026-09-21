"""w_prod.discovery: Product Evidence Discovery Specialist Sub-Agent.

Conducts systematic literature research, official rule gathering, and source metadata extraction.
Governed under least privilege: literature and official-rule web egress granted only via authorized SandboxEgressGrant.
Zero direct access to database, CMS, RAG, or parent runtime.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import re
from typing import Any, Literal
import uuid

from app.agents.product_evidence_engine.product_evidence import (
    DISCOVERY_PROFILE,
    SpecialistModelProfile,
    dispatch_specialist_s_val,
)
from app.schemas.product_evidence import (
    AccessLevel,
    EvidenceSubject,
    EvidenceType,
    ExtractedEvidence,
    FreshnessStatus,
    ProductEvidenceTask,
    ResearchProtocol,
    SearchRun,
    SourceRecord,
    SourceSnapshot,
    SpecialistResult,
    SpecialistResultStatus,
    SpecialistRole,
    SpecialistTask,
)
from app.schemas.sandbox import SandboxEgressGrant


class ProductDiscoveryAgent:
    """Specialist sub-agent for literature and rule discovery (w_prod.discovery).

    Implements PE-04: Systematic, reproducible, and bounded source acquisition
    under strict least privilege and disclosure safety.
    """

    SPECIALIST_ROLE = SpecialistRole.DISCOVERY
    SPECIALIST_ID = "w_prod.discovery"

    # Disclosure safety blacklist patterns
    CONFIDENTIAL_PATTERNS = (
        r"\b(secret|confidential|proprietary|unreleased|internal_batch|supplier_secret)\b",
        r"\b(batch-[a-zA-Z0-9_-]+)\b",
        r"\b\d+(\.\d+)?%\s+[a-zA-Z0-9_-]+\s+(active|peptide|formula|complex)\b",
    )

    def __init__(
        self,
        profile: SpecialistModelProfile | None = None,
        llm_client: Any = None,
        sandbox_client: Any = None,
    ) -> None:
        self._profile = profile or DISCOVERY_PROFILE
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

    def validate_protocol(self, protocol: ResearchProtocol | dict[str, Any]) -> ResearchProtocol:
        """Validate that an authorized ResearchProtocol contains all required specification elements."""
        if isinstance(protocol, dict):
            p = ResearchProtocol(**protocol)
        else:
            p = protocol

        if not p.protocol_id or not p.protocol_id.strip():
            raise ValueError("ResearchProtocol validation error: 'protocol_id' cannot be empty.")
        if not p.question_framing or not p.question_framing.strip():
            raise ValueError("ResearchProtocol validation error: 'question_framing' (atomic questions) cannot be empty.")
        if not p.inclusion_criteria:
            raise ValueError("ResearchProtocol validation error: 'inclusion_criteria' must contain at least one criterion.")
        if not p.exclusion_criteria:
            raise ValueError("ResearchProtocol validation error: 'exclusion_criteria' must contain at least one criterion.")
        if not p.search_syntax or not p.search_syntax.strip():
            raise ValueError("ResearchProtocol validation error: 'search_syntax' cannot be empty.")
        if not p.stopping_rules:
            raise ValueError("ResearchProtocol validation error: 'stopping_rules' must contain at least one stopping rule.")

        return p

    def sanitize_query(self, query: str, proprietary_terms: list[str] | None = None) -> str:
        """Enforce disclosure safety: ensure search queries do not leak confidential formulas or secrets."""
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("Search query cannot be empty.")

        # Check explicit proprietary terms
        if proprietary_terms:
            for term in proprietary_terms:
                if term and term.lower() in cleaned.lower():
                    raise ValueError(
                        f"Disclosure-safety violation: Query contains confidential proprietary term '{term}'."
                    )

        # Check confidential regex patterns
        for pattern in self.CONFIDENTIAL_PATTERNS:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                raise ValueError(
                    f"Disclosure-safety violation: Query matches confidential pattern '{pattern}': '{match.group(0)}'."
                )

        return cleaned

    def record_search_run(
        self,
        protocol_id: str,
        source_system_id: str,
        query: str,
        filters: dict[str, Any] | None = None,
        interface_version: str = "1.0",
        started_at_utc: datetime | None = None,
        completed_at_utc: datetime | None = None,
        pagination_cursor: str | None = None,
        results_count: int = 0,
        screened_count: int = 0,
        screening_outcomes: dict[str, int] | None = None,
        inaccessible_or_truncated_results: list[dict[str, str]] | None = None,
        stopping_reason: str = "saturation",
    ) -> SearchRun:
        """Record an auditable, reproducible SearchRun."""
        run_id = f"srun-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)
        return SearchRun(
            run_id=run_id,
            protocol_id=protocol_id,
            source_system_id=source_system_id,
            query=query,
            interface_version=interface_version,
            started_at_utc=started_at_utc or now,
            completed_at_utc=completed_at_utc or now,
            filters=filters or {},
            pagination_cursor=pagination_cursor,
            results_count=results_count,
            screened_count=screened_count,
            screening_outcomes=screening_outcomes or {"included": screened_count, "excluded": 0},
            inaccessible_or_truncated_results=inaccessible_or_truncated_results or [],
            stopping_reason=stopping_reason,
        )

    def capture_snapshot(
        self,
        source_id: str,
        content: bytes | str,
        requested_url: str,
        final_url: str | None = None,
        redirect_trace: list[str] | None = None,
        response_status: int = 200,
        media_type: str = "text/html",
        retrieval_activity_id: str | None = None,
        capture_tool_version: str = "1.0",
    ) -> SourceSnapshot:
        """Capture an immutable representation and content hash of retrieved document bytes."""
        content_bytes = content.encode("utf-8") if isinstance(content, str) else content
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
        activity_id = retrieval_activity_id or f"act-capture-{uuid.uuid4().hex[:8]}"

        return SourceSnapshot(
            snapshot_id=snapshot_id,
            source_id=source_id,
            content_hash=content_hash,
            media_type=media_type,
            byte_length=len(content_bytes),
            retrieval_activity_id=activity_id,
            requested_url=requested_url,
            final_url=final_url or requested_url,
            redirect_trace=redirect_trace or [],
            response_status=response_status,
            capture_tool_version=capture_tool_version,
            captured_at_utc=datetime.now(UTC),
        )

    def build_source_record(
        self,
        source_id: str,
        evidence_type: EvidenceType,
        access: AccessLevel,
        provenance_ref: str,
        url: str | None = None,
        identifier: str | None = None,
        issuer_or_authors: list[str] | None = None,
        title: str = "",
        jurisdiction: str = "not_applicable",
        language: str = "en",
        authenticity_status: Literal["verified", "partial", "unresolved", "compromised"] = "verified",
        freshness: FreshnessStatus = FreshnessStatus.CURRENT_CHECKED,
        snapshot_ref: str | None = None,
        rights_or_limitations: list[str] | None = None,
        correction_or_retraction_status: Literal["none", "corrected", "expression_of_concern", "retracted"] = "none",
        source_location: str = "",
        study_family_id: str = "",
        is_secondary_lead: bool = False,
        is_truncated_or_inaccessible: bool = False,
    ) -> SourceRecord:
        """Create a truthful SourceRecord. Never represent inaccessible full text as full_text."""
        effective_access = access
        if is_truncated_or_inaccessible and access == AccessLevel.FULL_TEXT:
            # Truthful reporting constraint: downgrade access level
            effective_access = AccessLevel.ABSTRACT_ONLY

        return SourceRecord(
            id=source_id,
            url=url,
            identifier=identifier,
            issuer_or_authors=issuer_or_authors or [],
            title=title,
            jurisdiction=jurisdiction,
            evidence_type=evidence_type,
            retrieved_at=datetime.now(UTC),
            access=effective_access,
            language=language,
            authenticity_status=authenticity_status,
            freshness=freshness,
            snapshot_ref=snapshot_ref,
            provenance_ref=provenance_ref,
            rights_or_limitations=rights_or_limitations or [],
            correction_or_retraction_status=correction_or_retraction_status,
            source_location=source_location,
            study_family_id=study_family_id,
            is_secondary_lead=is_secondary_lead,
        )

    def deduplicate_and_link_study_families(
        self,
        sources: list[SourceRecord],
    ) -> tuple[list[SourceRecord], list[dict[str, Any]]]:
        """Deduplicate identical records and link multiple reports belonging to the same study family.

        Preserves secondary reports with is_secondary_lead=True rather than deleting useful evidence.
        Prevents duplicate reports from inflating study counts.
        """
        deduped: list[SourceRecord] = []
        seen_keys: set[str] = set()
        study_families: dict[str, str] = {}  # family_id -> primary_source_id
        family_links: list[dict[str, Any]] = []

        for src in sources:
            # 1. Exact duplicate identification
            primary_key = (src.identifier or src.url or src.id).strip().lower()
            if primary_key in seen_keys:
                # Discard exact byte/identity duplicate
                continue
            seen_keys.add(primary_key)

            # 2. Study family grouping
            fam_id = src.study_family_id or src.identifier or src.id
            if fam_id in study_families:
                # Secondary report belonging to known study family
                updated_src = src.model_copy(
                    update={
                        "is_secondary_lead": True,
                        "study_family_id": fam_id,
                    }
                )
                deduped.append(updated_src)
                family_links.append({
                    "primary_source_id": study_families[fam_id],
                    "secondary_source_id": updated_src.id,
                    "study_family_id": fam_id,
                    "relationship": "secondary_report",
                })
            else:
                # Primary report of this family
                study_families[fam_id] = src.id
                updated_src = src.model_copy(
                    update={"study_family_id": fam_id, "is_secondary_lead": False}
                )
                deduped.append(updated_src)

        return deduped, family_links

    def extract_findings(
        self,
        source: SourceRecord,
        snapshot: SourceSnapshot,
        raw_findings: list[dict[str, Any]],
        activity_ref: str = "act-extract-001",
    ) -> list[ExtractedEvidence]:
        """Emit atomized extracts with precise locators.

        Preserves positive, negative, null, and safety evidence.
        Leaves certainty, final conflict resolution, and substantiation to downstream specialists.
        """
        extracted: list[ExtractedEvidence] = []
        for idx, finding in enumerate(raw_findings):
            ev_id = f"ev-{source.id}-{idx + 1}"
            outcome_text = str(finding.get("outcome", finding.get("finding", "Observed outcome")))
            subject_val = finding.get("subject", EvidenceSubject.INGREDIENT)
            if isinstance(subject_val, str):
                subject = EvidenceSubject(subject_val)
            else:
                subject = subject_val

            location = str(finding.get("location", "Unspecified section"))
            excerpt = str(finding.get("excerpt", outcome_text))
            extract_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()

            extracted.append(
                ExtractedEvidence(
                    id=ev_id,
                    source_id=source.id,
                    snapshot_ref=snapshot.snapshot_id,
                    location=location,
                    subject=subject,
                    outcome=outcome_text,
                    assessment_ref=f"assess-pending-{ev_id}",
                    activity_ref=activity_ref,
                    excerpt=excerpt,
                    extract_hash=extract_hash,
                    original_value=str(finding.get("original_value", "")),
                    normalized_value=str(finding.get("normalized_value", "")),
                    study_family_id=source.study_family_id,
                    study_design=str(finding.get("study_design", "Clinical observation")),
                    material_or_batch=str(finding.get("material_or_batch", "")),
                    population_or_subject_type=str(finding.get("population", "Human subjects")),
                    comparator=str(finding.get("comparator", "Placebo/Control")),
                    adverse_events=finding.get("adverse_events", []),
                    extraction_method="discovery_initial_extraction",
                )
            )
        return extracted

    def build_task(
        self,
        task_id: str,
        tenant_id: str,
        parent_task_id: str,
        operation: str = "research_literature",
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

    def execute_discovery(
        self,
        specialist_task: SpecialistTask,
        parent_task: ProductEvidenceTask,
        protocol: ResearchProtocol | None = None,
        egress_grant: SandboxEgressGrant | None = None,
    ) -> SpecialistResult:
        """Dispatch discovery execution via S_VAL sandbox runtime under governed egress."""
        if protocol is not None:
            validated_p = self.validate_protocol(protocol)
            specialist_task.context_slice["protocol"] = validated_p.model_dump(mode="json")
            if "query" in specialist_task.context_slice:
                specialist_task.context_slice["query"] = self.sanitize_query(
                    specialist_task.context_slice["query"]
                )

        return dispatch_specialist_s_val(
            self._sandbox_client,
            specialist_task=specialist_task,
            parent_task=parent_task,
            egress_grant=egress_grant,
        )
