# pyright: reportMissingImports=false, reportGeneralTypeIssues=false, reportArgumentType=false
"""Validation tests for TSK-02: State Schemas, Checkpointing, and Vector DB."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from core.persistence import (
    VectorRelationalClient,
    get_memory_checkpointer,
    get_postgres_checkpointer,
)
from core.state import AgentState, AuditMetrics, BrandProfile


def test_state_schemas_serialization():
    brand = BrandProfile(
        brand_name="GlowSkin eCommerce",
        tone_of_voice=["Authoritative", "Empathetic"],
        target_audience="D2C Skincare Shoppers",
    )
    audit = AuditMetrics(
        reach=100000,
        traffic=25000,
        conversions=750,
        cac=30.0,
        clv=120.0,
        roas=4.0,
        health_ratio=4.0,
    )
    assert brand.brand_name == "GlowSkin eCommerce"
    assert audit.health_ratio >= 3.0
    assert "35% Educational" in brand.core_pillars

    state: AgentState = {
        "messages": [HumanMessage(content="Initialize audit")],
        "phase": "perception",
        "brand_profile": brand,
        "audit_metrics": audit,
        "errors": [],
        "artifacts": ["audit_summary.md"],
    }
    assert state["phase"] == "perception"
    assert len(state["messages"]) == 1


def test_hitl_checkpoint_pause_resume():
    def perception_node(state: AgentState):
        return {
            "phase": "reasoning",
            "messages": [AIMessage(content="Perception complete.")],
        }

    def reasoning_node(state: AgentState):
        return {
            "phase": "human_gate",
            "messages": [AIMessage(content="Campaign proposal generated. Requires approval.")],
        }

    def human_gate_node(state: AgentState):
        return {
            "phase": "action",
            "messages": [AIMessage(content="Human gate approved action dispatch.")],
            "human_approved": True,
        }

    def action_node(state: AgentState):
        return {
            "phase": "completed",
            "messages": [AIMessage(content="Actions executed successfully.")],
        }

    builder = StateGraph(AgentState)  # type: ignore[arg-type]
    builder.add_node("perception", perception_node)
    builder.add_node("reasoning", reasoning_node)
    builder.add_node("human_gate", human_gate_node)
    builder.add_node("action", action_node)

    builder.add_edge(START, "perception")
    builder.add_edge("perception", "reasoning")
    builder.add_edge("reasoning", "human_gate")
    builder.add_edge("human_gate", "action")
    builder.add_edge("action", END)

    checkpointer = get_memory_checkpointer()
    graph = builder.compile(checkpointer=checkpointer, interrupt_before=["human_gate"])

    thread_config = {"configurable": {"thread_id": "session-tsk-02-001"}}
    graph.invoke({"messages": [HumanMessage(content="Start run")], "phase": "perception"}, thread_config)

    # Verify suspension at human_gate
    snapshot = graph.get_state(thread_config)
    assert snapshot.next == ("human_gate",)
    assert snapshot.values["phase"] == "human_gate"

    # Resume execution
    graph.invoke(None, thread_config)
    resumed_snapshot = graph.get_state(thread_config)
    assert resumed_snapshot.next == ()
    assert resumed_snapshot.values["phase"] == "completed"
    assert resumed_snapshot.values["human_approved"] is True


def test_postgres_pgvector_storage_and_search():
    client = VectorRelationalClient()

    # 1. Brand State Embedding & Cosine Similarity
    embedding_brand = [(float(i + 1) / 1536.0) for i in range(1536)]
    brand_id = f"brand_test_{id(client)}"
    record_id = client.save_brand_state(
        brand_id=brand_id,
        profile_data={"brand_name": "Test Brand", "niche": "eCommerce"},
        embedding=embedding_brand,
        version=1,
    )
    assert record_id is not None

    brand_results = client.search_brand_state(embedding_brand, limit=50)
    assert len(brand_results) > 0
    assert any(r["brand_id"] == brand_id for r in brand_results)
    assert brand_results[0]["similarity"] > 0.999

    # 2. Episodic Post-Mortem Embedding & Cosine Similarity
    embedding_pm = [-(float(i + 1) / 1536.0) for i in range(1536)]
    pm_id = client.save_episodic_post_mortem(
        task_id="task_audit_99",
        phase="evaluation",
        outcome="success",
        reflection="Checkout form audit identified 2 Baymard heuristic violations.",
        metrics={"health_ratio": 3.8, "violations": 2},
        embedding=embedding_pm,
    )
    assert pm_id is not None

    pm_results = client.search_episodic_post_mortems(embedding_pm, limit=1)
    assert len(pm_results) > 0
    assert pm_results[0]["task_id"] == "task_audit_99"
    assert pm_results[0]["similarity"] > 0.999


if __name__ == "__main__":
    test_state_schemas_serialization()
    print("test_state_schemas_serialization: PASSED")
    test_hitl_checkpoint_pause_resume()
    print("test_hitl_checkpoint_pause_resume: PASSED")
    test_postgres_pgvector_storage_and_search()
    print("test_postgres_pgvector_storage_and_search: PASSED")
    print("=== ALL TSK-02 TESTS PASSED ===")

