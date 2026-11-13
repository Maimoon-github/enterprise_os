import { test, expect, customizeAgent } from '@e2e'

// Screenshot baselines are generated on Linux in CI (the nightly job, or the e2e
// workflow run by hand with "update snapshots") and committed from its artifact.
// Never commit a baseline made on a Mac: fonts render differently.

test.describe('widget appearance', () => {
  for (const scheme of ['light', 'dark'] as const) {
    test(`launcher and open chat, ${scheme} @visual @widget`, async ({ agent, adminApi, widget }) => {
      // Fixed name and text, so nothing in the shot changes from run to run (the
      // avatar is drawn from the name, too).
      await adminApi.put(`/agent/${agent.id}`, { data: { display_name: 'Acme Support' } })
      await customizeAgent(adminApi, agent.id, { welcome_message: 'Hi! How can we help today?' })
      await widget.page.emulateMedia({ colorScheme: scheme })
      await widget.embed()
      await expect(widget.launcher).toBeVisible()
      await expect(widget.launcher).toHaveScreenshot(`launcher-${scheme}.png`)

      await widget.open()
      await expect(widget.welcomeMessage).toBeVisible()
      await expect(widget.agentName).toHaveText('Acme Support')
      await expect(widget.panel).toHaveScreenshot(`chat-${scheme}.png`)
    })
  }
})
