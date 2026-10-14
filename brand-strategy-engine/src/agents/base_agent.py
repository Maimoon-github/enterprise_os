"""Abstract base agent providing ReAct execution loop, Ollama routing, and tool access control."""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
import httpx
from src.schemas.state import ReActStep

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
        "sandbox_permissions": "No direct access",
        "network_bridge": "Internal loopback only",
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
        "network_bridge": "Internal VNC sandbox only",
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
        "network_bridge": "Denied",
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
        "network_bridge": "Denied",
    },
    "Agent_4": {
        "role": "SEO & Content Strategist",
        "whitelisted_tools": [
            "analyze_onpage_elements",
            "cluster_serp_intent",
            "scan_content_gaps",
            "rag_query",
        ],
        "sandbox_permissions": "Read-only (DOM snapshots)",
        "network_bridge": "Denied",
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
        "network_bridge": "Denied",
    },
    "Agent_6": {
        "role": "Strategy Validator",
        "whitelisted_tools": [
            "verify_evidence_provenance",
            "audit_logical_consistency",
            "validate_metric_feasibility",
            "issue_veto",
        ],
        "sandbox_permissions": "Read-only (Raw evidence blob)",
        "network_bridge": "Denied",
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
        raw_url = os.getenv("OLLAMA_BASE_URL", ollama_base_url).rstrip("/")
        if raw_url.endswith("/v1"):
            raw_url = raw_url[:-3]
        self.ollama_base_url = raw_url
        self.tools: Dict[str, Callable] = {}
        # Declarative default from master policy if registered
        default_whitelist = MASTER_RBAC_POLICY.get(agent_id, {}).get("whitelisted_tools", [])
        self.whitelisted_tool_names: List[str] = list(default_whitelist)
        self.execution_trace: List[ReActStep] = []

    def verify_sandbox_access(self, capability: str) -> bool:
        """Enforces declarative sandbox permissions based on agent profile."""
        policy = MASTER_RBAC_POLICY.get(self.agent_id, {})
        sandbox_perm = policy.get("sandbox_permissions", "None").lower()
        cap_norm = capability.lower().strip()
        allowed = False

        if cap_norm in ("vnc", "display", "mouse", "keyboard"):
            allowed = "read-write" in sandbox_perm
        elif cap_norm in ("dom_snapshot", "dom_snapshots", "dom"):
            allowed = "read-write" in sandbox_perm or "dom snapshot" in sandbox_perm
        elif cap_norm in ("raw_evidence", "raw_evidence_blob", "evidence"):
            allowed = "read-write" in sandbox_perm or "raw evidence" in sandbox_perm
        else:
            allowed = False

        if not allowed:
            raise PermissionError(
                f"RBAC Policy Violation: Agent {self.agent_id} ({self.name}) is denied access to sandbox capability '{capability}'."
            )
        return True

    def verify_network_access(self, target_network: str) -> bool:
        """Enforces declarative network bridge boundaries based on agent profile."""
        policy = MASTER_RBAC_POLICY.get(self.agent_id, {})
        bridge = policy.get("network_bridge", "Denied").lower()
        target_norm = target_network.lower().strip()
        allowed = False

        if "loopback" in bridge and "loopback" in target_norm:
            allowed = True
        elif "vnc" in bridge and "vnc" in target_norm:
            allowed = True

        if not allowed:
            raise PermissionError(
                f"RBAC Network Violation: Agent {self.agent_id} ({self.name}) is denied network bridge access to '{target_network}' (Permitted: {policy.get('network_bridge')})."
            )
        return True

    def register_tool(self, tool_name: str, tool_func: Callable) -> None:
        """Registers a tool if permitted under the agent's declarative whitelist."""
        if tool_name not in self.whitelisted_tool_names:
            raise PermissionError(
                f"Security Violation: Agent {self.agent_id} ({self.name}) is not authorized to use tool '{tool_name}'."
            )
        self.tools[tool_name] = tool_func

    async def invoke_tool(self, tool_name: str, **kwargs) -> Any:
        """Executes an authorized tool after verifying runtime whitelist boundaries."""
        if tool_name not in self.whitelisted_tool_names:
            raise PermissionError(
                f"Security Violation: Tool '{tool_name}' is not authorized for Agent {self.agent_id} under master RBAC policy."
            )
        if tool_name not in self.tools:
            raise RuntimeError(
                f"Error: Tool '{tool_name}' is whitelisted for {self.agent_id} but not yet registered."
            )
        tool = self.tools[tool_name]
        import inspect
        if inspect.iscoroutinefunction(tool):
            return await tool(**kwargs)
        else:
            return tool(**kwargs)

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
        reflection: str = "",
        error: Optional[str] = None,
    ) -> ReActStep:
        """Executes a single Reason -> Act -> Observe -> Reflect step producing a typed Pydantic record."""
        # 1. Reason
        logger.info("[%s Step %d] Reason: %s", self.name, step_number, thought)

        # 2. Act
        observation = ""
        if action not in self.whitelisted_tool_names:
            msg = f"Security Violation: Tool '{action}' is not authorized for Agent {self.agent_id} under master RBAC policy."
            logger.warning("RBAC Policy Violation in %s: %s", self.agent_id, msg)
            raise PermissionError(msg)

        try:
            res = await self.invoke_tool(action, **action_args)
            observation = str(res)
        except PermissionError:
            raise
        except Exception as e:
            error = str(e)
            observation = f"Tool Execution Error: {e}"

        # 3. Observe
        logger.info(
            "[%s Step %d] Observe: %s",
            self.name,
            step_number,
            observation[:120] if len(observation) > 120 else observation,
        )

        # 4. Reflect
        if not reflection:
            if error:
                reflection = f"Step {step_number} encountered tool error: {error}. Corrective reasoning required."
            else:
                reflection = f"Step {step_number} action '{action}' verified. Intermediate observations registered."
        logger.info("[%s Step %d] Reflect: %s", self.name, step_number, reflection)

        # Record typed Pydantic ReAct step
        step_record = ReActStep(
            step=step_number,
            thought=thought,
            action=action,
            args=action_args,
            observation=observation,
            reflection=reflection,
            error=error,
        )
        self.execution_trace.append(step_record)
        return step_record
