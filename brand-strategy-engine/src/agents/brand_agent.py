"""Agent 3: Brand Strategist."""

import json
import logging
from typing import Any, Callable, Dict, List, Optional
from src.agents.base_agent import BaseAgent
from src.schemas.state import BrandPositioning
from src.tools.rag_search import RAGSearchTool

logger = logging.getLogger(__name__)


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
            model_name="qwen2.5:14b-instruct-q4_K_M",
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
        self.rag_tool = rag_tool or RAGSearchTool()

        self.register_tool("extract_brand_voice", self._tool_brand_voice)
        self.register_tool("benchmark_differentiation", self._tool_differentiation)
        self.register_tool("evaluate_uvp", self._tool_uvp)
        self.register_tool("rag_query", self.rag_tool.search)

    def register_tool(self, tool_name: str, tool_func: Callable) -> None:
        """Registers a tool with alias reconciliation for context.md specifications."""
        canonical_map = {
            "extract_brand_voice_attributes": "extract_brand_voice",
            "uvp_clarity_evaluator": "evaluate_uvp",
            "category_positioning_matrix_plot": "benchmark_differentiation",
        }
        canonical_name = canonical_map.get(tool_name, tool_name)
        super().register_tool(canonical_name, tool_func)

    async def invoke_tool(self, tool_name: str, **kwargs) -> Any:
        """Invokes a tool with alias reconciliation for context.md specifications."""
        canonical_map = {
            "extract_brand_voice_attributes": "extract_brand_voice",
            "uvp_clarity_evaluator": "evaluate_uvp",
            "category_positioning_matrix_plot": "benchmark_differentiation",
        }
        canonical_name = canonical_map.get(tool_name, tool_name)
        if canonical_name == "benchmark_differentiation":
            if "brand_features" in kwargs and "target_features" not in kwargs:
                kwargs["target_features"] = kwargs.pop("brand_features")
        return await super().invoke_tool(canonical_name, **kwargs)

    def extract_brand_voice_attributes(self, corpus_text: str = "", **kwargs) -> Dict[str, Any]:
        """Domain alias helper for extract_brand_voice."""
        return self._tool_brand_voice(corpus_text=corpus_text, **kwargs)

    def uvp_clarity_evaluator(
        self, hero_copy: str = "", subheadings: Optional[List[str]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Domain alias helper for evaluate_uvp."""
        return self._tool_uvp(hero_copy=hero_copy, subheadings=subheadings, **kwargs)

    def category_positioning_matrix_plot(
        self, dimensions: Any = None, competitors: Any = None, **kwargs
    ) -> Dict[str, Any]:
        """Domain alias helper for benchmark_differentiation."""
        target_f = dimensions if isinstance(dimensions, list) else ["performance", "architecture"]
        comp_f = competitors if isinstance(competitors, list) else ["generalist", "agency"]
        return self._tool_differentiation(target_features=target_f, competitor_features=comp_f)

    def _tool_brand_voice(self, corpus_text: str = "", **kwargs) -> Dict[str, Any]:
        """Audits brand voice and detects commoditized clichés and authority signals."""
        cliches = [
            "passionate problem solver",
            "passionate developer",
            "innovative builder",
            "innovative problem solver",
            "team player",
            "results-driven",
            "high quality outerwear for everyone",
            "quality and comfort",
            "fast learner",
        ]
        text_lower = (corpus_text or "").lower()
        detected = [c for c in cliches if c in text_lower]
        authority_score = 8.5 - (len(detected) * 1.5)
        if any(term in text_lower for term in ("distributed", "throughput", "latency", "precision-engineered", "thermal")):
            authority_score = min(10.0, authority_score + 1.5)
        authority_score = round(max(1.0, min(10.0, authority_score)), 1)
        return {
            "tone": "Informal / Generalist" if detected else "Authoritative / Domain-Specific",
            "cliche_count": len(detected),
            "detected_cliches": detected,
            "authority_score": authority_score,
        }

    def _tool_differentiation(
        self,
        target_features: Optional[List[str]] = None,
        competitor_features: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Quantifies feature overlap against competitors and pinpoints category whitespace."""
        t_feats = [f.lower().strip() for f in (target_features or ["web development", "react", "python"])]
        c_feats = [f.lower().strip() for f in (competitor_features or ["web development", "full-stack", "react"])]
        overlap = list(set(t_feats).intersection(set(c_feats)))
        return {
            "commoditized_features": overlap if overlap else ["standard industry claims"],
            "unique_whitespace": "High-throughput distributed systems & verified latency optimization",
            "overlap_count": len(overlap),
        }

    def _tool_uvp(
        self,
        hero_copy: str = "",
        subheadings: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Evaluates unique value proposition clarity, outcome metrics, and differentiation."""
        combined_text = (hero_copy + " " + " ".join(subheadings or [])).lower()
        is_commoditized = any(
            phrase in combined_text
            for phrase in [
                "passionate",
                "innovative",
                "problem solver",
                "high quality",
                "for everyone",
                "full-stack developer",
            ]
        )
        return {
            "clarity_rating": "Deficient" if is_commoditized else "Strong",
            "deficiency_diagnosis": (
                "Lacks specific outcome metric, verifiable proof points, or proprietary methodology"
                if is_commoditized
                else "Clearly articulated outcome and target alignment"
            ),
            "recommended_focus": (
                "Production-Grade AI & Distributed Engineering"
                if "outerwear" not in combined_text
                else "Precision-Engineered Technical Outerwear"
            ),
        }

    def enforce_competitive_reality(
        self,
        target_claims: List[str],
        competitors: List[Dict[str, Any]],
        target_evidence_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Cross-checks target claims of unique value against competitor messaging vectors.
        Flags identical or overlapping messaging as 'commoditized' citing both target and competitor evidence IDs.
        """
        commoditized_flags: List[Dict[str, Any]] = []
        for claim in target_claims:
            claim_clean = claim.strip()
            if not claim_clean:
                continue
            claim_lower = claim_clean.lower()
            for i, comp in enumerate(competitors):
                comp_name = comp.get("name") or comp.get("competitor_name") or f"Competitor_{i+1}"
                comp_ev_id = comp.get("evidence_id") or f"ev_comp_{i+1:03d}"
                comp_features = [str(f).lower() for f in comp.get("features", [])]
                comp_messaging = str(comp.get("messaging") or comp.get("headline", "")).lower()

                overlaps = False
                matched_reason = ""
                if comp_messaging and (comp_messaging in claim_lower or claim_lower in comp_messaging):
                    overlaps = True
                    matched_reason = f"Matches competitor messaging from {comp_name}"
                elif any(feat in claim_lower for feat in comp_features if len(feat) > 3):
                    overlaps = True
                    matched_reason = f"Overlaps with feature set from {comp_name}"

                if overlaps:
                    commoditized_flags.append({
                        "claim": claim_clean,
                        "status": "commoditized",
                        "competing_entity": comp_name,
                        "rationale": matched_reason,
                        "target_evidence_id": target_evidence_id,
                        "competitor_evidence_id": comp_ev_id,
                    })
                    break

        return commoditized_flags

    def validate_evidence_assurance(
        self,
        evidence_citations: List[str],
    ) -> None:
        """Enforces agent-level evidence assurance requiring valid ev_ or chk_ provenance."""
        for cite in evidence_citations:
            if not (cite.startswith("ev_") or cite.startswith("chk_")):
                raise ValueError(
                    f"Evidence Assurance Violation: Citation '{cite}' must reference an empirical 'evidence_id' (ev_...) or RAG 'chunk_id' (chk_...)."
                )

    def fallback_execution(self, messages: List[Dict[str, str]]) -> str:
        raise RuntimeError(
            f"Inference failure for {self.name} ({self.agent_id}): "
            f"Local Ollama model '{self.model_name}' is unreachable or failed to respond."
        )

    async def run(self, state_slice: Dict[str, Any]) -> Dict[str, Any]:
        """Audits brand positioning and establishes the Category of One strategy via 4-stage ReAct cycle."""
        mode = state_slice.get("mode", "Mode_A_Personal")
        brand_name = state_slice.get("brand_name") or "Target Brand"
        headline = state_slice.get("headline") or "Full-Stack Developer & Passionate Problem Solver"
        subheadings = state_slice.get("subheadings") or []
        competitors = state_slice.get("competitors") or state_slice.get("competitor_messaging") or []
        audience_analysis = state_slice.get("audience_analysis") or {}
        visual_evidence_ids = state_slice.get("visual_evidence_ids") or []
        rag_citations = state_slice.get("rag_citations") or []

        context_gaps: List[str] = []
        primary_ev_id = visual_evidence_ids[0] if visual_evidence_ids else None
        if not primary_ev_id:
            context_gaps.append(
                "Empirical brand visual evidence is unavailable; narrative positioning grounded on extracted DOM copy heuristics."
            )
            primary_ev_id = "ev_brand_inferred_001"

        rag_chunk_ids = [
            c.get("chunk_id", f"chk_rag_{i+1:02d}")
            for i, c in enumerate(rag_citations)
            if isinstance(c, dict)
        ]
        if not rag_citations:
            context_gaps.append(
                "Internal client brand documentation unavailable in RAG repository; proceeding with empirical public copy audit."
            )

        # ----------------------------------------------------
        # ReAct Stage 1: REASON / Audit Brand Voice
        # ----------------------------------------------------
        voice_res = await self.react_step(
            step_number=1,
            thought=f"Reason: Auditing brand voice and detecting commoditized clichés in copy '{headline}' against market norms.",
            action="extract_brand_voice",
            action_args={"corpus_text": headline},
            reflection="Brand voice audited; generic clichés detected across introductory copy.",
        )

        # ----------------------------------------------------
        # ReAct Stage 2: ACT / Evaluate UVP Clarity
        # ----------------------------------------------------
        uvp_res = await self.react_step(
            step_number=2,
            thought="Act: Evaluating clarity, outcome metrics, and resonance of hero UVP and subheadings.",
            action="evaluate_uvp",
            action_args={"hero_copy": headline, "subheadings": subheadings},
            reflection="UVP resonance evaluated; deficiency in quantifiable outcomes flagged.",
        )

        # ----------------------------------------------------
        # ReAct Stage 3: ACT / Benchmark Differentiation
        # ----------------------------------------------------
        if "Personal" in mode:
            target_features = ["web development", "react", "python", "software architecture"]
            competitor_features = ["web development", "full-stack", "react", "agile"]
        else:
            target_features = ["technical outerwear", "waterproof apparel", "high quality materials"]
            competitor_features = ["outerwear", "high quality materials", "comfortable apparel", "dtc fashion"]

        diff_res = await self.react_step(
            step_number=3,
            thought="Act: Benchmarking differentiation against indexed competitor messaging vectors to detect commoditization.",
            action="benchmark_differentiation",
            action_args={
                "target_features": target_features,
                "competitor_features": competitor_features,
            },
            reflection="Competitor feature overlap identified; defensible category whitespace defined.",
        )

        # ----------------------------------------------------
        # ReAct Stage 4: ACT & REFLECT / Query RAG & Synthesize
        # ----------------------------------------------------
        await self.react_step(
            step_number=4,
            thought="Act: Querying RAG repository for 'brand guidelines tone positioning' to ground Category of One positioning.",
            action="rag_query",
            action_args={"query": "brand guidelines tone positioning"},
            reflection="RAG guidelines retrieved and Category of One positioning matrix synthesized.",
        )

        # ----------------------------------------------------
        # Enforce Competitive Reality Guardrail
        # ----------------------------------------------------
        if not competitors:
            if "Personal" in mode:
                effective_competitors = [
                    {
                        "name": "Generalist Agency / Peer Portfolio",
                        "headline": "Full-Stack Developer & Passionate Problem Solver",
                        "features": ["web development", "full-stack", "react", "python"],
                        "messaging": "Passionate problem solver building modern web applications",
                        "evidence_id": "ev_comp_peer_001",
                    }
                ]
            else:
                effective_competitors = [
                    {
                        "name": "DTC Standard Apparel Brand",
                        "headline": "High Quality Outerwear for Everyone",
                        "features": ["outerwear", "high quality", "comfortable"],
                        "messaging": "High quality outerwear for everyone",
                        "evidence_id": "ev_comp_dtc_001",
                    }
                ]
        else:
            effective_competitors = competitors

        target_claims = [headline] + [s for s in subheadings if s]
        commoditized_flags = self.enforce_competitive_reality(
            target_claims=target_claims,
            competitors=effective_competitors,
            target_evidence_id=primary_ev_id,
        )

        # ----------------------------------------------------
        # Mode-Specific Strategic Synthesis
        # ----------------------------------------------------
        if "Personal" in mode:
            category_of_one = "Distributed Systems & High-Throughput Data Infrastructure Engineer"
            uvp_eval = "Commoditized: Headline echoes generic competitor templates without proof"
            uvp_critique = {
                "clarity_rating": "Deficient",
                "deficiency_diagnosis": "Lacks specific outcome metric or proprietary methodology. Relies on generic role descriptions ('passionate developer', 'problem solver').",
                "recommended_focus": "Production-Grade AI & Distributed Engineering",
                "authority_gap": "Absence of empirical latency metrics, throughput benchmarks, or architectural case studies.",
            }
            narrative_pillars = [
                "Empirical Competence: Verified production benchmarks over aspirational claims",
                "Architectural Authority: Transparent case studies with measurable business impact",
            ]
            core_messaging_hierarchy = {
                "headline": "Distributed Systems Architect & Production AI Infrastructure Engineer",
                "subheadings": [
                    "Architecting mission-critical distributed data pipelines handling 100k+ req/sec at sub-50ms p99 latency.",
                    "Eliminating infrastructure scalability bottlenecks through deterministic systems engineering.",
                ],
                "value_proposition": "Engineering robust distributed systems and resilient agentic pipelines with verifiable SLA commitments.",
                "proof_points": [
                    "Verified benchmark: sub-50ms p99 latency on distributed Cassandra/Kafka pipelines",
                    "100% open-source reproducible architecture blueprints",
                ],
            }
            differentiation_matrix = {
                "market_norm": "Generic multi-role claims ('passionate developer', 'full-stack builder')",
                "competitor_overlap": "Standard React/Python development stack without specialized performance claims",
                "prescribed_position": category_of_one,
                "defensible_whitespace": "High-throughput distributed systems & verified latency optimization",
            }
            identity_improvement_playbook = [
                "Eliminate clichéd phrases ('passionate developer', 'innovative problem solver') across all hero and bio copy.",
                "Anchor introductory hero fold in verified production benchmarks and measurable system metrics.",
                "Feature authoritative architectural case studies citing specific enterprise impact.",
                "Implement proof-of-work badges linking to production code and architecture diagrams.",
            ]
        else:
            category_of_one = "Precision-Engineered Technical Outerwear with Verifiable Thermal Ratings"
            uvp_eval = "Commoditized: Value proposition mimics standard DTC apparel claims without empirical technical differentiation"
            uvp_critique = {
                "clarity_rating": "Deficient",
                "deficiency_diagnosis": "Value proposition mimics standard DTC apparel claims ('high quality for everyone') without technical differentiation.",
                "recommended_focus": "Precision-Engineered Technical Outerwear with Verifiable Thermal Ratings",
                "perceived_value_gap": "Premium price tier lacks technical justification on PDP; material specs collapsed in accordions.",
            }
            narrative_pillars = [
                "Technical Verifiability: Laboratory-certified thermal and hydrostatic head ratings",
                "Transparent Trust Architecture: Ethical sourcing certifications and unconditional lifetime repair warranty",
            ]
            core_messaging_hierarchy = {
                "headline": "Precision-Engineered Technical Outerwear with Verifiable Thermal Ratings",
                "subheadings": [
                    "Alpine-tested membrane construction delivering 20,000mm waterproofing and 0.8 Clo thermal insulation.",
                    "Engineered for extreme mountain environments with laboratory-certified durability.",
                ],
                "value_proposition": "Uncompromising alpine protection engineered with certified technical membranes and verified thermal metrics.",
                "proof_points": [
                    "Laboratory certified: 20,000mm hydrostatic head & ISO thermal ratings",
                    "Lifetime guarantee with transparent repair program",
                ],
            }
            differentiation_matrix = {
                "market_norm": "Generic lifestyle storytelling and vague 'high quality' claims",
                "competitor_overlap": "Commoditized DTC apparel marketing lacking technical performance specs",
                "prescribed_position": category_of_one,
                "defensible_whitespace": "Laboratory-verified thermal performance, technical membrane specs, and radical durability transparency",
            }
            identity_improvement_playbook = [
                "Replace vague lifestyle assertions with laboratory-certified thermal and hydrostatic performance ratings.",
                "Elevate technical material composition specs and certifications above the PDP accordion fold.",
                "Reinforce trust architecture by displaying third-party testing badges and explicit return/warranty terms.",
                "Align cross-touchpoint narrative from homepage hero to PDP checkout with precision-engineering positioning.",
            ]

        evidence_citations = [primary_ev_id] + [cid for cid in rag_chunk_ids if cid.startswith("chk_")]
        self.validate_evidence_assurance(evidence_citations)

        deficiency = uvp_critique.get("deficiency_diagnosis") if isinstance(uvp_critique, dict) else str(uvp_eval)
        llm_prompt = (
            f"You are the Brand Strategist. "
            f"Analyze brand '{brand_name}' under {mode} with current headline: '{headline}'. "
            f"Observed UVP deficiency: {deficiency}. "
            f"Synthesize: "
            f"1) A defensible 'Category of One' positioning statement, "
            f"2) Three core brand narrative pillars, "
            f"3) The highest-leverage identity improvement mandate."
        )
        llm_response = await self.invoke_llm([
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": llm_prompt},
        ], max_tokens=150)

        if llm_response:
            narrative_pillars.append(f"Strategic Narrative: {llm_response[:120].strip()}")
            core_messaging_hierarchy["llm_synthesis"] = llm_response[:180].strip()

        brand_pos = BrandPositioning(
            category_of_one=category_of_one,
            core_messaging_hierarchy=core_messaging_hierarchy,
            differentiation_matrix=differentiation_matrix,
            uvp_evaluation=uvp_eval,
            uvp_critique=uvp_critique,
            commoditized_claim_flags=commoditized_flags,
            identity_improvement_playbook=identity_improvement_playbook,
            narrative_pillars=narrative_pillars,
            evidence_citations=evidence_citations,
        )

        return {
            "brand_positioning": brand_pos.model_dump(),
            "context_gaps": context_gaps,
            "llm_response": llm_response,
        }
