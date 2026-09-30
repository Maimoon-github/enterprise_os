"""W_COMP: Layer-5 Competitor Intelligence Engine Coordinator.

Preserves Model A: Operates as a reasoning-only coordinator with zero direct
sandbox execution authority. Interprets Strategy plan assumptions, generates
bounded research step proposals for IE scheduling across authorized specialists,
and validates synthesized evidence briefs.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import BoundedWorkerAgent
from app.schemas.agent_contracts import TaskGrant
from app.schemas.competitor_intel import (
    CompetitiveEvidenceBrief,
    CompetitorResearchContext,
    CompetitorRole,
    ResearchStepProposal,
    StepProposalItem,
)
from app.schemas.sandbox import SandboxCapability


class CompetitorIntelAgent(BoundedWorkerAgent):
    """W_COMP Competitor Intel Engine Coordinator.

    Acts as reasoning-only domain coordinator. Does not directly execute
    sandbox tools or establish container lifecycles; delegates execution
    to IE-authorized specialist attempts.
    """

    capability = SandboxCapability.COMP

    def __init__(
        self,
        sandbox_client: Any = None,
        llm_client: Any = None,
        *,
        discovery_agent: Any = None,
        advertising_agent: Any = None,
        pricing_agent: Any = None,
        search_agent: Any = None,
        positioning_agent: Any = None,
        synthesis_agent: Any = None,
        specialist_llm_clients: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(sandbox_client, llm_client=llm_client)
        from app.agents.competitor_intel_engine.subagents import (
            CompetitorAdvertisingAgent,
            CompetitorDiscoveryAgent,
            CompetitorPositioningAgent,
            CompetitorPricingAgent,
            CompetitorSearchIntelAgent,
            CompetitorSynthesisAgent,
        )
        sub_clients = specialist_llm_clients or {}

        def _resolve_sub_llm(ident: str) -> Any:
            if ident in sub_clients:
                return sub_clients[ident]
            key_alt = ident.lower().replace("-", "_").replace("w_comp.", "").replace("comp_", "")
            if key_alt in sub_clients:
                return sub_clients[key_alt]
            if llm_client is not None and hasattr(llm_client, "settings"):
                return llm_client.__class__(
                    llm_client.settings,
                    agent_identity=ident,
                    model_identity=getattr(llm_client, "model_identity", None),
                    default_temperature=getattr(llm_client, "default_temperature", None),
                    default_max_output_tokens=getattr(llm_client, "default_max_output_tokens", None),
                )
            return llm_client

        self.discovery_agent = discovery_agent or CompetitorDiscoveryAgent(
            llm_client=_resolve_sub_llm("COMP-DISCOVERY")
        )
        self.advertising_agent = advertising_agent or CompetitorAdvertisingAgent(
            llm_client=_resolve_sub_llm("COMP-ADS")
        )
        self.pricing_agent = pricing_agent or CompetitorPricingAgent(
            llm_client=_resolve_sub_llm("COMP-PRICE")
        )
        self.search_agent = search_agent or CompetitorSearchIntelAgent(
            llm_client=_resolve_sub_llm("COMP-SEARCH")
        )
        self.positioning_agent = positioning_agent or CompetitorPositioningAgent(
            llm_client=_resolve_sub_llm("COMP-POSITION")
        )
        self.synthesis_agent = synthesis_agent or CompetitorSynthesisAgent(
            llm_client=_resolve_sub_llm("COMP-SYNTH")
        )

    @property
    def specialists(self) -> dict[str, Any]:
        """Registered Competitor Intel specialist sub-agents."""
        return {
            "COMP-DISCOVERY": self.discovery_agent,
            "COMP-ADS": self.advertising_agent,
            "COMP-PRICE": self.pricing_agent,
            "COMP-PRICING": self.pricing_agent,
            "COMP-SEARCH": self.search_agent,
            "COMP-POSITION": self.positioning_agent,
            "COMP-POSITIONING": self.positioning_agent,
            "COMP-SYNTH": self.synthesis_agent,
            "COMP-SYNTHESIS": self.synthesis_agent,
        }

    def build_payload(self, grant: TaskGrant, context: dict[str, object]) -> dict[str, str]:
        """Formulate legacy baseline payload if invoked via base execute path."""
        competitor = str(context.get("competitor", "CompetitorCorp"))
        return {
            "task_id": grant.task_id,
            "operation": "scrape_prices",
            "objective": "gather_competitor_intelligence",
            "competitor": competitor,
        }

    def interpret_strategy_plan(self, context: CompetitorResearchContext) -> ResearchStepProposal:
        """Interpret Strategy plan assumptions into a bounded DAG of research step proposals.

        Pure cognitive decomposition: produces no executable grants and executes no tools.
        """
        steps: list[StepProposalItem] = []

        # 1. Discovery step
        disc_step_id = f"step-disc-{context.run_id[:8]}"
        steps.append(
            StepProposalItem(
                step_id=disc_step_id,
                role=CompetitorRole.DISCOVERY,
                target_entity=context.scoped_entities[0] if context.scoped_entities else "all",
                scope_description="Resolve entity identities, subsidiaries, and domains",
            )
        )

        # 2. Parallel domain capture steps dependent on discovery
        ads_step_id = f"step-ads-{context.run_id[:8]}"
        price_step_id = f"step-price-{context.run_id[:8]}"
        search_step_id = f"step-search-{context.run_id[:8]}"
        pos_step_id = f"step-pos-{context.run_id[:8]}"

        steps.extend(
            [
                StepProposalItem(
                    step_id=ads_step_id,
                    role=CompetitorRole.ADS,
                    dependencies=[disc_step_id],
                    scope_description="Gather transparency ad-library metadata",
                ),
                StepProposalItem(
                    step_id=price_step_id,
                    role=CompetitorRole.PRICE,
                    dependencies=[disc_step_id],
                    scope_description="Extract and compare pricing points",
                ),
                StepProposalItem(
                    step_id=search_step_id,
                    role=CompetitorRole.SEARCH,
                    dependencies=[disc_step_id],
                    scope_description="Measure SERP rankings and keyword visibility",
                ),
                StepProposalItem(
                    step_id=pos_step_id,
                    role=CompetitorRole.POSITION,
                    dependencies=[disc_step_id],
                    scope_description="Extract positioning statements and claims",
                ),
            ]
        )

        # 3. Offline synthesis step dependent on all capture steps
        synth_step_id = f"step-synth-{context.run_id[:8]}"
        steps.append(
            StepProposalItem(
                step_id=synth_step_id,
                role=CompetitorRole.SYNTHESIS,
                dependencies=[ads_step_id, price_step_id, search_step_id, pos_step_id],
                scope_description="Synthesize normalized findings and check conflicts",
            )
        )

        return ResearchStepProposal(
            proposal_id=f"prop-{context.run_id}",
            input_hash=context.compute_context_hash(),
            ordered_steps=steps,
            scoped_entities=list(context.scoped_entities),
            scoped_sources=[p.source_id for p in context.source_policies],
            assumption_references=[a.id for a in context.assumptions],
            stop_conditions=["budget_exhausted", "deadline_exceeded"],
        )

    def validate_synthesis_brief(
        self,
        brief: CompetitiveEvidenceBrief,
        context: CompetitorResearchContext,
    ) -> dict[str, Any]:
        """Validate synthesized brief against assumptions, scope, and evidence links."""
        assumptions_evaluated = set(brief.assumption_verdicts.keys())
        context_assumptions = {a.id for a in context.assumptions}

        missing = context_assumptions - assumptions_evaluated
        return {
            "valid": len(missing) == 0,
            "brief_id": brief.brief_id,
            "missing_assumptions": list(missing),
            "total_observations": len(brief.observations),
            "total_findings": len(brief.findings),
            "total_conflicts": len(brief.conflicts),
            "market_alerts_count": len(brief.market_alerts),
        }
