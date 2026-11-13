import { test, expect, env, AI_REPLY } from '@e2e'

// Merchants who harden their site's Content-Security-Policy around our script and
// API. One that also lets our frame in gets the framed widget; one that doesn't
// (no frame-src for us - most never hear they need it) still gets a working chat:
// the loader falls back to building it inside the page, under the page's policy.

test.describe('a site with a strict Content-Security-Policy', () => {
  test('that lets our frame in gets the framed chat @widget', async ({ agent, widget, llm }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Framed and fine.'))
    const frameSrc = [env.backendUrl, env.widgetFrameUrl].filter((origin): origin is string => Boolean(origin))

    await widget.embed({ strictCsp: { frameSrc } })
    await widget.open()
    await widget.send('Hi')

    await expect(widget.lastAgentMessage()).toHaveText('Framed and fine.', AI_REPLY)
    expect(await widget.runsInPage()).toBe(false)
  })

  test('that allows no frames still gets the chat, built inside the page @widget', async ({ agent, widget, llm }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Here inside the page.'))

    await widget.embed({ strictCsp: { frameSrc: [] } })
    await widget.open()
    await widget.send('Hi')

    await expect(widget.lastAgentMessage()).toHaveText('Here inside the page.', AI_REPLY)
    expect(await widget.runsInPage()).toBe(true)
  })

  test('the in-page chat keeps the conversation across a reload @widget', async ({ agent, widget, llm }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Still here.'))
    await widget.embed({ strictCsp: { frameSrc: [] } })
    await widget.open()
    await widget.send('Remember me')
    await expect(widget.lastAgentMessage()).toHaveText('Still here.', AI_REPLY)

    await widget.embed({ strictCsp: { frameSrc: [] } })
    await widget.open()

    await expect(widget.customerMessages.last()).toHaveText('Remember me')
  })

  test('on a site our CORS doesn\'t list, the in-page chat says it can\'t load rather than showing nothing @widget', async ({ widget }) => {
    // The in-page chat fetches the widget from the site's own origin, which CORS must
    // admit (today: the org's domain); without frame-src and without that, there's no way in
    await widget.embed({ strictCsp: { frameSrc: [], onUnlistedOrigin: true } })

    // The in-page loader's card ("can't load on"); the framed one would say "couldn't load on"
    await expect(widget.unavailableReason).toContainText('can’t load on')
  })

  test('that runs scripts only by nonce gets the can\'t-load card, not a blank chat @widget', async ({ widget }) => {
    // No 'unsafe-inline': the in-page chat's page loads but its inline scripts don't run,
    // so once it's had its chance the loader brings the framed widget back to say why
    await widget.embed({ strictCsp: { frameSrc: [], nonceOnly: true } })

    await expect(widget.unavailableReason).toContainText('Content-Security-Policy blocks it', { timeout: 30_000 })
  })
})

