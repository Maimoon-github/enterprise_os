import { test, expect, ApiClient, createWidgetApp, issueConversationToken, unique, AI_REPLY } from '@e2e'

test.describe('token-authenticated widget', () => {
  test.use({ agentSettings: { requireTokenAuth: true } })

  test('a visitor with a token from the site\'s server can chat @widget', async ({ agent, widget, llm, adminApi }) => {
    const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))
    const token = await issueConversationToken(adminApi, apiKey, widget.widgetId, widget.customer)
    await llm.script(agent, (s) => s.otherwise().reply('Welcome back!'))

    await widget.embed({ token })
    await widget.open()
    await widget.send('Hi')
    await expect(widget.lastAgentMessage()).toHaveText('Welcome back!', AI_REPLY)
  })

  test('without a token the widget refuses to load @widget', async ({ widget }) => {
    await widget.embed()
    // The notice lives in the chat panel, so the visitor sees it when they click the launcher.
    await widget.launcher.click()
    await expect(widget.unavailableNotice).toBeVisible()
  })

  test('a tampered token is refused @widget @security', async ({ widget, adminApi }) => {
    const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))
    const token = await issueConversationToken(adminApi, apiKey, widget.widgetId, widget.customer)
    // Swap the signature for another token's: a well-formed JWT this widget never signed.
    const other = await issueConversationToken(adminApi, apiKey, widget.widgetId, { ...widget.customer, email: `x.${widget.customer.email}` })
    const tampered = `${token.split('.').slice(0, 2).join('.')}.${other.split('.')[2]}`

    await widget.embed({ token: tampered })
    await widget.launcher.click()
    await expect(widget.unavailableNotice).toBeVisible()
  })

  test('a token minted for another widget is refused @widget @security', async ({ widget, adminApi, agent, makeWidget }) => {
    const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))
    const otherWidget = await makeWidget(agent.id)
    const tokenForOther = await issueConversationToken(adminApi, apiKey, otherWidget.widgetId, widget.customer)

    await widget.embed({ token: tokenForOther })
    await widget.launcher.click()
    await expect(widget.unavailableNotice).toBeVisible()
  })

  test('an expired token no longer opens the chat @widget @security @slow', async ({ widget, adminApi, request }) => {
    test.slow()
    const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))
    const token = await issueConversationToken(adminApi, apiKey, widget.widgetId, widget.customer, 60)
    // What the loader fetches to render the chat frame for this visitor. Each
    // poll on a fresh connection: the backend drops a keep-alive connection
    // idle for 5s, the poll interval, and a reused one can hang up mid-request.
    const visitor = new ApiClient(request, token)
    const frame = () => visitor.raw('GET', `/widgets/${widget.widgetId}/data`, { headers: { Connection: 'close' } })
    expect((await frame()).status()).toBe(200)

    // The shortest lifetime the API allows; the backend's own clock decides.
    await expect.poll(async () => (await frame()).status(), { timeout: 90_000, intervals: [5_000] }).toBe(401)
    expect(JSON.stringify(await (await frame()).json())).toContain('Conversation token expired')
  })
})
