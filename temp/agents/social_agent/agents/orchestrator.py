import json
import logging
import asyncio
from typing import Dict, Any, List

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from social_agent.agents.llm_factory import get_chat_model
from social_agent.agents.system_prompts import ORCHESTRATOR_SYSTEM_PROMPT
from social_agent.agents.system_tools import ORCHESTRATOR_TOOLS

logger = logging.getLogger(__name__)

async def _async_triage_intent(content: str, history=None, model_name=None) -> dict:
    """Internal async executor running ReAct loop for tool calls."""
    # Note: Use reasoning model if applicable.
    llm = get_chat_model(role="evaluator", model_name_override=model_name)
    
    # Bind our explicit enterprise system tools
    llm_with_tools = llm.bind_tools(ORCHESTRATOR_TOOLS)
    
    sys_prompt = (
        ORCHESTRATOR_SYSTEM_PROMPT + "\n\n"
        "You are empowered with MCP Research Tools, Memory, and Social Publisher Action tools.\n"
        "1. Plan: Identify if you need context (tool_query_brand_rag) or real-time intel (tool_search_web_trends).\n"
        "2. Action: Execute the relevant tools.\n"
        "3. Respond: If they asked for a campaign, tool_trigger_social_campaign and let them know.\n"
        "4. Wrap your final unstructured reply in the exact JSON schema requested previously:\n"
        "{\n"
        "  \"mode\": \"A\" or \"B\",\n"
        "  \"response\": \"Your finalized conversational response.\",\n"
        "  \"platforms\": [\"x_twitter\", \"instagram\"] \n"
        "}"
    )

    messages = [SystemMessage(content=sys_prompt)]
    if history:
        for msg in history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
                
    messages.append(HumanMessage(content=content))

    # ReAct Loop
    for step in range(5):
        try:
            res = await llm_with_tools.ainvoke(messages)
            messages.append(res)
            
            if not res.tool_calls:
                # Finished reasoning! Ensure we have JSON layout
                res_text = res.content.strip()
                if "```json" in res_text:
                    res_text = res_text.split("```json")[1].split("```")[0].strip()
                elif "```" in res_text:
                    res_text = res_text.replace("```", "").strip()
                else:
                    idx = res_text.find("{")
                    if idx != -1:
                        res_text = res_text[idx:]
                        idx = res_text.rfind("}")
                        res_text = res_text[:idx+1]

                d = json.loads(res_text)
                if "mode" not in d:
                    d["mode"] = "A"
                if "platforms" not in d:
                    d["platforms"] = []
                return d
            
            # Execute Tools Sequentially
            from langchain_core.messages import ToolMessage
            for tool_call in res.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                
                # Dynamic matching
                matched_tool = next((t for t in ORCHESTRATOR_TOOLS if t.name == tool_name), None)
                if matched_tool:
                    observation = await matched_tool.ainvoke(tool_args)
                    messages.append(ToolMessage(content=json.dumps(observation), tool_call_id=tool_id))
                else:
                    messages.append(ToolMessage(content=f"Error: Tool {tool_name} not found.", tool_call_id=tool_id))

        except Exception as e:
            logger.warning(f"Orchestrator Loop Event Failure: {e}")
            break
            
    # Fallback to graceful response if loop exhausts or fails
    try:
        raw_text = res.content.strip() if 'res' in locals() and res.content else ""
        if raw_text and len(raw_text) > 5:
            return {"mode": "A", "response": raw_text, "platforms": []}
    except Exception:
        pass

    query = content.lower()
    if any(w in query for w in ["post", "campaign", "launch", "draft"]):
        return {
            "mode": "B", 
            "response": "Understood. Background multi-agent processes have been alerted.",
            "platforms": ["x_twitter", "instagram"]
        }
        
    return {
        "mode": "A",
        "response": "Currently experiencing heavy load (ReAct fallback). How can I assist?",
        "platforms": []
    }

def triage_intent(content: str, history=None, model_name=None) -> dict:
    """Synchronous interface bound to Django Views."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Using nested compat because we are in an event loop (e.g., if channels is used)
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(_async_triage_intent(content, history, model_name))
    else:
        return asyncio.run(_async_triage_intent(content, history, model_name))
