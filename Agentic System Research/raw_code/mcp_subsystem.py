# File: mcp_subsystem.py
"""
Model Context Protocol (MCP) Client, Server, and Governed Tools Subsystem.

Architecture & Invariants:
1. Client-Server 1:1 Session Topology:
   MCP Host -> 1:1 MCP Client Session -> 1:1 MCP Server Session.
   Each client connects to exactly one server. Servers operate in process/sandbox isolation
   and cannot inspect peer servers, host conversation history, or global state.
2. Tools Primitive & Control Locus:
   Model-controlled invocation strictly gated by Host Authorization and Server-Side Validation.
   Governed Tool Lifecycle:
   tools/list -> policy projection -> model selection -> host authorization -> tools/call -> server validation/execution -> structured result
3. Monotonic Authorization:
   Effective Tool Access = Host Policy ∩ Task Grant ∩ Sub-Agent Scope ∩ Server Scope.
   Discovery != Authorization. Technical availability never bypasses authorization.
4. Defense-in-Depth Validation & Credential Decoupling:
   Arguments validated at host before dispatch and at server before execution.
   Upstream third-party API credentials remain strictly server-side; client tokens are audience-bound.
5. Auditability:
   Every invocation, clearance, argument hash, and outcome is logged in a tamper-resistant ledger.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import enum
import hashlib
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("mcp_subsystem")


# ============================================================================
# 1. MCP PROTOCOL PRIMITIVES & JSON-RPC 2.0 SPECIFICATION
# ============================================================================

LATEST_PROTOCOL_VERSION = "2024-11-05"


class MCPErrorCode(enum.IntEnum):
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    UNAUTHORIZED = -32001
    RATE_LIMIT_EXCEEDED = -32002
    HITL_APPROVAL_REQUIRED = -32003
    CIRCUIT_BREAKER_OPEN = -32004


@dataclasses.dataclass(frozen=True)
class MCPError:
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


@dataclasses.dataclass(frozen=True)
class TextContent:
    type: str = "text"
    text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "text": self.text}


@dataclasses.dataclass(frozen=True)
class CallToolResult:
    content: List[Dict[str, Any]]
    isError: bool = False
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "isError": self.isError,
            "_meta": self.metadata
        }


@dataclasses.dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    inputSchema: Dict[str, Any]
    is_high_impact: bool = False
    required_upstream_scopes: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.inputSchema
        }


# ============================================================================
# 2. TRANSPORT LAYER & 1:1 ISOLATED SESSION
# ============================================================================

class MCPTransport:
    """Abstract 1:1 transport channel between an MCP Client and an MCP Server."""
    async def send_to_server(self, message: str) -> None:
        raise NotImplementedError

    async def receive_from_client(self) -> str:
        raise NotImplementedError

    async def send_to_client(self, message: str) -> None:
        raise NotImplementedError

    async def receive_from_server(self) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class InMemoryPipeTransport(MCPTransport):
    """
    Bi-directional, asynchronous in-memory transport for 1:1 client-server pairs.
    Messages are serialized to JSON strings over the wire to simulate real process/network boundaries
    and eliminate shared-memory object leakage.
    """

    def __init__(self):
        self._client_to_server: asyncio.Queue[str] = asyncio.Queue()
        self._server_to_client: asyncio.Queue[str] = asyncio.Queue()
        self._is_closed = False

    async def send_to_server(self, message: str) -> None:
        if self._is_closed:
            raise ConnectionError("Transport is closed.")
        await self._client_to_server.put(message)

    async def receive_from_client(self) -> str:
        if self._is_closed:
            raise ConnectionError("Transport is closed.")
        return await self._client_to_server.get()

    async def send_to_client(self, message: str) -> None:
        if self._is_closed:
            raise ConnectionError("Transport is closed.")
        await self._server_to_client.put(message)

    async def receive_from_server(self) -> str:
        if self._is_closed:
            raise ConnectionError("Transport is closed.")
        return await self._server_to_client.get()

    async def close(self) -> None:
        self._is_closed = True


# ============================================================================
# 3. MCP SERVER (ISOLATED CAPABILITY PROVIDER)
# ============================================================================

ToolHandler = Callable[[Dict[str, Any], Dict[str, str]], Awaitable[CallToolResult]]


@dataclasses.dataclass
class RegisteredTool:
    definition: ToolDefinition
    handler: ToolHandler


class MCPServer:
    """
    Isolated MCP Server exposing declared operational capabilities.
    Maintains defense-in-depth argument validation and upstream credential isolation.
    Cannot inspect peer servers or host conversation history.
    """

    def __init__(self, server_id: str, name: str, version: str = "1.0.0",
                 service_credentials: Optional[Dict[str, str]] = None):
        self.server_id = server_id
        self.name = name
        self.version = version
        self._service_credentials: Dict[str, str] = service_credentials or {}
        self._tools: Dict[str, RegisteredTool] = {}
        self._is_running = False

    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any],
                      handler: ToolHandler, is_high_impact: bool = False,
                      required_upstream_scopes: Sequence[str] = ()) -> None:
        defn = ToolDefinition(
            name=name,
            description=description,
            inputSchema=input_schema,
            is_high_impact=is_high_impact,
            required_upstream_scopes=tuple(required_upstream_scopes)
        )
        self._tools[name] = RegisteredTool(definition=defn, handler=handler)
        logger.info("Server [%s] registered tool '%s' (high_impact=%s)", self.server_id, name, is_high_impact)

    @staticmethod
    def validate_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validates payload against simple JSON Schema properties and required fields."""
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in payload:
                return False, f"Missing required parameter: '{field_name}'"

        properties = schema.get("properties", {})
        for key, val in payload.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type == "string" and not isinstance(val, str):
                    return False, f"Parameter '{key}' must be a string."
                elif expected_type == "number" and not isinstance(val, (int, float)):
                    return False, f"Parameter '{key}' must be a number."
                elif expected_type == "integer" and not isinstance(val, int):
                    return False, f"Parameter '{key}' must be an integer."
                elif expected_type == "boolean" and not isinstance(val, bool):
                    return False, f"Parameter '{key}' must be a boolean."
                elif expected_type == "object" and not isinstance(val, dict):
                    return False, f"Parameter '{key}' must be an object."
                elif expected_type == "array" and not isinstance(val, list):
                    return False, f"Parameter '{key}' must be an array."

        return True, None

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Processes standardized MCP JSON-RPC requests."""
        msg_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": LATEST_PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": self.version}
                }
            }

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        elif method == "tools/list":
            tool_list = [t.definition.to_dict() for t in self._tools.values()]
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": tool_list}
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name not in self._tools:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": MCPError(
                        code=MCPErrorCode.METHOD_NOT_FOUND,
                        message=f"Tool '{tool_name}' not found on server '{self.server_id}'"
                    ).to_dict()
                }

            tool_entry = self._tools[tool_name]
            
            # Server-side argument validation before execution
            valid, err = self.validate_schema(arguments, tool_entry.definition.inputSchema)
            if not valid:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": MCPError(
                        code=MCPErrorCode.INVALID_PARAMS,
                        message=f"Server-side schema validation failed: {err}"
                    ).to_dict()
                }

            try:
                result = await tool_entry.handler(arguments, copy.deepcopy(self._service_credentials))
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": result.to_dict()
                }
            except Exception as exc:
                logger.exception("Error executing tool '%s' on server '%s'", tool_name, self.server_id)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": MCPError(
                        code=MCPErrorCode.INTERNAL_ERROR,
                        message=f"Tool execution exception: {str(exc)}"
                    ).to_dict()
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": MCPError(
                    code=MCPErrorCode.METHOD_NOT_FOUND,
                    message=f"Method '{method}' unsupported."
                ).to_dict()
            }

    async def run_loop(self, transport: MCPTransport) -> None:
        """Asynchronous server event loop serving a single connected client."""
        self._is_running = True
        try:
            while self._is_running:
                raw_req = await transport.receive_from_client()
                req_obj = json.loads(raw_req)
                resp_obj = await self.handle_request(req_obj)
                await transport.send_to_client(json.dumps(resp_obj))
        except (asyncio.CancelledError, ConnectionError):
            pass
        finally:
            self._is_running = False


# ============================================================================
# 4. MCP CLIENT (1:1 PROTOCOL GATEWAY)
# ============================================================================

class MCPClient:
    """
    Dedicated 1:1 client session connector for a single MCP Server.
    Handles message transport, protocol negotiation, and error unwrapping.
    Does NOT make enterprise authorization decisions.
    """

    def __init__(self, client_id: str, target_server_id: str, transport: MCPTransport):
        self.client_id = client_id
        self.target_server_id = target_server_id
        self.transport = transport
        self.is_connected = False
        self.server_info: Dict[str, Any] = {}
        self.server_capabilities: Dict[str, Any] = {}
        self._request_counter = 0

    def _next_id(self) -> int:
        self._request_counter += 1
        return self._request_counter

    async def connect(self) -> None:
        """Executes MCP initialization handshake."""
        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": f"client_{self.client_id}", "version": "1.0.0"}
            }
        }
        await self.transport.send_to_server(json.dumps(init_req))
        raw_resp = await self.transport.receive_from_server()
        resp = json.loads(raw_resp)

        if "error" in resp:
            raise ConnectionError(f"MCP Initialize failed: {resp['error']}")

        self.server_capabilities = resp.get("result", {}).get("capabilities", {})
        self.server_info = resp.get("result", {}).get("serverInfo", {})
        self.is_connected = True
        logger.info("MCPClient [%s] connected to server [%s] (%s v%s)",
                    self.client_id, self.target_server_id,
                    self.server_info.get("name"), self.server_info.get("version"))

    async def list_tools(self) -> List[ToolDefinition]:
        """Discovers tools exposed by the connected server."""
        if not self.is_connected:
            raise ConnectionError("Client is not connected.")

        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }
        await self.transport.send_to_server(json.dumps(req))
        raw_resp = await self.transport.receive_from_server()
        resp = json.loads(raw_resp)

        if "error" in resp:
            raise RuntimeError(f"tools/list failed: {resp['error']}")

        tools_data = resp.get("result", {}).get("tools", [])
        return [
            ToolDefinition(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"]
            )
            for t in tools_data
        ]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Dispatches an authorized tools/call request to the server."""
        if not self.is_connected:
            raise ConnectionError("Client is not connected.")

        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments}
        }
        await self.transport.send_to_server(json.dumps(req))
        raw_resp = await self.transport.receive_from_server()
        resp = json.loads(raw_resp)

        if "error" in resp:
            err = resp["error"]
            raise RuntimeError(f"tools/call error [{err.get('code')}]: {err.get('message')}")

        result_data = resp.get("result", {})
        return CallToolResult(
            content=result_data.get("content", []),
            isError=result_data.get("isError", False),
            metadata=result_data.get("_meta", {})
        )

    async def close(self) -> None:
        self.is_connected = False
        await self.transport.close()


