import httpx

class MCPClient:
    """Connects to FastMCP servers over Streamable HTTP with stateless _meta header."""
    def __init__(self, server_url: str):
        self.server_url = server_url

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        async with httpx.AsyncClient(base_url=self.server_url, timeout=30.0) as client:
            payload = {
                "method": f"tools/{tool_name}",
                "params": arguments,
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientInfo": {"name": "marketing-os-worker", "version": "1.0.0"}
                }
            }
            res = await client.post("/mcp", json=payload)
            res.raise_for_status()
            return res.json()
