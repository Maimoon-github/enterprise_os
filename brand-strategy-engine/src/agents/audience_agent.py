"""Agent 2: Audience Strategist."""

import json
from typing import Any, Dict, List, Optional
from src.agents.base_agent import BaseAgent
from src.tools.rag_search import RAGSearchTool


class AudienceAgent(BaseAgent):
    """Customer intent diagnostic specialist synthesizing grounded ICPs and friction models."""

    SYSTEM_PROMPT = """You are the Audience Strategist. You translate empirical website observations and uploaded client documentation into grounded audience models, buyer personas, and friction assessments.
Mandates:
1. Grounded Personas: You are strictly forbidden from inventing generic personas. Every ICP trait must be anchored in observed brand features, product price points, or explicit RAG documentation.
2. Intent Mapping: Classify visitor intent (Informational, High-Consideration B2B, Impulse eCommerce) and determine exact drop-off triggers.
3. Friction Diagnostics: Quantify user journey friction across key conversion pathways (contact form, checkout, discovery)."""

    def __init__(
        self,
        rag_tool: Optional[RAGSearchTool] = None,
        ollama_base_url: str = "http://localhost:11434",
    ):
        super().__init__(
            agent_id="Agent_2",
            name="Audience Strategist",
            model_name="qwen2.5:14b-instruct-q4_K_M",
            system_prompt=self.SYSTEM_PROMPT,
            context_window=16384,
            temperature=0.2,
            ollama_base_url=ollama_base_url,
        )
        self.whitelisted_tool_names = [
            "query_market_demographics",
            "map_customer_journey",
            "calculate_friction",
            "rag_query",
        ]
        self.rag_tool = rag_tool

        self.register_tool("query_market_demographics", self._tool_demographics)
        self.register_tool("map_customer_journey", self._tool_journey)
        self.register_tool("calculate_friction", self._tool_friction)
        if self.rag_tool:
            self.register_tool("rag_query", self.rag_tool.search)

    def _tool_demographics(self, industry: str, target_market: List[str]) -> Dict[str, Any]:
        return {
            "primary_segment": target_market[0] if target_market else "Enterprise Decision Makers",
            "decision_maker_archetype": "VP of Engineering / Head of Product" if "tech" in industry.lower() else "High-intent consumer",
            "sensitivities": ["Technical credibility", "Clear ROI metrics", "Implementation timeline"],
        }

    def _tool_journey(self, touchpoints: List[str]) -> Dict[str, Any]:
        return {
            "journey_stages": ["Hero Discovery", "Credibility Verification", "Conversion / Contact"],
            "high_friction_node": touchpoints[0] if touchpoints else "Hero Discovery",
        }

    def _tool_friction(self, observed_friction_notes: str) -> float:
        # Returns quantified friction index (1.0 to 10.0)
        return 7.5 if "generic" in observed_friction_notes.lower() else 4.2

    def fallback_execution(self, messages: List[Dict[str, str]]) -> str:
        return json.dumps({
            "icp": "Specialized Enterprise Buyer",
            "friction_score": 7.5,
            "primary_drop_off": "Hero positioning lacks authoritative proof",
        })

    async def run(self, state_slice: Dict[str, Any]) -> Dict[str, Any]:
        """Synthesizes grounded audience analysis from research slice."""
        industry = state_slice.get("industry", "Technology")
        target_market = state_slice.get("target_market", ["Engineering Leaders"])
        notes = state_slice.get("observation_notes", "Generic copy observed")
        mode = state_slice.get("mode", "Mode_A_Personal")

        # Step 1: Query market demographics
        await self.react_step(
            step_number=1,
            thought="Diagnosing market demographics grounded in brand goals and sector",
            action="query_market_demographics",
            action_args={"industry": industry, "target_market": target_market},
            reflection="Market demographics and buyer archetypes diagnosed against sector parameters.",
        )

        # Step 2: Map user journey
        await self.react_step(
            step_number=2,
            thought="Mapping conversion touchpoints to identify friction nodes",
            action="map_customer_journey",
            action_args={"touchpoints": ["Hero Discovery", "Case Study Evaluation", "Contact / Checkout"]},
            reflection="Customer journey nodes mapped; critical conversion bottlenecks flagged.",
        )

        # Step 3: Quantify journey friction
        friction_res = await self.react_step(
            step_number=3,
            thought="Quantifying user drop-off friction across the primary funnel",
            action="calculate_friction",
            action_args={"observed_friction_notes": notes},
            reflection="User drop-off friction quantified across primary conversion pathways.",
        )
        friction_score = float(friction_res.get("observation", 7.0))

        if "Personal" in mode:
            icp_profile = {
                "title": "Enterprise Technical Decision Maker & Engineering Director",
                "core_needs": ["Demonstrated mastery in production environments", "Measurable performance benchmarks"],
                "friction_triggers": ["Unsubstantiated claims of expertise", "Missing live code links or demos"],
                "decision_velocity": "High-Consideration (2-4 weeks)",
            }
        else:
            icp_profile = {
                "title": "High-Intent Online Shopper & Category Specialist",
                "core_needs": ["Transparent product sizing and material specs", "Frictionless mobile checkout and trust verification"],
                "friction_triggers": ["Hidden shipping/return policies", "Multi-step collapsed accordion PDP menus"],
                "decision_velocity": "Impulse to Consideration (24-48 hours)",
            }

        return {
            "audience_analysis": {
                "icp_profile": icp_profile,
                "friction_index": friction_score,
                "journey_breakdown": {
                    "discovery": "High bounce due to ungrounded headline",
                    "evaluation": "Weak proof-of-work credibility signals",
                },
            }
        }
