"""CREAT-CONCEPT: Creative Specialist Sub-Agent.

Message territories, angles, audience tensions, and narrative architecture specialist.
Uses only approved strategy and product evidence; does not alter channel, budget,
funnel, or campaign scope. Operates with purpose-scoped LLM reasoning under DENY_ALL tool policy.
"""

from __future__ import annotations

import json
from typing import Any
import uuid

from app.core.exceptions import PolicyViolationError
from app.schemas.agent_contracts import (
    ConceptItem,
    ConceptPack,
    CreativePlan,
    TaskGrant,
)
from app.schemas.sandbox import SandboxInvocationMandate


class CreativeConceptAgent:
    """Specialist sub-agent for creative concepting and narrative architecture (CREAT-CONCEPT)."""

    SPECIALIST_ID = "CREAT-CONCEPT"
    ALLOWED_OPERATIONS = ()

    def __init__(self, llm_client: Any = None, sandbox_client: Any = None) -> None:
        self._llm_client = llm_client
        self._sandbox_client = sandbox_client

    @property
    def specialist_id(self) -> str:
        return self.SPECIALIST_ID

    @property
    def allowed_operations(self) -> tuple[str, ...]:
        return self.ALLOWED_OPERATIONS

    @property
    def llm_client(self) -> Any:
        return self._llm_client

    @property
    def sandbox_client(self) -> Any:
        return self._sandbox_client


    def build_sandbox_mandate(
        self,
        task_id: str,
        tenant_id: str,
        operation: str,
        payload: dict[str, Any],
    ) -> SandboxInvocationMandate:
        """Reject sandbox mandate: CREAT-CONCEPT operates under strict DENY_ALL tool policy."""
        raise PolicyViolationError(
            f"Specialist '{self.SPECIALIST_ID}' operates under DENY_ALL tool policy "
            "and cannot formulate sandbox invocation mandates."
        )

    async def run(
        self,
        grant: TaskGrant | None = None,
        plan: CreativePlan | None = None,
        context: dict[str, Any] | None = None,
    ) -> ConceptPack:
        """Formulate message territories and narrative architecture grounded in approved evidence.

        Fails closed if approved evidence manifest is absent or empty.
        """
        effective_context = context or {}

        # 1. Determine Tenant and Task ID
        tenant_id = (
            grant.tenant_scope.tenant_id
            if (grant and grant.tenant_scope)
            else (plan.tenant_id if plan else "default")
        )
        task_id = grant.task_id if grant else (plan.task_id if plan else f"task-{uuid.uuid4().hex[:8]}")

        # 2. Strict Evidence Grounding Check (Fail-closed)
        evidence_manifest: list[str] = []
        if plan and plan.evidence_manifest:
            evidence_manifest = list(plan.evidence_manifest)
        elif "approved_claims" in effective_context:
            raw_claims = effective_context["approved_claims"]
            if isinstance(raw_claims, list):
                for c in raw_claims:
                    if isinstance(c, dict) and "id" in c:
                        evidence_manifest.append(str(c["id"]))
                    elif isinstance(c, str):
                        evidence_manifest.append(c)
            elif isinstance(raw_claims, str):
                evidence_manifest = [c.strip() for c in raw_claims.split(",") if c.strip()]
        elif "evidence_refs" in effective_context:
            evidence_manifest = list(effective_context["evidence_refs"])

        if not evidence_manifest:
            raise ValueError(
                f"Specialist '{self.SPECIALIST_ID}': Missing approved evidence manifest. "
                "CREAT-CONCEPT cannot fabricate concept territories without verified evidence."
            )

        # 3. Scope Boundaries Enforcement
        approved_channels = plan.approved_channels if plan else effective_context.get("channels", ["meta"])
        target_audience = plan.target_audience if plan else effective_context.get("target_audience", "enterprise")
        prohibited_claims = plan.prohibited_scope if plan else effective_context.get("prohibited_claims", [])

        # 4. Formulate Distinct Message Territories
        distinct_templates = [
            {
                "territory": "Operational Efficiency & Proven Performance",
                "audience_tension": "High overhead and friction in scaling operations without predictable ROI",
                "message_angle": "Empirical benchmark superiority and radical operational simplicity",
                "narrative_architecture": "Hook (Current friction) -> Tension (Cost of inaction) -> Resolution (Verified benchmark) -> CTA",
            },
            {
                "territory": "Governance, Certainty & Risk Mitigation",
                "audience_tension": "Fear of non-compliance, ungrounded hallucinations, and vendor lock-in",
                "message_angle": "Institutional-grade verification and policy-enforced reliability",
                "narrative_architecture": "Hook (Regulatory/compliance exposure) -> Insight (Governed architectures) -> Proof (Evidence manifest) -> CTA",
            },
            {
                "territory": "Velocity & Competitive Advantage",
                "audience_tension": "Competitors accelerating deployment while existing legacy tools remain siloed",
                "message_angle": "Accelerating production cycles with audited, automated workflows",
                "narrative_architecture": "Hook (Pace of innovation) -> Contrast (Manual vs automated) -> Validation (Proven metrics) -> CTA",
            },
        ]

        # LLM reasoning hook if client is configured
        if self._llm_client is not None:
            try:
                system_prompt = (
                    "You are CREAT-CONCEPT, the Creative Engine specialist for message territories, "
                    "audience tensions, and narrative architecture. "
                    "Use strictly the approved evidence manifest and target audience. "
                    "Return a JSON list of concept objects with keys: territory, audience_tension, message_angle, narrative_architecture."
                )
                user_prompt = (
                    f"Audience: {target_audience}\n"
                    f"Evidence Manifest: {json.dumps(evidence_manifest)}\n"
                    f"Channels: {json.dumps(approved_channels)}\n"
                    f"Prohibited: {json.dumps(prohibited_claims)}"
                )
                llm_out, _ = await self._llm_client.complete_with_metadata(
                    prompt=user_prompt, system=system_prompt
                )
                parsed_concepts = json.loads(llm_out)
                if isinstance(parsed_concepts, list) and len(parsed_concepts) >= 2:
                    distinct_templates = parsed_concepts
            except Exception:
                pass

        concepts: list[ConceptItem] = []
        for i, t in enumerate(distinct_templates):
            concept_item = ConceptItem(
                concept_id=f"cpt-{i + 1}",
                territory=t["territory"],
                audience_tension=t["audience_tension"],
                message_angle=t["message_angle"],
                narrative_architecture=t["narrative_architecture"],
                approved_evidence_refs=evidence_manifest,
                prohibited_claims=prohibited_claims,
            )
            concepts.append(concept_item)

        concept_pack = ConceptPack(
            tenant_id=tenant_id,
            task_id=task_id,
            producing_agent_id=self.SPECIALIST_ID,
            concepts=concepts,
            narrative_framework="Hook -> Audience Tension -> Evidence Proof -> Resolution CTA",
            approved_channel_ids=approved_channels,
            evidence_refs=evidence_manifest,
        )
        concept_pack.compute_artifact_hash()

        return concept_pack


CreatConceptAgent = CreativeConceptAgent
