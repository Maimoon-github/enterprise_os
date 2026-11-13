import { test, expect, chatsWithAgent, conversationTokenExpiry, createWidgetApp, issueConversationToken, unique, AI_REPLY } from '@e2e'

test.describe('widget JS API', () => {
  test('the host page opens and closes the chat with window.ChatterMate @widget', async ({ widget }) => {
    await widget.embed()

    await widget.api('open')
    await expect(widget.panel).toHaveClass(/\bactive\b/)
    await widget.expectReady()
    expect(await widget.api('isOpen')).toBe(true)

    await widget.api('close')
    await expect(widget.panel).not.toHaveClass(/\bactive\b/)
    expect(await widget.api('isOpen')).toBe(false)
  })

  test('a site can hide the launcher and open the chat from its own button @widget', async ({ widget }) => {
    await widget.embed({ config: { launcher: false }, withTriggerButton: true })
    await expect(widget.launcher).toBeHidden()

    await widget.hostChatButton.click()
    await expect(widget.panel).toHaveClass(/\bactive\b/)
    await widget.expectReady()
  })

  test('logout() starts a fresh anonymous visitor, without the signed-in visitor\'s conversation @widget', async ({ agent, widget, llm, adminApi }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Happy to help!'))
    const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))

    await widget.embed({ token: await issueConversationToken(adminApi, apiKey, widget.widgetId, widget.customer) })
    await widget.open()
    await widget.send('Signed-in question')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)

    // The site signs the visitor out without reloading the page
    await widget.api('logout')
    await expect(widget.panel).not.toHaveClass(/\bactive\b/)
    await widget.open()
    await widget.send('Anonymous question')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)
    await expect(widget.customerMessages).toHaveText(['Anonymous question'])

    // Two visitors now: the signed-in one, whose conversation logout() closed, and a new one
    const chats = await chatsWithAgent(adminApi, agent.id)
    expect(chats.map((c) => ({ email: c.customer.email, status: c.status })))
      .toContainEqual({ email: widget.customer.email, status: 'closed' })
    expect(new Set(chats.map((c) => c.customer.id)).size).toBe(2)
  })

  test('Escape pressed in the chat closes a sidebar drawer @widget', async ({ widget }) => {
    await widget.embed({ config: { displayMode: 'sidebar-right' } })
    await widget.open()

    await widget.pressEscapeInChat()
    await expect(widget.panel).not.toHaveClass(/\bactive\b/)
    expect(await widget.api('isOpen')).toBe(false)
  })

  test.describe('a token-authenticated widget', () => {
    test.use({ agentSettings: { requireTokenAuth: true } })

    test('a visitor whose short-lived token ran out is signed in again by the site\'s tokenProvider, and keeps the conversation @widget @slow', async ({ agent, widget, llm, adminApi }) => {
      test.slow()
      await llm.script(agent, (s) => s.otherwise().reply('Happy to help!'))
      const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))
      // The shortest lifetime the API allows
      const mint = () => issueConversationToken(adminApi, apiKey, widget.widgetId, widget.customer, 60)
      const token = await mint()

      await widget.embed({ token, tokenProvider: mint })
      await widget.open()
      await widget.send('Before my token ran out')
      await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)
      expect(widget.tokenRequests).toBe(0)

      // The visitor comes back to the page as first rendered, its token long gone
      await expect.poll(() => Date.now(), { timeout: 90_000, intervals: [1_000] })
        .toBeGreaterThan(conversationTokenExpiry(token).getTime() + 1_000)
      await widget.embed({ token, tokenProvider: mint })
      await widget.open()
      await expect(widget.customerMessages).toHaveText(['Before my token ran out'])
      expect(widget.tokenRequests).toBe(1)

      await widget.send('And after')
      await expect(widget.agentMessages.last()).toHaveText('Happy to help!', AI_REPLY)
      await expect(widget.customerMessages).toHaveText(['Before my token ran out', 'And after'])
    })
  })
})
