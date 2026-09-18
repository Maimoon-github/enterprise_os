"""Typed schemas and contracts for DEV-UI (UI Layout & Component Sub-Agent - DE-08).

Defines structured UI templates, multi-viewport render evidence, automated WCAG 2.2 A/AA
accessibility audit findings, and tamper-evident candidate deliverable sealing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.agent_contracts import (
    CodeDiffEntry,
    ConfidenceInterval,
    DevelopmentDeliverable,
    ResponsiveBreakpoint,
    UITemplateDefinition,
)


class WcagSeverity(StrEnum):
    """Severity classification for automated accessibility findings."""

    CRITICAL = "CRITICAL"
    SERIOUS = "SERIOUS"
    MODERATE = "MODERATE"
    MINOR = "MINOR"
    PASS = "PASS"


class WcagFinding(BaseModel):
    """An individual WCAG 2.2 A/AA rule evaluation finding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    criterion: str
    description: str
    severity: WcagSeverity = WcagSeverity.PASS
    element_selector: str = ""
    is_passed: bool = True
    recommendation: str = ""


class UiAccessibilityReport(BaseModel):
    """Automated accessibility audit report targeting WCAG 2.2 A/AA criteria.

    IMPORTANT: Treated strictly as automated evidence of conformance,
    not full human screen-reader or assistive-technology certification.
    """

    model_config = ConfigDict(extra="forbid")

    target_standard: str = "WCAG 2.2 A/AA"
    rules_evaluated: int = 0
    rules_passed: int = 0
    compliance_score: float = 100.0
    findings: list[WcagFinding] = Field(default_factory=list)
    contrast_ratio_verified: bool = True
    keyboard_navigable_verified: bool = True
    aria_semantics_verified: bool = True
    manual_assessment_required: list[str] = Field(
        default_factory=lambda: [
            "WCAG 2.2 1.3.2 Meaningful Sequence (DOM and visual reading order)",
            "WCAG 2.2 2.1.2 No Keyboard Trap (manual tab/shift-tab cycle verification)",
            "WCAG 2.2 2.4.3 Focus Order (logical focus navigation with screen reader)",
            "WCAG 2.2 2.4.7 Focus Visible (custom indicator visual contrast)",
            "WCAG 2.2 3.1.2 Language of Parts (multilingual passage identification)",
            "WCAG 2.2 4.1.3 Status Messages (ARIA live region announcement verification)",
        ]
    )
    disclaimer: str = (
        "Automated scan provides evidence of WCAG 2.2 A/AA criteria adherence, "
        "but does not constitute comprehensive manual screen-reader or assistive-technology certification."
    )

    @property
    def is_accessible(self) -> bool:
        """Determines if all evaluated rules passed without critical/serious violations."""
        return self.compliance_score >= 90.0 and all(
            f.is_passed for f in self.findings if f.severity in (WcagSeverity.CRITICAL, WcagSeverity.SERIOUS)
        )

    @property
    def violations_count(self) -> int:
        return sum(1 for f in self.findings if not f.is_passed)


