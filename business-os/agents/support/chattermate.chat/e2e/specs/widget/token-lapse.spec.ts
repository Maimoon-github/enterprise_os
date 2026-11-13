import { test, expect, conversationTokenExpiry, createWidgetApp, revokeConversationToken, tokenRunningOut, unique, AI_REPLY } from '@e2e'

// A tab left open past its conversation token's life used to reconnect with the
// dead token about once a minute for hours and never chat again (prod, Oct 2026).
test.describe('a visitor whose token stops working while the page is open', () => {
  test('gets the chat back when the connection drops after the token ran out @widget @slow', async ({ agent, widget, llm }) => {
    test.slow()
    await llm.script(agent, (s) => s.otherwise().reply('Happy to help!'))
    const connection = await widget.watchConnection()
    await widget.embed()
    await widget.open()
    await widget.send('Before')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)

    // Their token was issued on an earlier visit and runs out during this one
    const expiring = tokenRunningOut(connection.token(), 15)
    await widget.returnWithStoredToken(expiring)
    await widget.open()
    await expect(widget.customerMessages).toHaveText(['Before'])
    await expect.poll(() => connection.token()).toBe(expiring)

    await expect.poll(() => Date.now(), { timeout: 30_000, intervals: [1_000] })
      .toBeGreaterThan(conversationTokenExpiry(expiring).getTime() + 1_000)
    const authorizedBefore = widget.authorizations
    await connection.drop()

    // The widget authorizes again for a live token instead of retrying the dead one
    await expect.poll(() => connection.token()).not.toBe(expiring)
    await widget.expectReady()
    await widget.send('After')
    await expect(widget.agentMessages.last()).toHaveText('Happy to help!', AI_REPLY)
    // One authorization recovered it: a second one ran alongside and made the
    // visitor a second anonymous customer
    expect(widget.authorizations - authorizedBefore).toBe(1)
  })

  // Revoking is how a test kills a token without waiting; it needs Redis, so @redis (nightly).
  test('gets the chat back when the connection drops after the token was revoked @widget @redis', async ({ agent, widget, llm, adminApi }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Happy to help!'))
    const connection = await widget.watchConnection()

    await widget.embed()
    await widget.open()
    await widget.send('Before')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)

    const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))
    const revoked = connection.token()
    await revokeConversationToken(adminApi, apiKey, revoked)
    await connection.drop()

    // The widget authorizes again for a live token instead of retrying the dead one
    await expect.poll(() => connection.token()).not.toBe(revoked)
    await widget.expectReady()
    await widget.send('After')
    await expect(widget.agentMessages.last()).toHaveText('Happy to help!', AI_REPLY)
  })
})
