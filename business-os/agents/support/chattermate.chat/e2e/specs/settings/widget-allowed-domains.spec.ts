import { test, expect, env, customizeAgent, setAllowedDomains } from '@e2e'

// The Widget tab's allowed-domains editor. Every add and remove is saved at once,
// and what it shows is what the server stored.

test.describe('widget allowed domains editor', () => {
  test('a pasted address is saved as just its host, and entries that can\'t work are explained @settings', async ({ agent, allowedDomainsPage }) => {
    await allowedDomainsPage.goto(agent.id)
    await expect(allowedDomainsPage.anySiteNotice).toBeVisible()

    await allowedDomainsPage.add('https://Shop.Example.com/pricing?plan=pro')
    await expect(allowedDomainsPage.domains).toHaveText(['shop.example.com'])

    for (const [entry, reason] of [
      ['*.com', 'is too broad for a wildcard'],
      ['*.co.uk', 'is too broad for a wildcard'],
      ['shop.example.com:99999', 'has an invalid port'],
      ['intranet', 'needs a full domain, like example.com'],
    ]) {
      await allowedDomainsPage.add(entry)
      await expect(allowedDomainsPage.error).toHaveText(`'${entry}' ${reason}`)
    }
    // None of them was saved
    await expect(allowedDomainsPage.domains).toHaveText(['shop.example.com'])
  })

  test('a widget allows at most 20 domains @settings', async ({ agent, widget, adminApi, allowedDomainsPage }) => {
    const twenty = Array.from({ length: 20 }, (_, i) => `site${i + 1}.example.com`)
    await setAllowedDomains(adminApi, widget.widgetId, twenty)
    await allowedDomainsPage.goto(agent.id)
    await expect(allowedDomainsPage.domains).toHaveCount(20)

    await allowedDomainsPage.add('one-more.example.com')
    await expect(allowedDomainsPage.error).toHaveText('At most 20 domains')
    await expect(allowedDomainsPage.domains).toHaveText(twenty)
  })

  test('the list decides where the widget shows, and removing every entry lets any site show it @settings', async ({ agent, widget, allowedDomainsPage }) => {
    await allowedDomainsPage.goto(agent.id)

    // Another site only: the customer's site (127.0.0.1) refuses the widget
    await allowedDomainsPage.add('shop.example.com')
    await widget.embed()
    await widget.launcher.click()
    await expect(widget.unavailableNotice).toBeVisible()

    await allowedDomainsPage.add('127.0.0.1')
    await expect(allowedDomainsPage.domains).toHaveText(['shop.example.com', '127.0.0.1'])
    await widget.embed()
    await widget.open()

    await allowedDomainsPage.remove('shop.example.com')
    await allowedDomainsPage.remove('127.0.0.1')
    await expect(allowedDomainsPage.domains).toHaveCount(0)
    await expect(allowedDomainsPage.anySiteNotice).toBeVisible()
  })

  // The API the snippet points at, and the frame host its /frame redirects to
  const frameSources = () => [env.backendUrl, env.widgetFrameUrl].filter(Boolean).join(' ')

  test('the Widget tab says what a site\'s Content-Security-Policy must allow @settings', async ({ agent, allowedDomainsPage }) => {
    await allowedDomainsPage.goto(agent.id)

    await expect(allowedDomainsPage.cspSources).toHaveText([`script-src ${env.frontendUrl};\nframe-src ${frameSources()};`])
  })

  test('the iframe snippet\'s CSP note needs no loader script @settings', async ({ agent, adminApi, allowedDomainsPage }) => {
    // Only Ask-anything agents offer the iframe snippet
    await customizeAgent(adminApi, agent.id, { chat_style: 'ASK_ANYTHING' })
    await allowedDomainsPage.goto(agent.id)

    await expect(allowedDomainsPage.cspSources).toHaveText([
      `script-src ${env.frontendUrl};\nframe-src ${frameSources()};`,
      `frame-src ${frameSources()};`,
    ])
  })
})