class UiViewportRender(BaseModel):
    """Render metrics and snapshot evidence for an individual viewport width."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    viewport_name: Literal["mobile", "tablet", "desktop"]
    width: int
    height: int
    render_status: Literal["SUCCESS", "RENDER_ERROR"] = "SUCCESS"
    dom_snapshot_hash: str = ""
    layout_metrics: dict[str, Any] = Field(default_factory=dict)
    console_errors: list[str] = Field(default_factory=list)


class UiRenderEvidence(BaseModel):
    """Multi-viewport localhost render simulation evidence inside the DE-03 sandbox."""

    model_config = ConfigDict(extra="forbid")

    viewports: list[UiViewportRender] = Field(default_factory=list)
    simulated_in_sandbox: bool = True
    sandbox_localhost_url: str = "http://localhost:3000/preview"
    zero_external_egress_verified: bool = True
    visual_snapshot_hash: str = ""
    dom_tree_summary: str = ""
    render_duration_ms: float = 0.0

    @property
    def all_viewports_rendered(self) -> bool:
        return len(self.viewports) >= 3 and all(v.render_status == "SUCCESS" for v in self.viewports)


class UiValidationEvidence(BaseModel):
    """Consolidated compilation, template, and contract validation evidence."""

    model_config = ConfigDict(extra="forbid")

    ast_valid: bool = True
    template_syntax_valid: bool = True
    style_syntax_valid: bool = True
    responsive_verified: bool = True
    cms_contract_compatible: bool = True
    validation_findings: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)


class UiCandidateDeliverable(BaseModel):
    """Complete sealed candidate deliverable produced by DEV-UI for DE-04 HITL review."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    task_id: str
    workflow_id: str
    attempt_id: str = "att-1"
    component_name: str
    templates: list[UITemplateDefinition] = Field(default_factory=list)
    css_styles: str = ""
    design_tokens: dict[str, str] = Field(default_factory=dict)
    code_diffs: list[CodeDiffEntry] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    render_evidence: UiRenderEvidence
    accessibility_report: UiAccessibilityReport
    validation_evidence: UiValidationEvidence
    cms_contract_hash: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    candidate_hash: str = ""
    rejection_feedback: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)

    @property
    def primary_template(self) -> UITemplateDefinition:
        if self.templates:
            return self.templates[0]
        return UITemplateDefinition(
            template_id=f"tmpl-{self.component_name.lower()}",
            name=self.component_name,
            template_markup="",
        )

    def canonical_bytes(self) -> bytes:
        """Return deterministic JSON-serialized byte representation of UI candidate deliverable."""
        canonical_templates = [
            {
                "template_id": t.template_id,
                "name": t.name,
                "component_type": t.component_type,
                "template_markup": t.template_markup.strip(),
                "css_styles": t.css_styles.strip(),
                "design_tokens": dict(sorted(t.design_tokens.items())),
                "props_schema": dict(sorted(t.props_schema.items())),
            }
            for t in sorted(self.templates, key=lambda x: x.template_id)
        ]
        canonical_diffs = [
            {
                "file_path": d.file_path,
                "action": d.action,
                "diff_unified": d.diff_unified.strip(),
            }
            for d in sorted(self.code_diffs, key=lambda x: x.file_path)
        ]
        canonical_payload = {
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "attempt_id": self.attempt_id,
            "component_name": self.component_name,
            "templates": canonical_templates,
            "css_styles": self.css_styles.strip(),
            "design_tokens": dict(sorted(self.design_tokens.items())),
            "code_diffs": canonical_diffs,
            "changed_files": sorted(self.changed_files),
            "cms_contract_hash": self.cms_contract_hash or "",
            "visual_snapshot_hash": self.render_evidence.visual_snapshot_hash,
            "compliance_score": round(self.accessibility_report.compliance_score, 2),
        }
        return json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_candidate_hash(self) -> str:
        """Compute SHA-256 tamper-evident digest of this UI candidate deliverable."""
        computed = hashlib.sha256(self.canonical_bytes()).hexdigest()
        self.candidate_hash = computed
        return computed

    def to_development_deliverable(self, tenant_id: str = "default") -> DevelopmentDeliverable:
        """Map to standard DevelopmentDeliverable for W_DEV engine result handoff."""
        return DevelopmentDeliverable(
            deliverable_id=f"dev-ui-{self.candidate_id}",
            tenant_id=tenant_id,
            task_id=self.task_id,
            component_name=self.component_name,
            ui_templates=self.templates,
            cms_schema_diffs=[],
            code_diffs=self.code_diffs,
            changed_files=self.changed_files,
            validation_findings=self.validation_evidence.validation_findings,
            security_checks_passed=self.render_evidence.zero_external_egress_verified,
            provenance={
                "candidate_id": self.candidate_id,
                "candidate_hash": self.candidate_hash or self.compute_candidate_hash(),
                "attempt_id": self.attempt_id,
                "subagent": "DEV-UI",
                **self.provenance,
            },
            confidence=ConfidenceInterval(
                point_estimate=0.95 if self.accessibility_report.is_accessible else 0.75,
                lower_bound=0.85,
                upper_bound=0.99,
            ),
        )
