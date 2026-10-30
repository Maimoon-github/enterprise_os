class MCPHost:
    """Manages connections and tool/resource routing to registered FastMCP servers."""
    def __init__(self):
        self._servers: dict[str, str] = {}

    def register_server(self, name: str, endpoint: str):
        self._servers[name] = endpoint

    def get_server_endpoint(self, name: str) -> str | None:
        return self._servers.get(name)

mcp_host = MCPHost()
