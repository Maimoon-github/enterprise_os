"""Unit and integration test suite for Task-01: Dual-Tier Memory & Context Engine."""

import os
from pathlib import Path
import pytest
from src.memory.long_term import LongTermMemory
from src.memory.short_term import (
    SessionGraphEdge,
    SessionGraphNode,
    SessionNodeType,
    ShortTermMemory,
    TaskSessionGraph,
)
from src.memory.summarizer import StateSummarizer, TokenBudget
from src.orchestrator.context_isolator import ContextIsolator
from src.orchestrator.state_machine import PipelineStage
from src.schemas.state import (
    BrandProfile,
    MasterEngineState,
    OperationalMode,
)


# ============================================================================
# 1. Context Window Optimization Engine Tests
# ============================================================================


def test_token_budget_stage_allocations():
    """Validates exact stage-based token budget allocations across 16,384 window."""
    assert TokenBudget.SYSTEM_RESERVE == 2500
    assert TokenBudget.STAGE_INPUT_SLICE == 6000
    assert TokenBudget.ACTIVE_SCRATCHPAD == 5500
    assert TokenBudget.GENERATION_HEADROOM == 2384
    assert TokenBudget.TOTAL_WINDOW == 16384

    # Verify mathematical partition
    allocated_sum = (
        TokenBudget.SYSTEM_RESERVE
        + TokenBudget.STAGE_INPUT_SLICE
        + TokenBudget.ACTIVE_SCRATCHPAD
        + TokenBudget.GENERATION_HEADROOM
    )
    assert allocated_sum == TokenBudget.TOTAL_WINDOW
    assert ContextIsolator.STAGE_TOKEN_BUDGET == TokenBudget


def test_context_isolation_bounded_slices(sample_master_state):
    """Verifies specialist agents receive bounded typed state slices rather than monolithic prompt histories."""
    # Analyst slice
    analyst_model = ContextIsolator.get_analyst_slice_model(sample_master_state)
    assert analyst_model.website_url == sample_master_state.brand_profile.website_url
    assert analyst_model.mode == sample_master_state.mode.value
    assert analyst_model.industry == sample_master_state.brand_profile.industry

    # Audience slice
    audience_model = ContextIsolator.get_audience_slice_model(sample_master_state)
    assert audience_model.target_market == sample_master_state.brand_profile.target_market
    assert audience_model.industry == sample_master_state.brand_profile.industry

    # Brand slice
    brand_model = ContextIsolator.get_brand_slice_model(sample_master_state)
    assert brand_model.brand_name == sample_master_state.brand_profile.brand_name
    assert hasattr(brand_model, "headline")
    # Verify no raw DOM tree in brand slice
    assert not hasattr(brand_model, "raw_dom")

    # SEO slice
    seo_model = ContextIsolator.get_seo_slice_model(sample_master_state)
    assert seo_model.website_url == sample_master_state.brand_profile.website_url

    # Growth slice
    growth_model = ContextIsolator.get_growth_slice_model(sample_master_state)
    assert growth_model.mode == sample_master_state.mode.value

    # Validator slice
    validator_model = ContextIsolator.get_validator_slice_model(sample_master_state)
    assert isinstance(validator_model.growth_initiatives, list)


def test_hierarchical_compression_react_trace():
    """Verifies ReAct step traces condense into structured observation digests."""
    raw_traces = [
        {
            "step": 1,
            "action": "navigate_to_url",
            "observation": "Page loaded completely with status 200 OK. " + "Lots of verbose debug text. " * 30,
        },
        {
            "step": 2,
            "action": "extract_dom_headings",
            "observation": "Found 12 headings in main container. " + "Extraneous logs. " * 30,
        },
    ]

    condensed = StateSummarizer.condense_react_trace(raw_traces)
    assert len(condensed) == 2
    assert condensed[0]["step"] == "1"
    assert condensed[0]["action"] == "navigate_to_url"
    assert len(condensed[0]["observation_digest"]) <= 200
    assert "Lots of verbose debug text" in condensed[0]["observation_digest"]


