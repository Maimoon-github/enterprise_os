import type { APIRequestContext } from '@playwright/test'
import { env } from '../env'

export interface McpRequest {
  at: string
  authorization: string | null
  rpcMethod: string | null
}

/** Test-side client for services/fake-mcp: what reached the MCP server. */
export class FakeMcp {
  readonly url = `${env.fakeMcpUrl}/mcp`
  private readonly request: APIRequestContext

  constructor(request: APIRequestContext) {
    this.request = request
  }

  async requests(): Promise<McpRequest[]> {
    return (await (await this.request.get(`${env.fakeMcpUrl}/__requests`)).json()) as McpRequest[]
  }
}
