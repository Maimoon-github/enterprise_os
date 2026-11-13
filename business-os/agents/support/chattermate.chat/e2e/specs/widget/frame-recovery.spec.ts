import { test, expect, expectUnchanged, setAllowedDomains, AI_REPLY } from '@e2e'

// When the widget can't start, the loader shows a "Chat Unavailable" card. A server
// error may pass, so opening the chat again tries once more; a refusal won't, so
// it doesn't keep asking.

test.describe('when the widget cannot start', () => {
  test('after a server error the visitor sees the chat is unavailable, and opening it again recovers @widget', async ({ agent, widget, llm }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Back in business.'))
    const outage = await widget.failNextStart(500)

    await widget.embed()
    await widget.api('open')
    await outage.fail()
    await expect(widget.unavailableNotice).toBeVisible()
    await expect(widget.unavailableReason).toHaveText('Chat is unavailable right now. Please try again later.')

    await widget.api('close')
    await widget.open()
    await widget.send('Hi')
    await expect(widget.lastAgentMessage()).toHaveText('Back in business.', AI_REPLY)
    expect(widget.startAttempts).toBe(2)
  })

  test.describe('a widget that refuses the visitor', () => {
    test.use({ agentSettings: { requireTokenAuth: true } })

    test('says so, and opening it again does not ask the server again @widget', async ({ widget }) => {
      await widget.embed()
      await widget.launcher.click()
      await expect(widget.unavailableReason).toHaveText(/not currently configured/)
      expect(widget.startAttempts).toBe(1)

      await widget.api('close')
      await widget.launcher.click()
      await expect(widget.unavailableReason).toHaveText(/not currently configured/)
      await expectUnchanged('widget start attempts', async () => widget.startAttempts)
      expect(widget.startAttempts).toBe(1)
    })
  })

  test('a site its allowed domains refuse is told so, and opening it again does not load it again @widget', async ({ widget, adminApi }) => {
    await setAllowedDomains(adminApi, widget.widgetId, ['shop.example.com'])

    await widget.embed()
    await widget.launcher.click()
    await expect(widget.unavailableReason).toContainText('add this one in its settings')
    const loads = widget.frameLoads
    expect(loads).toBeGreaterThan(0)

    await widget.api('close')
    await widget.launcher.click()
    await expect(widget.unavailableReason).toContainText('add this one in its settings')
    await expectUnchanged('widget frame loads', async () => widget.frameLoads)
    expect(widget.frameLoads).toBe(loads)
  })
})
