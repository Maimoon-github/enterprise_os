"""Schemas for development execution plans and ordered sub-agent steps (DE-06)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.exceptions import PolicyViolationError

# Canonical Sub-Agent IDs for W_DEV
SUBAGENT_CMS = "DEV-CMS"
SUBAGENT_UI = "DEV-UI"
SUBAGENT_CODE = "DEV-CODE"
SUBAGENT_VERIFY = "DEV-VERIFY"
SUBAGENT_SEC = "DEV-SEC"
SUBAGENT_REL = "DEV-REL"

MANDATORY_RELEASE_SUBAGENTS = frozenset({SUBAGENT_VERIFY, SUBAGENT_SEC, SUBAGENT_REL})
CONDITIONALLY_EXCLUDABLE_SUBAGENTS = frozenset({SUBAGENT_CMS, SUBAGENT_UI, SUBAGENT_CODE})


class DevelopmentPlanStep(BaseModel):
    """An individual ordered step in a development execution plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    subagent_id: str
    order: int = 1
    name: str = ""
    description: str = ""
    status: Literal["REQUIRED", "SKIPPED_NOT_APPLICABLE"] = "REQUIRED"
    skip_reason: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    affected_artifacts: list[str] = Field(default_factory=list)
    risk_class: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    acceptance_criteria: list[str] = Field(default_factory=list)
    is_applicable: bool = True

    @property
    def subagent(self) -> str:
        """Alias for subagent_id."""
        return self.subagent_id

    @model_validator(mode="before")
    @classmethod
    def _normalize_subagent(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "subagent" in data and "subagent_id" not in data:
                data["subagent_id"] = data.pop("subagent")
            if "name" not in data or not data["name"]:
                data["name"] = data.get("description", "") or data.get("subagent_id", "step")
        return data

    @model_validator(mode="after")
    def validate_skip_contract(self) -> DevelopmentPlanStep:
        """Enforce explicit skip justification and sync is_applicable flag."""
        if self.status == "SKIPPED_NOT_APPLICABLE":
            if not self.skip_reason or not self.skip_reason.strip():
                raise ValueError(
                    f"Step '{self.step_id}' ({self.subagent_id}) is marked SKIPPED_NOT_APPLICABLE "
                    f"but lacks a required non-empty skip_reason."
                )
            if self.is_applicable is True:
                object.__setattr__(self, "is_applicable", False)
        elif self.status == "REQUIRED":
            if self.is_applicable is False:
                object.__setattr__(self, "is_applicable", True)
        return self


class DevelopmentPlan(BaseModel):
    """Structured, ordered plan produced by DEV-PLAN defining sequential W_DEV execution."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    task_id: str
    workflow_id: str
    attempt_id: str = "att-1"
    plan_version: int | str = 1
    objective: str
    architecture_summary: str = ""
    change_impact_summary: str = ""
    affected_files: list[str] = Field(default_factory=list)
    steps: list[DevelopmentPlanStep] = Field(default_factory=list)
    risk_class: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    assumptions: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    discovered_facts: dict[str, Any] = Field(default_factory=dict)
    plan_hash: str = ""
    status: Literal["DRAFT", "SEALED", "APPROVED", "REJECTED", "EXECUTING", "COMPLETED"] = "DRAFT"
    rejection_feedback: str | None = None

    def canonical_bytes(self) -> bytes:
        """Return deterministic JSON-serialized byte representation of canonical plan fields."""
        canonical_steps = [
            {
                "acceptance_criteria": sorted(s.acceptance_criteria),
                "affected_artifacts": sorted(s.affected_artifacts),
                "dependencies": sorted(s.dependencies),
                "description": s.description,
                "name": s.name,
                "order": s.order,
                "required_capabilities": sorted(s.required_capabilities),
                "required_tools": sorted(s.required_tools),
                "risk_class": s.risk_class,
                "skip_reason": s.skip_reason or "",
                "status": s.status,
                "step_id": s.step_id,
                "subagent_id": s.subagent_id,
            }
            for s in self.steps
        ]
        payload = {
            "affected_files": sorted(self.affected_files),
            "architecture_summary": self.architecture_summary,
            "assumptions": sorted(self.assumptions),
            "attempt_id": self.attempt_id,
            "change_impact_summary": self.change_impact_summary,
            "discovered_facts": self.discovered_facts,
            "objective": self.objective,
            "plan_id": self.plan_id,
            "plan_version": str(self.plan_version),
            "risk_class": self.risk_class,
            "steps": canonical_steps,
            "task_id": self.task_id,
            "unresolved_items": sorted(self.unresolved_items),
            "workflow_id": self.workflow_id,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_plan_hash(self) -> str:
        """Compute tamper-evident SHA-256 digest over canonical plan bytes."""
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def validate_policy(self, is_release_producing: bool = True) -> None:
        """Validate plan against strict development governance policies.

        Fails closed on:
        - Missing steps
        - Exclusion of DEV-VERIFY, DEV-SEC, or DEV-REL on release workflows
        - Exclusion of non-excludable subagents
        - Duplicate step IDs
        - Unresolved or cyclic step dependencies
        """
        if not self.steps:
            raise PolicyViolationError("Development plan must contain at least one step.")

        step_ids: set[str] = set()
        seen_steps: set[str] = set()
        seen_subagents: set[str] = set()
        subagent_status_map: dict[str, str] = {}

        for step in self.steps:
            if step.step_id in step_ids:
                raise PolicyViolationError(
                    f"Duplicate step ID '{step.step_id}' found in development plan."
                )
            step_ids.add(step.step_id)

            # Dependencies must only reference preceding steps or subagents
            for dep in step.dependencies:
                if dep not in seen_steps and dep not in seen_subagents:
                    raise PolicyViolationError(
                        f"Step '{step.step_id}' depends on '{dep}', which is not an earlier step. "
                        "Forward references and cyclic dependencies are prohibited."
                    )
            seen_steps.add(step.step_id)
            seen_subagents.add(step.subagent_id)

            subagent_status_map[step.subagent_id] = step.status

            # Conditional exclusion restrictions
            if step.status == "SKIPPED_NOT_APPLICABLE":
                if step.subagent_id not in CONDITIONALLY_EXCLUDABLE_SUBAGENTS:
                    raise PolicyViolationError(
                        f"Sub-agent '{step.subagent_id}' cannot be excluded. "
                        f"Only {sorted(CONDITIONALLY_EXCLUDABLE_SUBAGENTS)} permit conditional exclusion."
                    )

        # Mandatory sub-agent verification for release workflows
        if is_release_producing:
            for mandatory in MANDATORY_RELEASE_SUBAGENTS:
                status = subagent_status_map.get(mandatory)
                if status != "REQUIRED":
                    raise PolicyViolationError(
                        f"Mandatory sub-agent '{mandatory}' must be included and marked REQUIRED "
                        "for release-producing development workflows."
                    )


# Backwards compatibility alias
class DevelopmentExecutionPlan(DevelopmentPlan):
    """Backwards-compatible alias for DevelopmentPlan."""
    pass

