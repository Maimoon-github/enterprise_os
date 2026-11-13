import { test, expect, attachMcpConnector, createMcpConnector, FakeMcp, unique, AI_REPLY } from '@e2e'

test.describe('MCP connectors', () => {
  test('an agent answers with a tool from a connected MCP server @mcp', async ({ agent, widget, llm, adminApi, request }) => {
    const mcp = new FakeMcp(request)
    const connector = await createMcpConnector(adminApi, { name: unique('orders'), url: mcp.url })
    await attachMcpConnector(adminApi, connector.id, agent.id)
    const orderId = unique('A')
    await llm.script(agent, (s) => s
      .when(/order/i).callTool('lookup_order', { order_id: orderId }).thenReply('Your order shipped on 2 May via DHL.')
      .otherwise().reply('Happy to help!'))

    await widget.embed()
    await widget.open()
    await widget.send(`Where is my order ${orderId}?`)

    await expect(widget.lastAgentMessage()).toHaveText('Your order shipped on 2 May via DHL.', AI_REPLY)
    // The answer came from the MCP server, through the backend, back to the model.
    const toolResults = (await llm.requests(agent)).flatMap((r) => r.toolResults).join('\n')
    expect(toolResults).toContain(`Order ${orderId}: shipped on 2 May via DHL`)
  })

  test('a connector\'s secrets are masked when read back, but still reach the server @mcp @security', async ({ agent, widget, llm, adminApi, request }) => {
    const mcp = new FakeMcp(request)
    const secret = `Bearer ${unique('mcp-secret')}`
    const connector = await createMcpConnector(adminApi, { name: unique('orders'), url: mcp.url, headers: { Authorization: secret } })

    expect(connector.headers).toEqual({ Authorization: '********' })
    expect(JSON.stringify(await adminApi.get(`/mcp-tools/${connector.id}`))).not.toContain(secret)

    // Saving the masked value back keeps the real one.
    await adminApi.put(`/mcp-tools/${connector.id}`, { data: { headers: { Authorization: '********' } } })
    await attachMcpConnector(adminApi, connector.id, agent.id)
    await llm.script(agent, (s) => s.otherwise().callTool('lookup_order', { order_id: 'A1' }).thenReply('Checked.'))
    await widget.embed()
    await widget.open()
    await widget.send('Where is my order?')
    await expect(widget.lastAgentMessage()).toHaveText('Checked.', AI_REPLY)
    expect((await mcp.requests()).map((r) => r.authorization)).toContain(secret)
  })

  // Nothing listens on port 1: the connection is refused at once.
  const DEAD_SERVER = 'http://127.0.0.1:1/mcp'

  test('a server that is down costs only its own tools, not the agent\'s other connectors @mcp', async ({ agent, widget, llm, adminApi, request }) => {
    const mcp = new FakeMcp(request)
    const down = await createMcpConnector(adminApi, { name: unique('down'), url: DEAD_SERVER })
    const up = await createMcpConnector(adminApi, { name: unique('orders'), url: mcp.url })
    await attachMcpConnector(adminApi, down.id, agent.id)
    await attachMcpConnector(adminApi, up.id, agent.id)
    const orderId = unique('A')
    await llm.script(agent, (s) => s
      .when(/order/i).callTool('lookup_order', { order_id: orderId }).thenReply('Your order shipped on 2 May via DHL.')
      .otherwise().reply('Happy to help!'))

    await widget.embed()
    await widget.open()
    await widget.send(`Where is my order ${orderId}?`)

    await expect(widget.lastAgentMessage()).toHaveText('Your order shipped on 2 May via DHL.', AI_REPLY)
    const toolResults = (await llm.requests(agent)).flatMap((r) => r.toolResults).join('\n')
    expect(toolResults).toContain(`Order ${orderId}: shipped on 2 May via DHL`)
  })

  test('testing a server that is down says it could not connect @mcp', async ({ adminApi }) => {
    const down = await createMcpConnector(adminApi, { name: unique('down'), url: DEAD_SERVER })

    const result = await adminApi.post<{ success: boolean; error: string | null }>(`/mcp-tools/${down.id}/test`)

    expect(result).toMatchObject({ success: false, error: expect.stringContaining('Could not connect to the server') })
  })
})
