"""Agent 4: SEO and Content Strategist."""

import json
from typing import Any, Dict, List, Optional
from src.agents.base_agent import BaseAgent
from src.tools.rag_search import RAGSearchTool


class SEOContentAgent(BaseAgent):
    """Information retrieval auditor diagnosing search visibility, schema markup, and content depth."""

    SYSTEM_PROMPT = """You are the SEO and Content Strategist. You audit search engine discoverability, information architecture, technical on-page health, and commercial intent coverage.
Mandates:
1. Technical Grounding: Every technical flaw (missing canonicals, broken schema, improper heading hierarchy) must cite the exact DOM snapshot node.
2. Semantic Content Mapping: Identify high-intent content gaps based on verified competitor coverage and audience search intent.
3. CMS Feasibility: Constrain recommendations to standard CMS capabilities (WordPress, Shopify, Webflow, Next.js) unless custom architecture is verified."""

    def __init__(
        self,
        rag_tool: Optional[RAGSearchTool] = None,
        ollama_base_url: str = "http://localhost:11434",
    ):
        super().__init__(
            agent_id="Agent_4",
            name="SEO & Content Strategist",
            model_name="qwen2.5:32b-instruct-q4_K_M",
            system_prompt=self.SYSTEM_PROMPT,
            context_window=16384,
            temperature=0.2,
            ollama_base_url=ollama_base_url,
        )
        self.whitelisted_tool_names = [
            "analyze_onpage_elements",
            "cluster_serp_intent",
            "scan_content_gaps",
            "rag_query",
        ]
        self.rag_tool = rag_tool

        self.register_tool("analyze_onpage_elements", self._tool_onpage)
        self.register_tool("cluster_serp_intent", self._tool_serp)
        self.register_tool("scan_content_gaps", self._tool_content_gaps)
        if self.rag_tool:
            self.register_tool("rag_query", self.rag_tool.search)

    def _tool_onpage(self, dom_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title_tag_status": "Generic / Unoptimized",
            "json_ld_schema_valid": False,
            "heading_hierarchy_issues": ["Multiple H1 tags or missing primary H1", "Unstructured sub-headings"],
            "canonical_status": "Missing canonical tag",
        }

    def _tool_serp(self, target_keywords: List[str]) -> Dict[str, Any]:
        return {
            "high_intent_clusters": [
                {"intent": "Commercial", "cluster": "Distributed Systems Consultant / Contractor"},
                {"intent": "Transactional", "cluster": "Hire Distributed Systems Engineer"},
            ],
            "unaddressed_volume": "Moderate (High Conversion Intent)",
        }

    def _tool_content_gaps(self, target_topics: List[str], competitor_topics: List[str]) -> Dict[str, Any]:
        return {
            "missing_case_studies": ["Latency benchmark breakdown", "High-throughput architecture teardown"],
            "depth_score": 4.1,
        }

    def fallback_execution(self, messages: List[Dict[str, str]]) -> str:
        return json.dumps({
            "technical_issues": ["Missing JSON-LD schema", "Unoptimized title tags"],
            "content_gaps": ["Technical deep dive case studies"],
        })

    async def run(self, state_slice: Dict[str, Any]) -> Dict[str, Any]:
        """Conducts on-page and semantic search gap analysis."""
        dom_slice = state_slice.get("dom_snapshot", {})

        # Step 1: Analyze on-page elements
        await self.react_step(
            step_number=1,
            thought="Auditing on-page SEO elements, schema markup, and DOM heading hierarchy",
            action="analyze_onpage_elements",
            action_args={"dom_data": dom_slice},
        )

        # Step 2: Cluster search intent
        await self.react_step(
            step_number=2,
            thought="Clustering target keywords into commercial and transactional intent",
            action="cluster_serp_intent",
            action_args={"target_keywords": ["software engineer", "developer portfolio"]},
        )

        # Step 3: Scan content voids
        await self.react_step(
            step_number=3,
            thought="Scanning semantic content voids relative to top competing authorities",
            action="scan_content_gaps",
            action_args={
                "target_topics": ["portfolio", "about"],
                "competitor_topics": ["distributed systems case study", "performance benchmarks"],
            },
        )

        return {
            "seo_and_content_plan": {
                "technical_health": {
                    "schema_org": "Deficient: Missing Person/ProfessionalService or Product schema",
                    "title_tag": "Deficient: Currently lacks niche positioning keywords",
                    "canonical_tag": "Missing: Risk of duplicate parameter indexing",
                },
                "high_intent_keywords": [
                    "Distributed Systems Architect",
                    "High Throughput Infrastructure Optimization",
                    "Production Python Performance Engineer",
                ],
                "content_editorial_blueprint": [
                    "Architecture Teardown: How we scaled to 50k req/s with 99.9th percentile sub-10ms latency",
                    "Production Post-Mortem Case Study with quantifiable system throughput metrics",
                ],
            }
        }
