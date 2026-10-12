# pyright: reportMissingImports=false
"""Validation tests for TSK-03: Perception Pipelines and Hybrid RAG Knowledge Base."""

import os
from agent_sandbox import Sandbox
from core.perception import PerceptionPipeline, AudienceProfile, StoreAuditSignal, MarketTrendSignal
from rag.ingestion import DocumentIndexer
from rag.retriever import HybridRetriever


def test_perception_normalization_and_signal_parsing():
    pipeline = PerceptionPipeline()

    raw_html = """
    <html>
        <body>
            <h1>Checkout Redesign</h1>
            <p>Customer pain point: Checkout complexity and hidden shipping fees.</p>
            <p>Customer desire: Transparent pricing and fast guest checkout.</p>
            <p>Customer trigger: Free shipping threshold at $50.</p>
            <input type="text" name="email" />
            <button>Add to Cart</button>
            <script>window.dataLayer = []; function gtag(){dataLayer.push(arguments);}</script>
        </body>
    </html>
    """
    # 1. HTML Normalization
    md = pipeline.normalize_html_to_markdown(raw_html)
    assert "# Checkout Redesign" in md
    assert "Checkout complexity" in md

    # 2. Audience Profile Signal
    aud: AudienceProfile = pipeline.parse_audience_profile(md)
    assert len(aud.pain_points) > 0
    assert len(aud.desires) > 0
    assert len(aud.purchasing_triggers) > 0

    # 3. Store Audit Signal
    audit: StoreAuditSignal = pipeline.parse_store_audit(raw_html, url="https://store.example.com")
    assert audit.url == "https://store.example.com"
    assert "Checkout Redesign" in audit.headings
    assert "GA4" in audit.tracking_tags
    assert audit.baymard_heuristics["form_field_count"] >= 1
    assert "Add to Cart" in audit.cta_elements

    # 4. Market Trend Signal
    social_text = "Massive growth and high ROI for direct response video campaigns on LinkedIn."
    trend: MarketTrendSignal = pipeline.parse_market_trend(social_text, platform="linkedin")
    assert trend.platform == "linkedin"
    assert trend.sentiment == "positive"
    assert trend.engagement_score > 50


def test_brand_core_and_playbook_ingestion_and_hybrid_search():
    indexer = DocumentIndexer()
    retriever = HybridRetriever()

    # 1. Ingest Brand Core materials
    brand_content = """
    Brand Manifesto: We empower ambitious eCommerce founders with deterministic AI agents.
    Our mission is high-margin growth with authentic personal brand positioning.
    Core values: extreme transparency, zero fluff, unit economic rigor.
    """
    brand_ids = indexer.index_brand_core(
        doc_id="brand_manifesto_01",
        title="Autonomous AI Brand Manifesto",
        content=brand_content,
        metadata={"author": "Founder", "target": "Founders"},
    )
    assert len(brand_ids) > 0

    # 2. Ingest Playbook Research
    cro_content = """
    Baymard Checkout Heuristic 402: Hidden shipping costs cause 48% of cart abandonment.
    Always disclose total order cost including taxes and shipping before payment step.
    Ensure guest checkout is prominently displayed beside login buttons.
    """
    cro_ids = indexer.index_playbook(
        doc_id="baymard_cro_402",
        title="Baymard Checkout Friction Patterns",
        content=cro_content,
        category="baymard_cro",
        metadata={"source": "Baymard Institute", "impact": "High"},
    )
    assert len(cro_ids) > 0

    # 3. Partition-Isolated Search
    brand_results = retriever.search("deterministic AI eCommerce founders", partition="brand_core", top_k=3)
    assert len(brand_results) > 0
    for res in brand_results:
        assert res.partition == "brand_core"
        assert res.score > 0

    cro_results = retriever.search("cart abandonment hidden shipping costs", partition="playbooks_research", top_k=3)
    assert len(cro_results) > 0
    for res in cro_results:
        assert res.partition == "playbooks_research"
        assert "shipping" in res.content.lower()

    # 4. Cross-Reranking validation
    top_hit = cro_results[0]
    assert top_hit.doc_id == "baymard_cro_402"
    assert top_hit.dense_score != 0 or top_hit.sparse_score != 0


if __name__ == "__main__":
    test_perception_normalization_and_signal_parsing()
    print("test_perception_normalization_and_signal_parsing: PASSED")
    test_brand_core_and_playbook_ingestion_and_hybrid_search()
    print("test_brand_core_and_playbook_ingestion_and_hybrid_search: PASSED")
    print("=== ALL TSK-03 TESTS PASSED ===")
