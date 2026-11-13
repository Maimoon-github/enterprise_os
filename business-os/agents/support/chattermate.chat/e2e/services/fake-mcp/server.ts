// A real MCP server (streamable HTTP, stateless) for the MCP-connector journeys:
// the backend connects to it exactly as it would to a customer's server, lists
// its tools and calls them when the (fake) model asks.
//
//   POST /mcp               the MCP endpoint
//   GET  /__requests        the headers each MCP request arrived with, oldest first
//   DELETE /__requests      forget them
//
// Tools: lookup_order(order_id) → "Order <id>: shipped on 2 May via DHL".
//
// Run: node services/fake-mcp/server.ts --port 14030

import { createServer, type IncomingMessage, type ServerResponse } from 'node:http'
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js'
import { z } from 'zod'

interface SeenRequest {
  at: string
  method: string
  authorization: string | null
  rpcMethod: string | null
}

const seen: SeenRequest[] = []

function mcpServer(): McpServer {
  const server = new McpServer({ name: 'e2e-orders', version: '1.0.0' })
  server.registerTool('lookup_order', {
    description: 'Look up an order by its id and return its shipping status.',
    inputSchema: { order_id: z.string().describe('The order id, e.g. A123') },
  }, async ({ order_id }) => ({
    content: [{ type: 'text', text: `Order ${order_id}: shipped on 2 May via DHL` }],
  }))
  return server
}

async function readJson(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  const raw = Buffer.concat(chunks).toString('utf8')
  return raw ? JSON.parse(raw) : undefined
}

function send(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { 'content-type': 'application/json' })
  res.end(JSON.stringify(body))
}

async function route(req: IncomingMessage, res: ServerResponse) {
  const path = new URL(req.url ?? '/', 'http://fake-mcp').pathname
  if (path === '/health') return send(res, 200, { status: 'ok' })
  if (path === '/__requests' && req.method === 'GET') return send(res, 200, seen)
  if (path === '/__requests' && req.method === 'DELETE') {
    seen.length = 0
    return send(res, 200, { ok: true })
  }
  if (path !== '/mcp') return send(res, 404, { error: `no route for ${path}` })
  if (req.method !== 'POST') return send(res, 405, { jsonrpc: '2.0', error: { code: -32000, message: 'Method not allowed.' }, id: null })

  const body = await readJson(req)
  seen.push({
    at: new Date().toISOString(),
    method: req.method,
    authorization: req.headers.authorization ?? null,
    rpcMethod: (body as { method?: string } | undefined)?.method ?? null,
  })
  // Stateless: a fresh server and transport per request, as the SDK recommends.
  const server = mcpServer()
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined })
  res.on('close', () => {
    void transport.close()
    void server.close()
  })
  await server.connect(transport)
  await transport.handleRequest(req, res, body)
}

const portArg = process.argv.indexOf('--port')
const port = Number(portArg > -1 ? process.argv[portArg + 1] : 14030)

createServer((req, res) => {
  route(req, res).catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err)
    console.error(`[fake-mcp] ${req.method} ${req.url} -> 500: ${message}`)
    if (!res.headersSent) send(res, 500, { error: message })
  })
}).listen(port, '127.0.0.1', () => console.log(`[fake-mcp] listening on http://127.0.0.1:${port}/mcp`))