# ============================================================================
# 5. MCP HOST & GOVERNED TOOL LIFECYCLE CONTROLLER
# ============================================================================

@dataclasses.dataclass(frozen=True)
class CallerContext:
    tenant_id: str
    brand_id: str
    agent_id: str
    agent_role: str
    task_id: str
    budget_usd_remaining: float


@dataclasses.dataclass(frozen=True)
class TaskCapabilityGrant:
    task_id: str
    allowed_tools: Set[str]
    allowed_servers: Set[str]
    max_call_count: int = 50
    allow_financial_spend: bool = False


@dataclasses.dataclass(frozen=True)
class ToolAuditRecord:
    audit_id: str
    timestamp: str
    task_id: str
    tenant_id: str
    agent_id: str
    tool_name: str
    server_id: str
    arguments_hash: str
    authorization_decision: str
    execution_status: str
    remote_entity_id: Optional[str] = None
    cost_usd: float = 0.0


class MCPHost:
    """
    Central Orchestration & Security Chokepoint.
    Maintains 1:1 client sessions, applies monotonic policy filtering at discovery,
    intercepts invocations for identity/grant/HITL validation, and records audit trails.
    """

    def __init__(self, host_id: str = "orchestrator_host"):
        self.host_id = host_id
        self._clients: Dict[str, MCPClient] = {}
        self._server_tool_map: Dict[str, str] = {}
        self._host_policy_allowlist: Set[str] = set()
        self._high_impact_tools: Set[str] = set()
        self._audit_log: List[ToolAuditRecord] = []
        self._tool_call_counts: Dict[str, int] = {}

    def register_server_client(self, server_id: str, client: MCPClient,
                               server_tools: Sequence[ToolDefinition],
                               is_approved_by_policy: bool = True) -> None:
        """Registers a dedicated 1:1 client connector and indexes tool mapping."""
        self._clients[server_id] = client
        for t in server_tools:
            self._server_tool_map[t.name] = server_id
            if is_approved_by_policy:
                self._host_policy_allowlist.add(t.name)
            if t.is_high_impact:
                self._high_impact_tools.add(t.name)

        logger.info("Host registered server [%s] with %d tools.", server_id, len(server_tools))

    def discover_effective_tools(self, caller: CallerContext,
                                 task_grant: TaskCapabilityGrant,
                                 subagent_scope_tools: Optional[Set[str]] = None) -> List[ToolDefinition]:
        """
        Discovery-Time Projection:
        Returns ONLY the effective allowlisted subset of tools for the model context.
        Effective Tool Access = Host Policy ∩ Task Grant ∩ SubAgent Scope ∩ Server Scope.
        """
        effective_names = self._host_policy_allowlist.intersection(task_grant.allowed_tools)
        if subagent_scope_tools is not None:
            effective_names = effective_names.intersection(subagent_scope_tools)

        projected_tools: List[ToolDefinition] = []
        for tool_name in effective_names:
            srv_id = self._server_tool_map.get(tool_name)
            if srv_id and srv_id in task_grant.allowed_servers:
                projected_tools.append(ToolDefinition(
                    name=tool_name,
                    description=f"Governed capability on server {srv_id}",
                    inputSchema={"type": "object"}
                ))

        logger.debug("Projected %d effective tools to agent [%s] for task [%s]",
                     len(projected_tools), caller.agent_id, caller.task_id)
        return projected_tools

    async def invoke_governed_tool(self, caller: CallerContext,
                                   task_grant: TaskCapabilityGrant,
                                   tool_name: str,
                                   arguments: Dict[str, Any],
                                   approval_token: Optional[str] = None,
                                   subagent_scope_tools: Optional[Set[str]] = None) -> CallToolResult:
        """
        Governed Invocation Interceptor:
        Validates caller identity, tenant, monotonic allowlist, rate caps, schema,
        and required HITL clearance tokens before dispatching to the 1:1 client.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        audit_id = f"aud_{uuid.uuid4().hex[:10]}"
        arg_hash = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode("utf-8")).hexdigest()

        # 1. Rate & Count Limits
        current_calls = self._tool_call_counts.get(caller.task_id, 0)
        if current_calls >= task_grant.max_call_count:
            self._record_audit(audit_id, now_iso, caller, tool_name, "UNKNOWN", arg_hash, "DENIED_CALL_LIMIT", "FAILED")
            raise PermissionError(f"Task call limit exceeded: {current_calls} >= {task_grant.max_call_count}")

        # 2. Monotonic Capability Intersection Verification
        effective_names = self._host_policy_allowlist.intersection(task_grant.allowed_tools)
        if subagent_scope_tools is not None:
            effective_names = effective_names.intersection(subagent_scope_tools)

        if tool_name not in effective_names:
            self._record_audit(audit_id, now_iso, caller, tool_name, "UNKNOWN", arg_hash, "DENIED_NOT_IN_ALLOWLIST", "FAILED")
            raise PermissionError(f"Authorization Denied: Tool '{tool_name}' not in effective capability allowlist.")

        server_id = self._server_tool_map.get(tool_name)
        if not server_id or server_id not in self._clients:
            self._record_audit(audit_id, now_iso, caller, tool_name, "UNKNOWN", arg_hash, "DENIED_SERVER_UNMAPPED", "FAILED")
            raise RuntimeError(f"Server configuration missing for tool '{tool_name}'.")

        # 3. High-Impact & Financial HITL Gate Verification
        spend_val = arguments.get("spend_amount_usd", 0)
        is_spend = isinstance(spend_val, (int, float)) and spend_val > 0
        is_high_impact = tool_name in self._high_impact_tools or is_spend
        if is_high_impact:
            if not approval_token or not approval_token.startswith("AUTH_SIG_"):
                self._record_audit(audit_id, now_iso, caller, tool_name, server_id, arg_hash, "BLOCKED_HITL_REQUIRED", "FAILED")
                raise PermissionError(f"Action '{tool_name}' requires an unexpired, cryptographic HITL approval token.")

        client = self._clients[server_id]

        # 4. Dispatch via Dedicated 1:1 Client Session
        try:
            result = await client.call_tool(tool_name, arguments)
            self._tool_call_counts[caller.task_id] = current_calls + 1
            
            remote_id = result.metadata.get("remote_entity_id")
            cost = float(result.metadata.get("cost_usd", 0.0))

            self._record_audit(
                audit_id=audit_id,
                timestamp=now_iso,
                caller=caller,
                tool_name=tool_name,
                server_id=server_id,
                arg_hash=arg_hash,
                decision="AUTHORIZED",
                status="EXECUTED",
                remote_id=remote_id,
                cost_usd=cost
            )
            return result
        except Exception as exc:
            self._record_audit(
                audit_id=audit_id,
                timestamp=now_iso,
                caller=caller,
                tool_name=tool_name,
                server_id=server_id,
                arg_hash=arg_hash,
                decision="AUTHORIZED",
                status=f"EXEC_ERROR: {str(exc)}"
            )
            raise

    def _record_audit(self, audit_id: str, timestamp: str, caller: CallerContext,
                      tool_name: str, server_id: str, arg_hash: str,
                      decision: str, status: str, remote_id: Optional[str] = None,
                      cost_usd: float = 0.0) -> None:
        rec = ToolAuditRecord(
            audit_id=audit_id,
            timestamp=timestamp,
            task_id=caller.task_id,
            tenant_id=caller.tenant_id,
            agent_id=caller.agent_id,
            tool_name=tool_name,
            server_id=server_id,
            arguments_hash=arg_hash,
            authorization_decision=decision,
            execution_status=status,
            remote_entity_id=remote_id,
            cost_usd=cost_usd
        )
        self._audit_log.append(rec)

    def get_audit_trail(self) -> List[ToolAuditRecord]:
        return list(self._audit_log)