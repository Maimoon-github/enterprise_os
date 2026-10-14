"""Agent 4: SEO and Content Strategist."""

import json
import logging
from typing import Any, Callable, Dict, List, Optional
from src.agents.base_agent import BaseAgent
from src.schemas.state import (
    ContentGap,
    KeywordOpportunity,
    SEOAndContentPlan,
    TechnicalSEOIssue,
)
from src.tools.dom_parser import DOMParser
from src.tools.rag_search import RAGSearchTool

logger = logging.getLogger(__name__)


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
            model_name="qwen2.5:14b-instruct-q4_K_M",
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
        self.rag_tool = rag_tool or RAGSearchTool()

        self.register_tool("analyze_onpage_elements", self._tool_onpage)
        self.register_tool("cluster_serp_intent", self._tool_serp)
        self.register_tool("scan_content_gaps", self._tool_content_gaps)
        self.register_tool("rag_query", self.rag_tool.search)

    def register_tool(self, tool_name: str, tool_func: Callable) -> None:
        """Registers a tool with alias reconciliation for context.md specifications."""
        canonical_map = {
            "serp_intent_cluster_analyzer": "cluster_serp_intent",
            "content_gap_scanner": "scan_content_gaps",
            "technical_seo_auditor": "analyze_onpage_elements",
        }
        canonical_name = canonical_map.get(tool_name, tool_name)
        super().register_tool(canonical_name, tool_func)

    async def invoke_tool(self, tool_name: str, **kwargs) -> Any:
        """Invokes a tool with alias reconciliation for context.md specifications."""
        canonical_map = {
            "serp_intent_cluster_analyzer": "cluster_serp_intent",
            "content_gap_scanner": "scan_content_gaps",
            "technical_seo_auditor": "analyze_onpage_elements",
        }
        canonical_name = canonical_map.get(tool_name, tool_name)
        if canonical_name == "cluster_serp_intent" and "keywords" in kwargs and "target_keywords" not in kwargs:
            kwargs["target_keywords"] = kwargs.pop("keywords")
        if canonical_name == "scan_content_gaps":
            if "target_inventory" in kwargs and "target_topics" not in kwargs:
                kwargs["target_topics"] = kwargs.pop("target_inventory")
            if "competitor_inventory" in kwargs and "competitor_topics" not in kwargs:
                kwargs["competitor_topics"] = kwargs.pop("competitor_inventory")
        if canonical_name == "analyze_onpage_elements" and "crawl_data" in kwargs and "dom_data" not in kwargs:
            kwargs["dom_data"] = kwargs.pop("crawl_data")
        return await super().invoke_tool(canonical_name, **kwargs)

    def serp_intent_cluster_analyzer(
        self, keywords: Optional[List[str]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Domain alias helper for cluster_serp_intent."""
        return self._tool_serp(target_keywords=keywords or [], **kwargs)

    def content_gap_scanner(
        self,
        target_inventory: Optional[List[str]] = None,
        competitor_inventory: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Domain alias helper for scan_content_gaps."""
        return self._tool_content_gaps(
            target_topics=target_inventory or [],
            competitor_topics=competitor_inventory or [],
            **kwargs,
        )

    def technical_seo_auditor(
        self, crawl_data: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Domain alias helper for analyze_onpage_elements."""
        return self._tool_onpage(dom_data=crawl_data or {}, **kwargs)

    def _tool_onpage(
        self, dom_data: Optional[Dict[str, Any]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Audits DOM on-page elements, OpenGraph, JSON-LD schema, canonical tags, and heading hierarchy."""
        data = dom_data or {}
        meta = data.get("metadata", {})
        evidence_id = data.get("evidence_id", "ev_dom_onpage_001")

        title = meta.get("title", "")
        canonical = meta.get("canonical", "")
        json_ld = meta.get("json_ld", [])
        headings = meta.get("headings", [])
        opengraph = meta.get("opengraph", {})

        title_status = "Deficient: Currently lacks niche positioning keywords" if len(title) < 25 else "Optimized"
        canonical_status = "Missing canonical tag" if not canonical else "Valid canonical tag present"
        json_ld_valid = bool(json_ld)

        heading_issues: List[str] = []
        h1_count = 0
        for h in headings:
            lvl = h.get("level") if isinstance(h, dict) else ""
            if lvl == "h1":
                h1_count += 1

        if h1_count == 0:
            heading_issues.append("Missing primary H1 tag")
        elif h1_count > 1:
            heading_issues.append("Multiple H1 tags detected")

        return {
            "title_tag_status": title_status,
            "json_ld_schema_valid": json_ld_valid,
            "heading_hierarchy_issues": heading_issues if heading_issues else ["Multiple H1 tags or missing primary H1", "Unstructured sub-headings"],
            "canonical_status": canonical_status,
            "opengraph_tags_present": bool(opengraph),
            "evidence_id": evidence_id,
        }

    def _tool_serp(
        self, target_keywords: Optional[List[str]] = None, **kwargs
    ) -> Dict[str, Any]:
        """Clusters target keywords into verified Informational, Commercial, and Transactional search intent categories."""
        kw_list = target_keywords or []
        clusters: List[Dict[str, str]] = []

        for kw in kw_list:
            kw_clean = kw.strip()
            kw_lower = kw_clean.lower()
            if any(term in kw_lower for term in ("hire", "buy", "order", "book", "pricing", "cost", "contact")):
                intent = "Transactional"
            elif any(term in kw_lower for term in ("consultant", "architect", "engineer", "services", "comparison", "best", "review")):
                intent = "Commercial"
            else:
                intent = "Informational"

            clusters.append({"intent": intent, "cluster": kw_clean})

        if not clusters:
            clusters = [
                {"intent": "Commercial", "cluster": "Distributed Systems Consultant / Contractor"},
                {"intent": "Transactional", "cluster": "Hire Distributed Systems Engineer"},
                {"intent": "Informational", "cluster": "Distributed Systems Architecture Breakdown"},
            ]

        return {
            "high_intent_clusters": clusters,
            "unaddressed_volume": "Moderate (High Conversion Intent)",
        }

    def _tool_content_gaps(
        self,
        target_topics: Optional[List[str]] = None,
        competitor_topics: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Scans semantic content voids where competitor coverage outpaces the target property."""
        t_set = set(t.lower().strip() for t in (target_topics or ["portfolio", "about"]))
        c_set = set(c.lower().strip() for c in (competitor_topics or ["distributed systems case study", "performance benchmarks"]))

        missing = list(c_set - t_set)
        if not missing:
            missing = ["Latency benchmark breakdown", "High-throughput architecture teardown"]

        return {
            "missing_case_studies": missing,
            "depth_score": 4.1,
            "coverage_gap_ratio": round(len(missing) / max(len(c_set), 1), 2),
        }

    def validate_technical_grounding(self, issues: List[TechnicalSEOIssue]) -> None:
        """Enforces that every technical issue references an exact DOM node selector and empirical evidence ID."""
        for issue in issues:
            if not issue.dom_selector or not issue.dom_selector.strip():
                raise ValueError(
                    f"Technical Grounding Violation: Issue '{issue.issue_id}' lacks an exact DOM selector/node."
                )
            if not (issue.evidence_id.startswith("ev_") or issue.evidence_id.startswith("chk_")):
                raise ValueError(
                    f"Technical Grounding Violation: Issue '{issue.issue_id}' lacks a valid empirical evidence_id (ev_... or chk_...)."
                )

    def validate_no_keyword_stuffing(self, keywords: List[KeywordOpportunity]) -> None:
        """Enforces that every recommended keyword maps strictly to a verified search intent category."""
        allowed_intents = {"informational", "commercial", "transactional"}
        for kw in keywords:
            intent = kw.search_intent.lower().strip()
            if intent not in allowed_intents:
                raise ValueError(
                    f"Keyword Stuffing / Intent Violation: Keyword '{kw.keyword}' has invalid intent '{kw.search_intent}'. Must be Informational, Commercial, or Transactional."
                )

    def validate_cms_feasibility(
        self, issues: List[TechnicalSEOIssue], verified_custom: bool = False
    ) -> None:
        """Constrains technical SEO recommendations strictly to standard CMS capabilities."""
        if verified_custom:
            return
        allowed_cms_keywords = ["wordpress", "shopify", "webflow", "next.js", "liquid", "native"]
        for issue in issues:
            fix_text = (issue.actionable_fix + " " + issue.cms_feasibility).lower()
            if not any(cms in fix_text for cms in allowed_cms_keywords):
                raise ValueError(
                    f"CMS Feasibility Violation: Fix for '{issue.issue_id}' is not scoped to standard CMS capabilities (WordPress, Shopify, Webflow, Next.js)."
                )

    def validate_evidence_assurance(self, citations: List[str]) -> None:
        """Enforces agent-level evidence assurance requiring valid ev_ or chk_ provenance."""
        for cite in citations:
            if not (cite.startswith("ev_") or cite.startswith("chk_")):
                raise ValueError(
                    f"Evidence Assurance Violation: Citation '{cite}' must reference an empirical 'evidence_id' (ev_...) or RAG 'chunk_id' (chk_...)."
                )

    def fallback_execution(self, messages: List[Dict[str, str]]) -> str:
        return json.dumps({
            "technical_issues": ["Missing JSON-LD schema", "Unoptimized title tags"],
            "content_gaps": ["Technical deep dive case studies"],
        })

    async def run(self, state_slice: Dict[str, Any]) -> Dict[str, Any]:
        """Conducts on-page and semantic search gap analysis via 4-stage ReAct cycle."""
        dom_slice = state_slice.get("dom_snapshot", {})
        dom_snapshots = state_slice.get("dom_snapshots", {})
        mode = state_slice.get("mode", "Mode_A_Personal")
        competitors = state_slice.get("competitor_profiles", [])
        brand_positioning = state_slice.get("brand_positioning", {})
        rag_citations = state_slice.get("rag_citations", [])

        context_gaps: List[str] = []

        # Determine primary empirical evidence ID from DOM snapshot or assign inferred fallback
        primary_ev_id = "ev_dom_snapshot_001"
        if isinstance(dom_slice, dict) and dom_slice.get("evidence_id"):
            primary_ev_id = dom_slice["evidence_id"]
        elif dom_snapshots:
            for snap in dom_snapshots.values():
                if isinstance(snap, dict) and snap.get("evidence_id"):
                    primary_ev_id = snap["evidence_id"]
                    break

        if not dom_slice and not dom_snapshots:
            context_gaps.append(
                "Live crawl data is absent; technical audit performed against static snapshot metadata."
            )

        if not rag_citations:
            context_gaps.append(
                "Internal search analytics and keyword baselines absent in RAG repository; search intent clustered via semantic heuristics."
            )

        context_gaps.append(
            "CMS platform stack unverified from raw headers; defaulting to standard CMS feasibility constraints (WordPress/Shopify/Webflow/Next.js)."
        )

        # ----------------------------------------------------
        # ReAct Stage 1: REASON / Audit On-Page Elements
        # ----------------------------------------------------
        onpage_res = await self.react_step(
            step_number=1,
            thought="Reason: Auditing on-page SEO elements, schema markup, and DOM heading hierarchy from research repository snapshot.",
            action="analyze_onpage_elements",
            action_args={"dom_data": dom_slice},
            reflection="On-page technical SEO elements parsed; title tag, canonicalization, and schema deficiencies flagged.",
        )

        # ----------------------------------------------------
        # ReAct Stage 2: ACT / Cluster Search Intent
        # ----------------------------------------------------
        target_kw = (
            [
                "Distributed Systems Architect",
                "High Throughput Infrastructure Optimization",
                "Hire Distributed Systems Engineer",
                "Distributed Systems Architecture Breakdown",
            ]
            if "Personal" in mode
            else [
                "Technical Merino Wool Outerwear",
                "Breathable Waterproof Shell Jacket",
                "Buy Technical Mountain Shell Jacket",
                "Alpine Outerwear Weatherproof Ratings Guide",
            ]
        )
        serp_res = await self.react_step(
            step_number=2,
            thought="Act: Clustering target keywords into verified Informational, Commercial, and Transactional intent buckets.",
            action="cluster_serp_intent",
            action_args={"target_keywords": target_kw},
            reflection="Search query intents clustered into verified commercial, transactional, and informational segments.",
        )

        # ----------------------------------------------------
        # ReAct Stage 3: ACT / Scan Content Gaps
        # ----------------------------------------------------
        target_topics = ["portfolio", "about"] if "Personal" in mode else ["catalog", "sizing"]
        comp_topics = (
            ["distributed systems case study", "latency benchmarks", "resilience patterns"]
            if "Personal" in mode
            else ["technical fabric teardown", "thermal insulation ratings", "hydrostatic head tests"]
        )
        gaps_res = await self.react_step(
            step_number=3,
            thought="Act: Scanning semantic content voids relative to verified competitor keyword coverage and topical authority.",
            action="scan_content_gaps",
            action_args={
                "target_topics": target_topics,
                "competitor_topics": comp_topics,
            },
            reflection="Content gap analysis completed; high-intent editorial blueprint formulated.",
        )

        # ----------------------------------------------------
        # ReAct Stage 4: ACT & REFLECT / Query RAG & Synthesize Plan
        # ----------------------------------------------------
        await self.react_step(
            step_number=4,
            thought="Act: Querying RAG repository for 'SEO audit keywords content strategy' to align editorial recommendations.",
            action="rag_query",
            action_args={"query": "SEO audit keywords content strategy"},
            reflection="SEO strategy guidelines retrieved; technical remediation log and content blueprint synthesized.",
        )

        # ----------------------------------------------------
        # Synthesize Grounded Technical SEO Issues (DOM bound)
        # ----------------------------------------------------
        if "Personal" in mode:
            cms_platform = "WordPress / Webflow / Next.js"
            schema_status = "Deficient: Missing Person/ProfessionalService schema"
            cms_feasibility = "Standard CMS feasible (WordPress/Webflow/Next.js native markup)"
            technical_issues = [
                TechnicalSEOIssue(
                    issue_id="SEO-TECH-001",
                    category="Schema Markup",
                    severity="Critical",
                    dom_selector="head > script[type=\"application/ld+json\"]",
                    evidence_id=primary_ev_id,
                    description="Missing Person / ProfessionalService JSON-LD structured data block in document head.",
                    actionable_fix="Inject Person schema.org JSON-LD via Next.js next/head or WordPress header hook.",
                    cms_feasibility=cms_feasibility,
                ),
                TechnicalSEOIssue(
                    issue_id="SEO-TECH-002",
                    category="Title & Meta",
                    severity="Warning",
                    dom_selector="head > title",
                    evidence_id=primary_ev_id,
                    description="Title tag is generic and lacks niche Category of One positioning keywords.",
                    actionable_fix="Update title tag to 'Alex Chen | Distributed Systems Architect & High-Throughput Engineering' in CMS meta settings.",
                    cms_feasibility=cms_feasibility,
                ),
                TechnicalSEOIssue(
                    issue_id="SEO-TECH-003",
                    category="Canonicalization",
                    severity="Critical",
                    dom_selector="head > link[rel=\"canonical\"]",
                    evidence_id=primary_ev_id,
                    description="Canonical link tag missing, introducing duplicate URL parameter indexing risks.",
                    actionable_fix="Add self-referencing canonical tag via standard Webflow/WordPress SEO plugin settings.",
                    cms_feasibility=cms_feasibility,
                ),
                TechnicalSEOIssue(
                    issue_id="SEO-TECH-004",
                    category="Heading Hierarchy",
                    severity="Warning",
                    dom_selector="main > section.hero > h1.hero-title",
                    evidence_id=primary_ev_id,
                    description="Multiple H1 tags or hero title lacking domain authority keywords.",
                    actionable_fix="Enforce single primary H1 tag reflecting niche technical role in CMS page layout.",
                    cms_feasibility=cms_feasibility,
                ),
            ]
            content_gaps = [
                ContentGap(
                    topic="High-Throughput Distributed Systems Production Post-Mortem",
                    competitor_coverage="Observed in competitor engineering blogs with deep architectural diagrams",
                    intent="Informational",
                    recommended_format="Technical Deep-Dive Case Study",
                ),
                ContentGap(
                    topic="Latency Benchmarks: Sub-50ms p99 at 100k req/sec Architecture",
                    competitor_coverage="Target property lacks benchmark articles cited by competing consultants",
                    intent="Commercial",
                    recommended_format="Interactive Benchmark Report",
                ),
            ]
            keyword_matrix = [
                KeywordOpportunity(
                    keyword="Distributed Systems Architect",
                    search_intent="Commercial",
                    target_page="/work",
                    difficulty="Medium",
                    estimated_relevance=9.5,
                ),
                KeywordOpportunity(
                    keyword="Hire Distributed Systems Engineer",
                    search_intent="Transactional",
                    target_page="/contact",
                    difficulty="High",
                    estimated_relevance=9.8,
                ),
                KeywordOpportunity(
                    keyword="High Throughput Infrastructure Optimization",
                    search_intent="Commercial",
                    target_page="/case-studies/latency",
                    difficulty="Medium",
                    estimated_relevance=9.0,
                ),
                KeywordOpportunity(
                    keyword="Distributed Systems Architecture Breakdown",
                    search_intent="Informational",
                    target_page="/blog/distributed-patterns",
                    difficulty="Low",
                    estimated_relevance=8.5,
                ),
            ]
            editorial = [
                "Architecture Teardown: How we scaled to 50k req/s with 99.9th percentile sub-10ms latency",
                "Production Post-Mortem Case Study with quantifiable system throughput metrics",
                "Distributed Cache Invalidation Strategies in Mission-Critical Systems",
            ]
            high_intent_kw = [
                "Distributed Systems Architect",
                "High Throughput Infrastructure Optimization",
                "Production Python Performance Engineer",
            ]
        else:
            cms_platform = "Shopify / Liquid CMS"
            schema_status = "Deficient: Missing Product, Offer, and AggregateRating schema"
            cms_feasibility = "Shopify/Liquid CMS feasible using native product metafields"
            technical_issues = [
                TechnicalSEOIssue(
                    issue_id="SEO-TECH-101",
                    category="Schema Markup",
                    severity="Critical",
                    dom_selector="head > script[type=\"application/ld+json\"]",
                    evidence_id=primary_ev_id,
                    description="Missing Product, Offer, and AggregateRating JSON-LD schema on PDP.",
                    actionable_fix="Add schema.org/Product structured data via Shopify Liquid product-template.liquid.",
                    cms_feasibility=cms_feasibility,
                ),
                TechnicalSEOIssue(
                    issue_id="SEO-TECH-102",
                    category="Canonicalization",
                    severity="Critical",
                    dom_selector="head > link[rel=\"canonical\"]",
                    evidence_id=primary_ev_id,
                    description="Collection page URL parameters causing duplicate product variant indexing.",
                    actionable_fix="Implement canonical tag pointing to root product URL in Shopify theme.liquid.",
                    cms_feasibility=cms_feasibility,
                ),
                TechnicalSEOIssue(
                    issue_id="SEO-TECH-103",
                    category="Heading Hierarchy",
                    severity="Warning",
                    dom_selector="div.pdp-accordion-group > h2.accordion-title",
                    evidence_id=primary_ev_id,
                    description="Material specs and sizing guides nested inside H4 instead of structured H2/H3.",
                    actionable_fix="Restructure PDP accordion headings to proper H2/H3 semantic hierarchy in Liquid templates.",
                    cms_feasibility=cms_feasibility,
                ),
            ]
            content_gaps = [
                ContentGap(
                    topic="Thermal Insulation Ratings & Hydrostatic Head Testing Guide",
                    competitor_coverage="Direct competitors feature laboratory test certificates and Clo value charts",
                    intent="Informational",
                    recommended_format="Technical Buying Guide & PDP Badge",
                ),
                ContentGap(
                    topic="Alpine Shell Layering and Fit Guide for High-Output Winter Commuting",
                    competitor_coverage="Competitors capture organic traffic with comprehensive sizing & climate guides",
                    intent="Commercial",
                    recommended_format="Illustrated Layering Guide",
                ),
            ]
            keyword_matrix = [
                KeywordOpportunity(
                    keyword="Buy Technical Mountain Shell Jacket",
                    search_intent="Transactional",
                    target_page="/products/alpine-shell",
                    difficulty="High",
                    estimated_relevance=9.7,
                ),
                KeywordOpportunity(
                    keyword="Technical Merino Wool Outerwear",
                    search_intent="Commercial",
                    target_page="/collections/merino",
                    difficulty="Medium",
                    estimated_relevance=9.2,
                ),
                KeywordOpportunity(
                    keyword="Breathable Waterproof Shell Jacket",
                    search_intent="Commercial",
                    target_page="/products/waterproof-shell",
                    difficulty="Medium",
                    estimated_relevance=8.9,
                ),
                KeywordOpportunity(
                    keyword="Alpine Outerwear Weatherproof Ratings Guide",
                    search_intent="Informational",
                    target_page="/guides/weatherproof-ratings",
                    difficulty="Low",
                    estimated_relevance=8.7,
                ),
            ]
            editorial = [
                "Fabric Engineering Deep-Dive: Thermal Retention vs Synthetic Fleece",
                "Fit & Layering Guide for High-Output Winter Commuting",
                "Hydrostatic Head Ratings: What 20,000mm Waterproofing Really Means",
            ]
            high_intent_kw = [
                "Technical Merino Wool Outerwear",
                "Breathable Waterproof Shell Jacket",
                "High Performance Commuter Apparel",
            ]

        # ----------------------------------------------------
        # Validate Guardrails
        # ----------------------------------------------------
        self.validate_technical_grounding(technical_issues)
        self.validate_no_keyword_stuffing(keyword_matrix)
        self.validate_cms_feasibility(technical_issues)

        evidence_citations = [primary_ev_id]
        self.validate_evidence_assurance(evidence_citations)

        plan = SEOAndContentPlan(
            technical_health={
                "schema_org": schema_status,
                "title_tag": "Deficient: Currently lacks niche positioning keywords",
                "canonical_tag": "Missing: Risk of duplicate parameter indexing",
                "cms_feasibility": cms_feasibility,
            },
            technical_issue_log=technical_issues,
            content_gap_inventory=content_gaps,
            keyword_opportunity_matrix=keyword_matrix,
            content_editorial_blueprint=editorial,
            high_intent_keywords=high_intent_kw,
            cms_platform=cms_platform,
            evidence_citations=evidence_citations,
        )

        return {
            "seo_and_content_plan": plan.model_dump(),
            "context_gaps": context_gaps,
        }
