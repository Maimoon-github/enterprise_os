"""Common base for the seven bounded worker agents.

Every worker follows the same shape: accept a ``TaskGrant`` and assembled
context, formulate an explicit bounded sandbox invocation mandate, invoke
the sandbox adapter, and return an ``EvidenceEnvelope``. Centralizing that
shape here means each worker file only needs to declare its capability and
interpret its own sandbox output.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import PolicyViolationError
from app.integrations.llm.client import LlmClient, LlmResponseError
from app.integrations.sandbox.client import SandboxClient
from app.schemas.agent_contracts import ConfidenceInterval, EvidenceEnvelope, TaskGrant
from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxInvocationMandate


class WorkerReasoningOutput(BaseModel):
    """Structured LLM domain reasoning output produced by a bounded worker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain_interpretation: str = Field(min_length=1)
    requires_specialist_execution: bool = Field(default=True)
    selected_tools: list[str] = Field(default_factory=list)
    suggested_parameters: dict[str, Any] = Field(default_factory=dict)
    preliminary_findings: list[str] = Field(default_factory=list)
    identified_risks: list[str] = Field(default_factory=list)
    rationale_summary: str = Field(min_length=1)
    estimated_confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class BoundedWorkerAgent(ABC):
    """Base class for a single bounded worker with one sandbox capability and domain reasoning."""

    #: The sandbox capability this worker is authorized to request.
    capability: SandboxCapability

    def __init__(
        self,
        sandbox_client: SandboxClient,
        llm_client: LlmClient | None = None,
    ) -> None:
        self._sandbox_client = sandbox_client
        self._llm_client = llm_client

    @property
    def llm_client(self) -> LlmClient | None:
        return self._llm_client

    @abstractmethod
    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        """Return the sandbox invocation payload for this worker's capability."""

    def interpret_result(
        self, sanitized_output: dict[str, str]
    ) -> tuple[list[str], ConfidenceInterval]:
        """Return (evidence lines, confidence interval) from a sandbox result.

        The default interpretation treats every output value as an evidence
        line and reports a fixed moderate confidence; workers with richer
        output structure override this method.
        """

        evidence = [f"{key}: {value}" for key, value in sanitized_output.items()]
        confidence = ConfidenceInterval(point_estimate=0.6, lower_bound=0.4, upper_bound=0.8)
        return evidence, confidence

    async def _reason_domain(
        self, grant: TaskGrant, context: dict[str, object]
    ) -> tuple[WorkerReasoningOutput, dict[str, Any]]:
        """Perform bounded LLM domain reasoning over the supplied task grant and context."""
        assert self._llm_client is not None

        system_prompt = (
            f"You are the {grant.worker_role.value} bounded domain worker agent in a governed system. "
            "Interpret your grant and context strictly within your domain. "
            "Boundaries: "
            "- You have zero direct access to RAG, databases, or external systems (Model A). "
            "- You cannot authorize actions or grant permissions; reasoning never equals authorization. "
            f"- Tool usage is restricted strictly to your authorized sandbox capability '{self.capability.value}' "
            f"and permitted tools: {grant.tool_permissions or [self.capability.value]}. "
            "- Provide structured domain findings, evaluate whether specialist execution is needed, "
            "and identify any risks or assumptions."
        )

        grant_summary = {
            "task_id": grant.task_id,
            "worker_role": grant.worker_role.value,
            "tenant_id": grant.tenant_scope.tenant_id if grant.tenant_scope else "default",
            "brand_id": grant.brand_id,
            "objective": grant.objective,
            "task_scope": grant.task_scope,
            "task_slice": grant.task_slice,
            "allowed_tools": grant.tool_permissions,
            "allowed_capabilities": grant.sandbox_capabilities or [self.capability.value],
            "token_budget": grant.token_budget,
            "stop_conditions": grant.stop_conditions,
            "available_context_keys": list(context.keys()),
        }

        user_prompt = json.dumps(grant_summary, ensure_ascii=False, sort_keys=True, default=str)
        reasoning, metadata = await self._llm_client.generate_structured_with_metadata(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=WorkerReasoningOutput,
        )

        # -------------------------------------------------------------
        # Governed Tool Calling Enforcement (Model output never grants authority)
        # -------------------------------------------------------------
        effective_allowlist = set(grant.tool_permissions) | set(grant.sandbox_capabilities) | {self.capability.value}
        unauthorized_tools = [t for t in reasoning.selected_tools if t not in effective_allowlist]
        if unauthorized_tools:
            raise PolicyViolationError(
                f"Worker {grant.worker_role.value} attempted unauthorized tool execution: "
                f"{unauthorized_tools}. Model output never grants authority."
            )

        # Enforce tenant isolation boundary
        target_tenant = reasoning.suggested_parameters.get("tenant_id")
        current_tenant = grant.tenant_scope.tenant_id if grant.tenant_scope else "default"
        if target_tenant and target_tenant != current_tenant:
            raise PolicyViolationError(
                f"Worker {grant.worker_role.value} attempted cross-tenant access to '{target_tenant}'. "
                f"Bounded to '{current_tenant}'."
            )

        # Enforce token budget limit
        if metadata.get("total_tokens", 0) > grant.token_budget:
            raise PolicyViolationError(
                f"Worker {grant.worker_role.value} exceeded token budget: "
                f"{metadata.get('total_tokens')} > {grant.token_budget}."
            )

        return reasoning, metadata

    async def run(self, grant: TaskGrant, context: dict[str, object]) -> EvidenceEnvelope:
        """Execute this worker's bounded task grant and return its evidence."""

        reasoning_output: WorkerReasoningOutput | None = None
        llm_metadata: dict[str, Any] = {}

        if self._llm_client is not None:
            reasoning_output, llm_metadata = await self._reason_domain(grant, context)

        payload = self.build_payload(grant, context)
        operation = payload.get("operation", "default")
        network_policy = (
            NetworkPolicy.CONTROLLED
            if self.capability == SandboxCapability.SCRAPE
            else NetworkPolicy.DISABLED
        )

        egress_grant = context.get("egress_grant")
        mandate = SandboxInvocationMandate(
            task_id=grant.task_id,
            worker_role=grant.worker_role,
            tenant_id=grant.tenant_scope.tenant_id if grant.tenant_scope else "default",
            capability=self.capability,
            operation=operation,
            payload=payload,
            network_policy=network_policy,
            egress_grant=egress_grant,  # type: ignore[arg-type]
            timeout_seconds=grant.token_budget if grant.token_budget > 0 else 120,
        )
        result = await self._sandbox_client.invoke(mandate)

        findings: list[str] = []
        artifacts: list[str] = []
        risks: list[str] = []

        if reasoning_output:
            findings.extend(reasoning_output.preliminary_findings)
            risks.extend(reasoning_output.identified_risks)

        if not result.success:
            evidence = [f"sandbox execution failed: {result.error or 'unknown error'}"]
            confidence = ConfidenceInterval(point_estimate=0.0, lower_bound=0.0, upper_bound=0.0)
            risks.append(result.error or "sandbox execution failed")
        else:
            evidence, confidence = self.interpret_result(result.sanitized_output)
            findings.extend([line for line in evidence if not line.startswith("error")])
            if "diff" in result.sanitized_output:
                artifacts.append(f"diff:{grant.task_id}")
            if "dev_deliverable" in result.sanitized_output:
                artifacts.append(f"dev:{grant.task_id}")
            if "copy_body" in result.sanitized_output or "headline" in result.sanitized_output:
                artifacts.append(f"copy:{grant.task_id}")
            if "creative_package" in result.sanitized_output:
                artifacts.append(f"creative:{grant.task_id}")
            if "verified_dossier" in result.sanitized_output:
                artifacts.append(f"dossier:{grant.task_id}")
            if "learning_delta" in result.sanitized_output:
                artifacts.append(f"learning:{grant.task_id}")
            if "strategy_plan" in result.sanitized_output or "strategy_roadmap" in result.sanitized_output:
                artifacts.append(f"strategy:{grant.task_id}")
            if result.generated_artifacts:
                artifacts.extend(result.generated_artifacts)

        findings = sorted(list(set(findings)))
        artifacts = sorted(list(set(artifacts)))
        risks = sorted(list(set(risks)))

        provenance: dict[str, Any] = {
            "agent": grant.worker_role.value if grant.worker_role else "unknown",
            "capability": self.capability.value,
            "task_id": grant.task_id,
            "execution_id": result.execution_id,
            "status": result.status.value,
        }
        if llm_metadata:
            provenance.update({
                "llm_reasoning_used": "true",
                "llm_provider": str(llm_metadata.get("provider", "unset")),
                "llm_model": str(llm_metadata.get("actual_model", "unset")),
                "is_local_model": "true" if llm_metadata.get("is_local") else "false",
                "prompt_tokens": str(llm_metadata.get("prompt_tokens", 0)),
                "completion_tokens": str(llm_metadata.get("completion_tokens", 0)),
                "total_tokens": str(llm_metadata.get("total_tokens", 0)),
                "estimated_cost_usd": str(llm_metadata.get("estimated_cost_usd", 0.0)),
                "governed_tools_authorized": ",".join(reasoning_output.selected_tools) if reasoning_output else "",
            })
        if result.provenance:
            provenance.update({k: str(v) for k, v in result.provenance.items()})

        return EvidenceEnvelope(
            task_id=grant.task_id,
            worker_role=grant.worker_role,
            confidence=confidence,
            evidence=evidence,
            payload=result.sanitized_output,
            findings=findings,
            generated_artifacts=artifacts,
            supporting_evidence=evidence,
            provenance=provenance,
            proposed_state_changes={
                "status": "completed" if result.success else "failed",
                "capability": self.capability.value,
            },
            unresolved_risks_or_assumptions=risks,
        )
