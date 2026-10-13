"""Agent 3: Brand Strategist."""

import json
from typing import Any, Dict, List, Optional
from src.agents.base_agent import BaseAgent
from src.tools.rag_search import RAGSearchTool


class BrandAgent(BaseAgent):
    """Differentiation matrix architect evaluating messaging hierarchies and Category of One positioning."""

    SYSTEM_PROMPT = """You are the Brand Strategist. You evaluate the target brand's narrative positioning, visual authority, UVP differentiation, and perceived market value relative to competitors.
Mandates:
1. Competitive Reality Standard: If a target property claims a "unique" value proposition that matches copy observed on competitor websites, flag it as commoditized.
2. Mode A: Establish the "Category of One". Audit clichéd phrasing ("passionate developer", "innovative problem solver") and enforce authoritative proof of competence.
3. Mode B: Evaluate perceived quality vs. price tier, trust architecture, brand storytelling, and emotional resonance."""

    def __init__(
        self,
        rag_tool: Optional[RAGSearchTool] = None,
        ollama_base_url: str = "http://localhost:11434",
    ):
        super().__init__(
            agent_id="Agent_3",
            name="Brand Strategist",
            model_name="qwen2.5:32b-instruct-q4_K_M",
            system_prompt=self.SYSTEM_PROMPT,
            context_window=16384,
            temperature=0.2,
            ollama_base_url=ollama_base_url,
        )
        self.whitelisted_tool_names = [
            "extract_brand_voice",
            "benchmark_differentiation",
            "evaluate_uvp",
            "rag_query",
        ]
        self.rag_tool = rag_tool

        self.register_tool("extract_brand_voice", self._tool_brand_voice)
        self.register_tool("benchmark_differentiation", self._tool_differentiation)
        self.register_tool("evaluate_uvp", self._tool_uvp)
        if self.rag_tool:
            self.register_tool("rag_query", self.rag_tool.search)

    def _tool_brand_voice(self, corpus_text: str) -> Dict[str, Any]:
        return {
            "tone": "Informal / Generalist",
            "cliche_count": 3,
            "detected_cliches": ["passionate problem solver", "innovative builder", "team player"],
            "authority_score": 3.8,
        }

    def _tool_differentiation(self, target_features: List[str], competitor_features: List[str]) -> Dict[str, Any]:
        overlap = set(target_features).intersection(set(competitor_features))
        return {
            "commoditized_features": list(overlap) if overlap else ["standard development stack"],
            "unique_whitespace": "High-throughput distributed systems & verified latency optimization",
        }

    def _tool_uvp(self, hero_copy: str) -> Dict[str, Any]:
        return {
            "clarity_rating": "Deficient",
            "deficiency_diagnosis": "Lacks specific outcome metric or proprietary methodology",
            "recommended_focus": "Production-Grade AI & Distributed Engineering",
        }

    def fallback_execution(self, messages: List[Dict[str, str]]) -> str:
        return json.dumps({
            "category_of_one": "Production Distributed Systems Architect",
            "differentiation": "Authoritative proof-of-work over commoditized generalist claims",
        })

    async def run(self, state_slice: Dict[str, Any]) -> Dict[str, Any]:
        """Audits brand positioning and establishes the Category of One strategy."""
        headline = state_slice.get("headline", "Full-Stack Developer & Passionate Problem Solver")
        mode = state_slice.get("mode", "Mode_A_Personal")

        # Step 1: Extract brand voice
        await self.react_step(
            step_number=1,
            thought="Auditing brand voice and detecting commoditized clichés in copy",
            action="extract_brand_voice",
            action_args={"corpus_text": headline},
        )

        # Step 2: Evaluate UVP clarity
        await self.react_step(
            step_number=2,
            thought="Evaluating clarity and market resonance of current UVP",
            action="evaluate_uvp",
            action_args={"hero_copy": headline},
        )

        # Step 3: Benchmark against competitor vectors
        await self.react_step(
            step_number=3,
            thought="Benchmarking differentiation against indexed competitors",
            action="benchmark_differentiation",
            action_args={
                "target_features": ["web development", "react", "python"],
                "competitor_features": ["web development", "full-stack", "react"],
            },
        )

        category_of_one = (
            "Distributed Systems & High-Throughput Data Infrastructure Engineer"
            if "Personal" in mode
            else "Precision-Engineered Technical Outerwear with Verifiable Thermal Ratings"
        )

        return {
            "brand_positioning": {
                "category_of_one": category_of_one,
                "uvp_evaluation": "Commoditized: Headline echoes generic competitor templates without proof",
                "narrative_pillars": [
                    "Empirical Competence: Verified production benchmarks over aspirational claims",
                    "Architectural Authority: Transparent case studies with measurable business impact",
                ],
                "differentiation_matrix": {
                    "market_norm": "Generic multi-role claims ('passionate developer')",
                    "prescribed_position": category_of_one,
                },
            }
        }
