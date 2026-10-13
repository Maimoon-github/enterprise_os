# pyright: reportMissingImports=false
"""Validation tests for TSK-06: Brand Compliance, Anti-Hallucination, and HitL Approval Gates."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from core.nodes.human_gate import (
    ApprovalWebhookDispatcher,
    compliance_guardrail_node,
    human_gate_node,
)
from core.persistence import get_memory_checkpointer
from core.state import AgentState, BrandProfile
from guardrails.brand_rules import BrandComplianceFilter, BrandComplianceResult
from guardrails.grounding_verifier import GroundingVerificationResult, GroundingVerifier


SAMPLE_VERIFIED_RAG_CHUNKS = [
    {
        "id": "CHUNK-CLINICAL-001",
        "content": "Clinical trial results (N=120): The dual-peptide barrier serum increased skin hydration by 35% over 14 days, with 92% of participants reporting improved texture.",
    },
    {
        "id": "CHUNK-PRICING-002",
        "content": "AuraGlow Barrier Serum is priced at $68.00 for 50ml, offering standard 3-day shipping at $4.95 or free shipping on orders over $75.00.",
    },
]


def test_brand_compliance_filter():
    """Verify deterministic rule checker rejects forbidden buzzwords and validates style."""
    compliance = BrandComplianceFilter()

    brand = BrandProfile(
        brand_name="AuraGlow",
        tone_of_voice=["Authoritative", "Empathetic"],
        guidelines={"forbidden_terms": ["untested", "secret formula"]},
    )

    # 1. Non-compliant copy (contains forbidden terms and shouting)
    bad_copy = (
        "BUY NOW! THIS REVOLUTIONARY SECRET FORMULA IS A TOTAL GAME-CHANGER! "
        "GUARANTEED OVERNIGHT RESULTS WITH OUR CHEAPEST DEAL EVER!!!!!!!"
    )
    bad_result = compliance.validate_copy(bad_copy, brand=brand, platform="linkedin")

    assert bad_result.is_compliant is False
    assert len(bad_result.violations) >= 3
    assert any("game-changer" in v.lower() for v in bad_result.violations)
    assert any("guaranteed overnight" in v.lower() for v in bad_result.violations)
    assert any("secret formula" in v.lower() for v in bad_result.violations)

    # 2. Compliant copy (clear, professional, optimal readability)
    good_copy = (
        "Healthy skin starts with simple daily habits. "
        "Our light daily serum keeps skin soft and hydrated all day. "
        "See our simple three step routine for clear skin."
    )
    good_result = compliance.validate_copy(good_copy, brand=brand, platform="linkedin")

    assert good_result.is_compliant is True
    assert len(good_result.violations) == 0
    assert good_result.readability_score <= 12.0
    print("test_brand_compliance_filter: PASSED")


def test_anti_hallucination_grounding_verifier():
    """Verify factual claims must cite verified ground-truth RAG chunks."""
    verifier = GroundingVerifier(min_coverage_threshold=0.8)

    # 1. Grounded copy (cites facts present in SAMPLE_VERIFIED_RAG_CHUNKS)
    grounded_copy = (
        "Our dual-peptide barrier serum increased skin hydration by 35% over 14 days. "
        "Available now for $68.00 with transparent standard shipping."
    )
    grounded_result = verifier.verify_grounding(
        copy_text=grounded_copy,
        source_chunks=SAMPLE_VERIFIED_RAG_CHUNKS,
    )

    assert grounded_result.is_grounded is True
    assert grounded_result.grounded_claims_count >= 1
    assert len(grounded_result.ungrounded_claims) == 0
    assert grounded_result.citation_coverage >= 0.8

    # 2. Hallucinated copy (contains unverified fabricated statistics)
    hallucinated_copy = (
        "Our serum delivers an unprecedented 99.8% cure rate in 48 hours for over 50,000 patients, "
        "guaranteeing complete cellular rejuvenation with 0% side effects."
    )
    hallucinated_result = verifier.verify_grounding(
        copy_text=hallucinated_copy,
        source_chunks=SAMPLE_VERIFIED_RAG_CHUNKS,
    )

    assert hallucinated_result.is_grounded is False
    assert len(hallucinated_result.ungrounded_claims) >= 1
    assert hallucinated_result.citation_coverage < 0.5
    print("test_anti_hallucination_grounding_verifier: PASSED")


def test_langgraph_hitl_approval_gate_workflow():
    """Verify LangGraph interrupt_before=['human_gate'], webhook dispatch, and pause/resume."""
    checkpointer = get_memory_checkpointer()

    def draft_node(state: AgentState):
        return {
            "phase": "reasoning",
            "messages": [AIMessage(content="Draft content and ad spend proposal generated.")],
        }

    def execution_node(state: AgentState):
        return {
            "phase": "completed",
            "messages": [AIMessage(content="Action dispatched successfully.")],
        }

    builder = StateGraph(AgentState)
    builder.add_node("draft", draft_node)
    builder.add_node("guardrails", compliance_guardrail_node)
    builder.add_node("human_gate", human_gate_node)
    builder.add_node("execution", execution_node)

    builder.add_edge(START, "draft")
    builder.add_edge("draft", "guardrails")
    builder.add_edge("guardrails", "human_gate")
    builder.add_edge("human_gate", "execution")
    builder.add_edge("execution", END)

    # Compile with interrupt_before=["human_gate"]
    app = builder.compile(checkpointer=checkpointer, interrupt_before=["human_gate"])

    thread_config: RunnableConfig = {"configurable": {"thread_id": "session-tsk-06-gate-test"}}

    brand = BrandProfile(
        brand_name="AuraGlow",
        tone_of_voice=["Authoritative", "Empathetic"],
    )

    initial_state: AgentState = {
        "messages": [HumanMessage(content="Trigger campaign pipeline")],
        "phase": "init",
        "brand_profile": brand,
        "metadata": {
            "draft_copy": "Our dual-peptide barrier serum increased skin hydration by 35% over 14 days.",
            "source_chunks": SAMPLE_VERIFIED_RAG_CHUNKS,
            "action_type": "Publish Live Social Campaign",
        },
        "errors": [],
        "artifacts": [],
    }

    # Step 1: Initial invocation -> Runs up to human_gate and suspends
    app.invoke(initial_state, thread_config)

    snapshot = app.get_state(thread_config)
    assert snapshot.next == ("human_gate",)
    assert snapshot.values["phase"] == "human_gate"

    # Step 2: Test Rejection Flow
    # Human operator rejects action with feedback
    app.update_state(
        thread_config,
        {"human_approved": False, "human_feedback": "Adjust CTA button color and remove hashtag."},
        as_node="human_gate",
    )
    rejected_snapshot = app.get_state(thread_config)
    assert rejected_snapshot.values["human_approved"] is False

    # Step 3: Test Approval Flow
    # Human operator explicitly approves action
    app.update_state(
        thread_config,
        {"human_approved": True, "human_feedback": "Approved for live publishing."},
        as_node="human_gate",
    )

    # Resume graph execution
    app.invoke(None, thread_config)

    final_snapshot = app.get_state(thread_config)
    assert final_snapshot.next == ()
    assert final_snapshot.values["phase"] == "completed"
    assert final_snapshot.values["human_approved"] is True
    print("test_langgraph_hitl_approval_gate_workflow: PASSED")


if __name__ == "__main__":
    test_brand_compliance_filter()
    test_anti_hallucination_grounding_verifier()
    test_langgraph_hitl_approval_gate_workflow()
    print("=== ALL TSK-06 TESTS PASSED ===")
