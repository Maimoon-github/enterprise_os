from typing import Annotated, Any

from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command


def create_scoped_subgraph_handoff(
    *, subgraph_name: str, tool_name: str, description: str
) -> BaseTool:
    """Create a scoped supervisor handoff tool delegating execution to a target subgraph

    using LangGraph Command(goto=..., graph=Command.PARENT, update=...).
    """

    @tool(tool_name, description=description)
    def handoff_to_subgraph(
        task_description: Annotated[str, "Scoped objective and constraints for the subgraph team."],
        state: Annotated[dict[str, Any], InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        active_skills = state.get("active_skills", []) if isinstance(state, dict) else []
        return Command(
            goto=subgraph_name,
            graph=Command.PARENT,
            update={
                "task_description": task_description,
                "active_skills": active_skills,
            },
        )

    return handoff_to_subgraph
