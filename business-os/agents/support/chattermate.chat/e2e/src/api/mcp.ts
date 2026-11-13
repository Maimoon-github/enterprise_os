import type { ApiClient } from './client'

export interface McpConnector {
  id: number
  name: string
  url: string | null
  headers: Record<string, string> | null
}

/** Adds a streamable-HTTP MCP server to the org's connectors. */
export async function createMcpConnector(api: ApiClient, connector: { name: string; url: string; headers?: Record<string, string> }): Promise<McpConnector> {
  return api.post<McpConnector>('/mcp-tools', { data: { transport_type: 'http', enabled: true, timeout: 10, ...connector } })
}

/** Gives an agent the connector's tools. */
export async function attachMcpConnector(api: ApiClient, connectorId: number, agentId: string): Promise<void> {
  await api.post('/mcp-tools/agent-association', { data: { mcp_tool_id: connectorId, agent_id: agentId } })
}
