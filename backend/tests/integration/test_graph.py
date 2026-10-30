import pytest
from app.orchestrator.graph import (
    DEFAULT_RECURSION_LIMIT,
    builder,
    master_orchestrator_graph,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


@pytest.mark.asyncio
async def test_graph_initialization():
    """Verify MasterOrchestratorGraph compiles cleanly with recursion limit."""
    assert master_orchestrator_graph is not None
    assert DEFAULT_RECURSION_LIMIT == 25


@pytest.mark.asyncio
async def test_3_node_interrupt_gate_approval():
    """Verify the 3-node approval gate interrupts safely and resumes with approval."""
    test_graph = builder.compile(checkpointer=MemorySaver())
    thread_id = "test_hitl_approval_thread"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": DEFAULT_RECURSION_LIMIT,
    }

    # 1. Initial run enters prepare_publish_payload_node and halts at human_approval_gate_node
    result = await test_graph.ainvoke(
        {"campaign_id": "camp_hitl_01", "thread_id": thread_id},
        config=config,
    )
    assert "__interrupt__" in result
    interrupts = result["__interrupt__"]
    assert len(interrupts) > 0
    payload = interrupts[0].value
    assert payload["step_name"] == "human_approval_gate_node"
    assert "campaign_blueprint" in payload

    # Verify checkpointer recorded pause state
    state = await test_graph.aget_state(config)
    assert state.next == ("human_approval_gate_node",)
    assert state.values.get("approval_status") == "pending"

    # 2. Super-step replay safety: Resume with approval
    resume_result = await test_graph.ainvoke(
        Command(resume={"approved": True, "notes": "LGTM"}),
        config=config,
    )
    assert "__interrupt__" not in resume_result

    final_state = await test_graph.aget_state(config)
    assert final_state.next == ()
    assert final_state.values.get("approval_status") == "approved"
    assert final_state.values.get("human_approved") is True
    assert len(final_state.values.get("platform_publish_results", [])) == 8


@pytest.mark.asyncio
async def test_3_node_interrupt_gate_rejection_and_bounded_reflexion():
    """Verify rejection loop appends to critique_history and bounds revisions (max_revisions <= 2)."""
    test_graph = builder.compile(checkpointer=MemorySaver())
    thread_id = "test_hitl_rejection_thread"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": DEFAULT_RECURSION_LIMIT,
    }

    # Initial run -> Interrupt
    await test_graph.ainvoke(
        {"campaign_id": "camp_hitl_02", "thread_id": thread_id},
        config=config,
    )

    # Rejection 1 -> revisions = 1
    await test_graph.ainvoke(
        Command(resume={"approved": False, "notes": "Rewrite LinkedIn hook"}),
        config=config,
    )
    state_rev1 = await test_graph.aget_state(config)
    assert state_rev1.next == ("human_approval_gate_node",)
    assert state_rev1.values.get("revision_count") == 1
    assert "Rewrite LinkedIn hook" in state_rev1.values.get("critique_history", [])

    # Rejection 2 -> revisions = 2
    await test_graph.ainvoke(
        Command(resume={"approved": False, "notes": "Adjust tone for YouTube"}),
        config=config,
    )
    state_rev2 = await test_graph.aget_state(config)
    assert state_rev2.next == ("human_approval_gate_node",)
    assert state_rev2.values.get("revision_count") == 2
    assert len(state_rev2.values.get("critique_history", [])) == 2

    # Rejection 3 -> max_revisions (2) exceeded, graph terminates to prevent Reflexion oscillation
    await test_graph.ainvoke(
        Command(resume={"approved": False, "notes": "Still unsatisfactory"}),
        config=config,
    )
    final_state = await test_graph.aget_state(config)
    assert final_state.next == ()
    assert final_state.values.get("approval_status") == "rejected"
    assert final_state.values.get("revision_count") == 3
