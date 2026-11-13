import { test, expect, expectNoNewA11yViolations, InboxPage } from '@e2e'

// Serious and critical axe findings, per screen, held to a baseline
// (a11y-baseline/): today's known issues pass, anything new fails, and the
// baseline shrinks as they are fixed. The widget is checked in both themes.

test.describe('accessibility', () => {
  test('sign-in page @a11y', async ({ anonymousPage }) => {
    await anonymousPage.goto('/login')
    await expect(anonymousPage.getByRole('button', { name: /sign in/i })).toBeVisible()
    await expectNoNewA11yViolations(anonymousPage, 'login')
  })

  // The dashboard is dark unless the user picks light (stored as cm-theme); both are checked.
  for (const scheme of ['dark', 'light'] as const) {
    const suffix = scheme === 'dark' ? '' : '-light'

    test(`dashboard screens, ${scheme} theme @a11y`, async ({ page, agent, agentsPage, aiConfigPage, ticketsPage, peoplePage }) => {
      // An agent of its own, so the agents screen is the list (with a card to check), not first-run setup.
      expect(agent.id).toBeTruthy()
      await page.addInitScript((theme) => localStorage.setItem('cm-theme', theme), scheme)
      await new InboxPage(page).goto()
      expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe(scheme)
      await expectNoNewA11yViolations(page, `inbox${suffix}`)
      await agentsPage.goto()
      await expectNoNewA11yViolations(page, `ai-agents${suffix}`)
      await aiConfigPage.goto()
      await expectNoNewA11yViolations(page, `ai-config${suffix}`)
      await ticketsPage.goto()
      await expectNoNewA11yViolations(page, `tickets${suffix}`)
      await peoplePage.goto()
      await expectNoNewA11yViolations(page, `people${suffix}`)
    })
  }

  for (const scheme of ['light', 'dark'] as const) {
    test(`widget, ${scheme} theme @a11y @widget`, async ({ widget }) => {
      await widget.page.emulateMedia({ colorScheme: scheme })
      await widget.embed()
      await widget.open()
      await expect(widget.messageInput).toBeEditable()
      await expectNoNewA11yViolations(widget.page, `widget-${scheme}`)
    })
  }
})
