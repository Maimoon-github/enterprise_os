# pyright: reportMissingImports=false
"""Validation tests for TSK-07: Content Engine, 1-to-N Repurposing, MCP Hub, and Persistence."""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

try:
    from agent_sandbox import Sandbox  # type: ignore
except ImportError:
    from agent_sandbox.client import Sandbox  # type: ignore
from content.pillar_allocator import PillarAllocator, PillarBalanceReport, PillarSlot
from content.repurposing_engine import (
    PlatformAsset,
    RepurposingEngine,
    RepurposingPackage,
)
from core.nodes.execution_node import content_execution_node
from core.state import AgentState, BrandProfile


def test_strategic_content_pillar_allocation():
    """Verify PillarAllocator enforces 35% Educational, 25% Proof, 20% Story, and 20% Offers."""
    allocator = PillarAllocator()
    brand = BrandProfile(
        brand_name="AuraGlow Skincare",
        target_audience="D2C Skincare Shoppers",
    )

    # Allocate a 20-slot monthly queue
    slots = allocator.allocate_schedule(total_slots=20, brand=brand)
    assert len(slots) == 20
    assert all(isinstance(s, PillarSlot) for s in slots)

    # Verify balance report
    report: PillarBalanceReport = allocator.verify_pillar_balance(slots)
    assert report.is_balanced is True
    assert report.total_slots == 20

    # Check exact counts: 7 (35%), 5 (25%), 4 (20%), 4 (20%)
    assert report.counts["35% Educational"] == 7
    assert report.counts["25% Proof/Demos"] == 5
    assert report.counts["20% Brand Story"] == 4
    assert report.counts["20% Offers/Conversion"] == 4

    # Verify interleaved cadence (no 2 offers consecutively)
    pillars = [s.pillar for s in slots]
    for i in range(len(pillars) - 1):
        if pillars[i] == "20% Offers/Conversion":
            assert pillars[i + 1] != "20% Offers/Conversion"

    print("test_strategic_content_pillar_allocation: PASSED")


def test_1_to_n_repurposing_engine():
    """Verify RepurposingEngine derives 4 native platform assets from a single case study."""
    engine = RepurposingEngine()
    brand = BrandProfile(
        brand_name="AuraGlow Skincare",
        tone_of_voice=["Authoritative", "Empathetic"],
    )

    case_study = (
        "Clinical and storefront case study: AuraGlow eliminated hidden shipping costs and added upfront fee transparency. "
        "Over a 30-day trial with 15,000 visitors, checkout conversion increased by 35% and return purchase rate hit 28%."
    )

    package: RepurposingPackage = engine.repurpose(
        source_text=case_study,
        title="AuraGlow Storefront Optimization Case Study",
        pillar="25% Proof/Demos",
        brand=brand,
    )

    assert package.source_title == "AuraGlow Storefront Optimization Case Study"
    assert len(package.assets) == 4
    assert set(package.assets.keys()) == {"linkedin", "carousel", "video_script", "newsletter"}

    # 1. LinkedIn Post
    li = package.assets["linkedin"]
    assert "AuraGlow" in li.headline or "AuraGlow" in li.body
    assert li.character_count > 100
    assert li.character_count < 3000

    # 2. Carousel
    carousel = package.assets["carousel"]
    assert "Slide 1" in carousel.body
    assert "Slide 5" in carousel.body
    assert carousel.metadata.get("slide_count") == 5

    # 3. Short-Form Video Script
    video = package.assets["video_script"]
    assert "[0:00" in video.body or "HOOK" in video.body
    assert video.metadata.get("duration_seconds") == 60

    # 4. Email Newsletter
    email = package.assets["newsletter"]
    assert "Subject:" in email.body
    assert "Preview:" in email.body

    print("test_1_to_n_repurposing_engine: PASSED")


def test_content_execution_node_and_workspace_persistence():
    """Verify LangGraph execution node dispatches via MCP hub and writes /home/gem/published_strategy.md."""
    brand = BrandProfile(
        brand_name="AuraGlow Skincare",
        tone_of_voice=["Authoritative", "Empathetic"],
        target_audience="D2C Skincare Shoppers",
    )

    case_study_text = (
        "Storefront audit case study: AuraGlow resolved Baymard checkout friction and hidden shipping fees. "
        "Hydration barrier trials verified 35% improvement over 14 days."
    )

    initial_state: AgentState = {
        "messages": [HumanMessage(content="Trigger content execution node")],
        "phase": "action",
        "brand_profile": brand,
        "metadata": {
            "source_case_study": case_study_text,
            "case_study_title": "AuraGlow Barrier Restoration Case Study",
            "schedule_slots": 20,
        },
        "errors": [],
        "artifacts": [],
    }

    # 1. Single node execution
    output = content_execution_node(initial_state)

    assert output["phase"] == "completed"
    assert "/home/gem/published_strategy.md" in output["artifacts"]
    assert len(output["messages"]) == 1

    # 2. Verify file persistence directly in the AIO Sandbox container
    client = Sandbox(base_url="http://127.0.0.1:8080", headers={"X-AIO-API-Key": "aio-secret-key"})
    file_res = client.file.read_file(file="/home/gem/published_strategy.md")
    assert file_res.success is True and hasattr(file_res.data, "content")
    file_content = str(getattr(file_res.data, "content", ""))

    assert "AuraGlow Skincare Multi-Channel Content & Publishing Strategy" in file_content
    assert "35% Educational" in file_content
    assert "25% Proof/Demos" in file_content
    assert "LinkedIn Thought Leadership Post" in file_content
    assert "5-Slide Educational Visual Carousel" in file_content
    assert "60-Second Short-Form Video Script" in file_content
    assert "Email Nurturing Broadcast" in file_content

    # 3. LangGraph StateGraph compiled workflow execution
    workflow = StateGraph(AgentState)
    workflow.add_node("execution_node", content_execution_node)
    workflow.add_edge(START, "execution_node")
    workflow.add_edge("execution_node", END)

    app = workflow.compile()
    final_state = app.invoke(initial_state)

    assert final_state["phase"] == "completed"
    assert "/home/gem/published_strategy.md" in final_state["artifacts"]
    assert len(final_state["messages"]) == 2  # 1 Human + 1 AI
    print("test_content_execution_node_and_workspace_persistence: PASSED")


if __name__ == "__main__":
    test_strategic_content_pillar_allocation()
    test_1_to_n_repurposing_engine()
    test_content_execution_node_and_workspace_persistence()
    print("=== ALL TSK-07 TESTS PASSED ===")
