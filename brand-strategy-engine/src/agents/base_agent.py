"""Abstract base agent providing ReAct execution loop, Ollama routing, and tool access control."""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


MASTER_RBAC_POLICY: Dict[str, Dict[str, Any]] = {
    "Agent_0": {
        "role": "Brand Strategy Orchestrator",
        "whitelisted_tools": [
            "delegate_task",
            "merge_agent_payload",
            "route_revisions",
            "compile_strategy_dossier",
        ],
        "sandbox_permissions": "None",
        "network_bridge": "internal_loopback",
    },
    "Agent_1": {
        "role": "Website & Social Platform Analyst",
        "whitelisted_tools": [
            "vnc_navigate",
            "vnc_interact",
            "capture_visual_evidence",
            "extract_dom_tree",
            "rag_query",
        ],
        "sandbox_permissions": "Read-Write (Mouse, Keyboard, Display)",
        "network_bridge": "internal_vnc_sandbox",
    },
    "Agent_2": {
        "role": "Audience Strategist",
        "whitelisted_tools": [
            "query_market_demographics",
            "map_customer_journey",
            "calculate_friction",
            "rag_query",
        ],
        "sandbox_permissions": "None",
        "network_bridge": "denied",
    },
    "Agent_3": {
        "role": "Brand Strategist",
        "whitelisted_tools": [
            "extract_brand_voice",
            "benchmark_differentiation",
            "evaluate_uvp",
            "rag_query",
        ],
        "sandbox_permissions": "None",
        "network_bridge": "denied",
    },
    "Agent_4": {
        "role": "SEO & Content Strategist",
        "whitelisted_tools": [
            "analyze_onpage_elements",
            "cluster_serp_intent",
            "scan_content_gaps",
            "rag_query",
        ],
        "sandbox_permissions": "Read-Only (DOM snapshots)",
        "network_bridge": "denied",
    },
    "Agent_5": {
        "role": "Growth Strategist",
        "whitelisted_tools": [
            "calculate_ice_score",
            "model_growth_projection",
            "build_recommendation",
            "rag_query",
        ],
        "sandbox_permissions": "None",
        "network_bridge": "denied",
    },
    "Agent_6": {
        "role": "Strategy Validator",
        "whitelisted_tools": [
            "verify_evidence_provenance",
            "audit_logical_consistency",
            "validate_metric_feasibility",
            "issue_veto",
        ],
        "sandbox_permissions": "Read-Only (Raw evidence blob)",
        "network_bridge": "denied",
    },
}


class BaseAgent(ABC):
    """Abstract agent foundation with Reason-Act-Observe-Reflect mechanics."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        model_name: str,
        system_prompt: str,
        context_window: int = 16384,
        temperature: float = 0.1,
        ollama_base_url: str = "http://localhost:11434",
    ):
        self.agent_id = agent_id
        self.name = name
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.context_window = context_window
        self.temperature = temperature
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", ollama_base_url).rstrip("/")
        self.tools: Dict[str, Callable] = {}
        # Declarative default from master policy if registered
        default_whitelist = MASTER_RBAC_POLICY.get(agent_id, {}).get("whitelisted_tools", [])
        self.whitelisted_tool_names: List[str] = list(default_whitelist)
        self.execution_trace: List[Dict[str, Any]] = []

    def verify_sandbox_access(self, capability: str) -> bool:
        """Enforces declarative sandbox permissions based on agent profile."""
        policy = MASTER_RBAC_POLICY.get(self.agent_id, {})
        sandbox_perm = policy.get("sandbox_permissions", "None")
        if capability in ("vnc", "display", "mouse", "keyboard"):
            allowed = "Read-Write" in sandbox_perm or "Display" in sandbox_perm
        elif capability in ("dom_snapshot", "raw_evidence"):
            allowed = "Read-Only" in sandbox_perm or "Read-Write" in sandbox_perm
        else:
            allowed = False

        if not allowed:
            raise PermissionError(
                f"RBAC Policy Violation: Agent {self.agent_id} ({self.name}) is denied access to sandbox capability '{capability}'."
            )
        return True

    def register_tool(self, tool_name: str, tool_func: Callable) -> None:
        """Registers a tool if permitted under the agent's declarative whitelist."""
        if tool_name not in self.whitelisted_tool_names:
            raise PermissionError(
                f"Security Violation: Agent {self.agent_id} ({self.name}) is not authorized to use tool '{tool_name}'."
            )
        self.tools[tool_name] = tool_func

    async def invoke_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
    ) -> str:
        """Sends chat request to local Ollama instance with fallback handling."""
        temp = temperature if temperature is not None else self.temperature
        payload = {
            "model": self.model_name,
            "messages": messages,
            "options": {
                "temperature": temp,
                "num_ctx": self.context_window,
            },
            "stream": False,
        }

        url = f"{self.ollama_base_url}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data.get("message", {}).get("content", "")
                    return msg
        except Exception as e:
            logger.debug("Ollama model %s unavailable (%s); executing deterministic fallback", self.model_name, e)

        return self.fallback_execution(messages)

    @abstractmethod
    def fallback_execution(self, messages: List[Dict[str, str]]) -> str:
        """Deterministic response generator when running offline without active Ollama server."""
        ...

    @abstractmethod
    async def run(self, state_slice: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the agent's ReAct cycle on its designated state slice."""
        ...

    async def react_step(
        self,
        step_number: int,
        thought: str,
        action: str,
        action_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Executes a single Reason -> Act -> Observe -> Reflect step."""
        # Reason
        logger.info("[%s Step %d] Reason: %s", self.name, step_number, thought)

        # Act
        observation = ""
        error = None
        if action in self.tools:
            try:
                tool = self.tools[action]
                import inspect
                if inspect.iscoroutinefunction(tool):
                    res = await tool(**action_args)
                else:
                    res = tool(**action_args)
                observation = str(res)
            except Exception as e:
                error = str(e)
                observation = f"Tool Execution Error: {e}"
        elif action in self.whitelisted_tool_names:
            error = f"Error: Tool '{action}' is whitelisted for {self.agent_id} but not yet registered."
            observation = error
        else:
            error = f"Security Violation: Tool '{action}' is not authorized for Agent {self.agent_id} under master RBAC policy."
            observation = error
            logger.warning("RBAC Policy Violation in %s: Tool '%s' is not authorized", self.agent_id, action)

        # Observe & Record
        step_record = {
            "step": step_number,
            "thought": thought,
            "action": action,
            "args": action_args,
            "observation": observation,
            "error": error,
        }
        self.execution_trace.append(step_record)
        return step_record
