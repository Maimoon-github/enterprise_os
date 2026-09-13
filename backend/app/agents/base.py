"""Common base for the seven bounded worker agents.

Every worker follows the same shape: accept a ``TaskGrant`` and assembled
context, formulate an explicit bounded sandbox invocation mandate, invoke
the sandbox adapter, and return an ``EvidenceEnvelope``. Centralizing that
shape here means each worker file only needs to declare its capability and
interpret its own sandbox output.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.integrations.sandbox.client import SandboxClient
from app.schemas.agent_contracts import ConfidenceInterval, EvidenceEnvelope, TaskGrant
from app.schemas.sandbox import NetworkPolicy, SandboxCapability, SandboxInvocationMandate


class BoundedWorkerAgent(ABC):
    """Base class for a single bounded worker with one sandbox capability."""

    #: The sandbox capability this worker is authorized to request.
    capability: SandboxCapability

    def __init__(self, sandbox_client: SandboxClient) -> None:
        self._sandbox_client = sandbox_client

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

    async def run(self, grant: TaskGrant, context: dict[str, object]) -> EvidenceEnvelope:
        """Execute this worker's bounded task grant and return its evidence."""

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

        if not result.success:
            evidence = [f"sandbox execution failed: {result.error or 'unknown error'}"]
            confidence = ConfidenceInterval(point_estimate=0.0, lower_bound=0.0, upper_bound=0.0)
            risks.append(result.error or "sandbox execution failed")
        else:
            evidence, confidence = self.interpret_result(result.sanitized_output)
            findings = [line for line in evidence if not line.startswith("error")]
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

        artifacts = sorted(list(set(artifacts)))

        provenance = {
            "agent": grant.worker_role.value if grant.worker_role else "unknown",
            "capability": self.capability.value,
            "task_id": grant.task_id,
            "execution_id": result.execution_id,
            "status": result.status.value,
        }
        if result.provenance:
            provenance.update(result.provenance)

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
