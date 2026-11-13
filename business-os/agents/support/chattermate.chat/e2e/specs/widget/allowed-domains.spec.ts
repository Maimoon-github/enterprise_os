import { test, expect, setAllowedDomains, AI_REPLY } from '@e2e'

// Where a widget may be embedded. It runs on our own origin, so it needs no CORS
// for the customer's site; its allowed domains decide where the browser shows it.

test.describe('widget allowed domains', () => {
  test('with no list the widget works on any site, localhost included @widget', async ({ agent, widget, llm }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Hello from anywhere.'))

    await widget.embed({ onOtherOrigin: true })
    await widget.open()
    await widget.send('Hi')
    await expect(widget.lastAgentMessage()).toHaveText('Hello from anywhere.', AI_REPLY)

    await widget.embed()
    await widget.open()
  })

  test('a widget limited to some sites only shows there @widget @security', async ({ agent, widget, llm, adminApi }) => {
    await setAllowedDomains(adminApi, widget.widgetId, ['localhost'])
    await llm.script(agent, (s) => s.otherwise().reply('You found me.'))

    // 127.0.0.1 isn't on the list: the browser refuses the widget there
    await widget.embed()
    await widget.launcher.click()
    await expect(widget.unavailableNotice).toBeVisible()
    await expect(widget.page.getByText('add this one in its settings')).toBeVisible()

    // localhost is
    await widget.embed({ onOtherOrigin: true })
    await widget.open()
    await widget.send('Hi')
    await expect(widget.lastAgentMessage()).toHaveText('You found me.', AI_REPLY)
  })

  test('clearing the list lets every site show it again @widget', async ({ widget, adminApi }) => {
    await setAllowedDomains(adminApi, widget.widgetId, ['shop.example.com'])
    await widget.embed()
    await widget.launcher.click()
    await expect(widget.unavailableNotice).toBeVisible()

    await setAllowedDomains(adminApi, widget.widgetId, [])
    await widget.embed()
    await widget.open()
  })
})
