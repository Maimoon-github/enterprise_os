import pytest
from app.orchestrator.graph import master_orchestrator_graph

@pytest.mark.asyncio
async def test_graph_initialization():
    assert master_orchestrator_graph is not None
