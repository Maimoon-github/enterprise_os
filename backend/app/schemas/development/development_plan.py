"""Schemas for development execution plans and ordered sub-agent steps."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DevelopmentPlanStep(BaseModel):
    """An individual ordered step in a development execution plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    subagent_id: str
    name: str
    description: str
    dependencies: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    is_applicable: bool = True
    skip_reason: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)


class DevelopmentExecutionPlan(BaseModel):
    """Structured plan produced by DEV-PLAN defining sequential execution."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    task_id: str
    objective: str
    steps: list[DevelopmentPlanStep] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    risk_class: str = "LOW"
    plan_hash: str = ""
    status: Literal["DRAFT", "APPROVED", "REJECTED", "EXECUTING", "COMPLETED"] = "DRAFT"