def test_hierarchical_compression_dom_pruning():
    """Verifies verbose raw HTML trees prune into semantic accessibility outlines."""
    raw_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Brand Strategy Pro</title>
        <meta name="description" content="Next generation enterprise brand intelligence">
      </head>
      <body>
        <nav role="navigation">
          <a href="/home">Home</a>
          <a href="/pricing">Pricing</a>
        </nav>
        <main role="main">
          <h1>Enterprise AI Brand Strategy</h1>
          <h2>Autonomous Market Intelligence</h2>
          <p>Unstructured filler text.</p>
        </main>
      </body>
    </html>
    """
    condensed = StateSummarizer.condense_html(raw_html)
    assert condensed["title"] == "Brand Strategy Pro"
    assert condensed["meta_description"] == "Next generation enterprise brand intelligence"
    assert any(h["text"] == "Enterprise AI Brand Strategy" for h in condensed["primary_headings"])


def test_screenshot_buffer_offloading_to_uri_hash(tmp_path):
    """Verifies visual base64 screenshot buffers offload to URI hashes (blob://<sha256>)."""
    fake_screenshot_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk" + "A" * 3000
    uri_hash = StateSummarizer.offload_screenshot_buffer(fake_screenshot_data, storage_dir=str(tmp_path))

    assert uri_hash.startswith("blob://")
    sha_part = uri_hash.replace("blob://", "")
    assert len(sha_part) == 64

    # Verify physical file written to storage directory
    persisted_blob = tmp_path / f"{sha_part}.blob"
    assert persisted_blob.exists()
    assert persisted_blob.read_text(encoding="utf-8") == fake_screenshot_data


def test_scratchpad_automatic_budget_compression(tmp_path):
    """Verifies scratchpads exceeding 5,000 tokens trigger recursive state compression."""
    # Under-budget scratchpad remains intact
    small_scratchpad = {"status": "ok", "agent": "analyst", "note": "minimal data"}
    assert StateSummarizer.compress_scratchpad(small_scratchpad) == small_scratchpad

    # Over-budget scratchpad (> 5000 tokens ~= 20,000 chars)
    large_screenshot = "data:image/png;base64," + "ABCD" * 6000
    large_html = "<html><body><h1>Big Header</h1>" + "<p>Content</p>" * 1000 + "</body></html>"
    traces = [
        {"step": i, "action": f"tool_{i}", "observation": f"detailed result {i} " * 50}
        for i in range(10)
    ]
    heavy_scratchpad = {
        "screenshot": large_screenshot,
        "dom_content": large_html,
        "react_steps": traces,
        "verbose_log": "log line\n" * 1500,
    }

    compressed = StateSummarizer.compress_scratchpad(heavy_scratchpad, max_budget=2000)
    # Screenshot offloaded to URI hash
    assert str(compressed["screenshot"]).startswith("blob://")
    # DOM condensed to outline
    assert isinstance(compressed["dom_content"], dict)
    assert "primary_headings" in compressed["dom_content"]
    # ReAct steps condensed to digests
    assert isinstance(compressed["react_steps"], list)
    assert "observation_digest" in compressed["react_steps"][0]
    # Verbose text truncated
    assert "... [truncated for context budget]" in compressed["verbose_log"]


# ============================================================================
# 2. Short-Term Memory (Task & Session Graph) Tests
# ============================================================================


@pytest.mark.asyncio
async def test_short_term_memory_ephemeral_scratchpad():
    """Tests in-memory working scratchpad and TTL expiration."""
    memory = ShortTermMemory(default_ttl=1)
    await memory.set("test_key", {"status": "in_progress"}, ttl=2)
    val = await memory.get("test_key")
    assert val == {"status": "in_progress"}

    # Stage buffer operations
    await memory.save_stage_buffer("sess_123", "analyst", {"dom_count": 5})
    stage_val = await memory.get_stage_buffer("sess_123", "analyst")
    assert stage_val == {"dom_count": 5}

    # Session purge
    await memory.clear_session("sess_123")
    assert await memory.get_stage_buffer("sess_123", "analyst") is None


@pytest.mark.asyncio
async def test_short_term_memory_typed_session_graph():
    """Tests Pydantic v2 serialization, typing, and directed edges in TaskSessionGraph."""
    memory = ShortTermMemory()
    session_id = "session_graph_test_1"

    # Add initialization node
    node_init = await memory.add_graph_node(
        session_id=session_id,
        agent_id="Supervisor",
        stage=PipelineStage.INITIALIZATION.value,
        node_type=SessionNodeType.INITIALIZATION,
        payload={"brand_name": "Antigravity Corp"},
    )
    assert isinstance(node_init, SessionGraphNode)
    assert node_init.node_type == SessionNodeType.INITIALIZATION

    # Add ReAct step node
    node_step = await memory.add_graph_node(
        session_id=session_id,
        agent_id="Agent_1",
        stage=PipelineStage.ANALYST.value,
        node_type=SessionNodeType.REACT_STEP,
        payload={"action": "vnc_click", "x": 100, "y": 200},
    )

    # Add stage handoff node
    node_handoff = await memory.add_graph_node(
        session_id=session_id,
        agent_id="Agent_1",
        stage=PipelineStage.ANALYST.value,
        node_type=SessionNodeType.STAGE_HANDOFF,
        payload={"output_keys": ["dom_snapshots", "visual_evidence_vnc"]},
    )

    # Retrieve graph and verify topology
    graph = await memory.get_session_graph(session_id)
    assert isinstance(graph, TaskSessionGraph)
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2

    # Verify sequential edges
    assert graph.edges[0].source_node_id == node_init.node_id
    assert graph.edges[0].target_node_id == node_step.node_id
    assert graph.edges[1].source_node_id == node_step.node_id
    assert graph.edges[1].target_node_id == node_handoff.node_id

    # Strict Pydantic v2 serialization and round-trip verification
    serialized_json = graph.model_dump_json()
    deserialized_graph = TaskSessionGraph.model_validate_json(serialized_json)
    assert deserialized_graph.session_id == session_id
    assert len(deserialized_graph.nodes) == 3
    assert deserialized_graph.nodes[0].payload["brand_name"] == "Antigravity Corp"


# ============================================================================
# 3. Long-Term Memory (Cross-Session Knowledge Base & RLS) Tests
# ============================================================================


@pytest.mark.asyncio
async def test_long_term_memory_multi_tenant_isolation():
    """Verifies strict tenant and client isolation boundaries."""
    memory = LongTermMemory()
    await memory.connect()

    tenant_a = "tenant_alpha"
    client_a1 = "client_alpha_1"
    tenant_b = "tenant_beta"
    client_b1 = "client_beta_1"

    # 1. Brand Profile isolation
    await memory.save_brand_profile(
        tenant_id=tenant_a,
        client_id=client_a1,
        brand_name="Alpha Brand",
        website_url="https://alpha.example.com",
        industry="SaaS",
        business_goals=["Expand ARR"],
    )
    await memory.save_brand_profile(
        tenant_id=tenant_b,
        client_id=client_b1,
        brand_name="Beta Brand",
        website_url="https://beta.example.com",
        industry="Fintech",
        business_goals=["Achieve Profitability"],
    )

    # Tenant Alpha querying
    profile_a = await memory.get_brand_profile(tenant_id=tenant_a, client_id=client_a1)
    assert profile_a is not None
    assert profile_a["brand_name"] == "Alpha Brand"

    # Tenant Alpha cannot access Tenant Beta
    profile_cross = await memory.get_brand_profile(tenant_id=tenant_a, client_id=client_b1)
    assert profile_cross is None

    # 2. Historical Baseline isolation
    await memory.save_baseline(
        tenant_id=tenant_a,
        client_id=client_a1,
        brand_name="Alpha Brand",
        website_url="https://alpha.example.com",
        kpi="Organic Traffic",
        baseline="10k visitors/mo",
    )
    baselines_a = await memory.get_baselines(tenant_id=tenant_a, client_id=client_a1)
    assert len(baselines_a) == 1
    assert baselines_a[0]["kpi"] == "Organic Traffic"

    baselines_b = await memory.get_baselines(tenant_id=tenant_b, client_id=client_b1)
    assert len(baselines_b) == 0

    # 3. Strategy Audit Logs isolation
    await memory.save_audit_log(
        session_id="sess_a",
        tenant_id=tenant_a,
        client_id=client_a1,
        recommendation_id="rec_001",
        status="APPROVED",
        audit_data={"ice_score": 8.5},
    )
    audit_a = await memory.get_audit_history(tenant_id=tenant_a, client_id=client_a1)
    assert len(audit_a) == 1
    assert audit_a[0]["recommendation_id"] == "rec_001"

    audit_b = await memory.get_audit_history(tenant_id=tenant_b, client_id=client_b1)
    assert len(audit_b) == 0


@pytest.mark.asyncio
async def test_long_term_memory_competitor_embeddings_768_dim():
    """Verifies verified competitor footprints with 768-dimensional embeddings and cosine similarity search."""
    memory = LongTermMemory()
    await memory.connect()

    tenant_id = "tenant_competitor_test"
    client_id = "client_comp_1"

    # Generate deterministic 768-dimensional mock embeddings
    emb_direct = [0.1] * 768
    emb_indirect = [0.0] * 384 + [0.2] * 384
    query_vector = [0.1] * 768  # Identical direction to emb_direct

    await memory.save_competitor_footprint(
        tenant_id=tenant_id,
        client_id=client_id,
        competitor_name="Direct Competitor Inc",
        domain="direct.example.com",
        positioning_summary="Primary enterprise market rival",
        embedding=emb_direct,
    )

    await memory.save_competitor_footprint(
        tenant_id=tenant_id,
        client_id=client_id,
        competitor_name="Indirect Competitor LLC",
        domain="indirect.example.com",
        positioning_summary="Adjacent niche tool",
        embedding=emb_indirect,
    )

    # Cross-tenant competitor to verify isolation
    await memory.save_competitor_footprint(
        tenant_id="tenant_foreign",
        client_id="client_foreign",
        competitor_name="Foreign Competitor",
        domain="foreign.example.com",
        positioning_summary="Should not appear in search",
        embedding=emb_direct,
    )

    results = await memory.query_competitor_footprints(
        tenant_id=tenant_id,
        client_id=client_id,
        query_embedding=query_vector,
        top_k=5,
    )

    assert len(results) == 2
    # Verify top result is Direct Competitor with higher cosine similarity
    assert results[0]["competitor_name"] == "Direct Competitor Inc"
    assert results[0]["similarity_score"] > results[1]["similarity_score"]
    # Foreign competitor is strictly isolated
    assert all(r["competitor_name"] != "Foreign Competitor" for r in results)
