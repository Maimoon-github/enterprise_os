import { test, expect, enableHelpCenter, helpCenterChat, setAllowedDomains, setHelpCenterChat, AI_REPLY, type HelpCenterChat } from '@e2e'

// The help center can carry an agent's chat widget. It is one of our own pages, so
// the widget shows there whatever sites its allowed domains list. The help center's
// chat is org-wide, so this runs in the serial `org` project and puts it back.

let before: HelpCenterChat

test.beforeEach(async ({ adminApi }) => { before = await helpCenterChat(adminApi) })

test.afterEach(async ({ adminApi }) => { await setHelpCenterChat(adminApi, before) })

test('the help center shows the chat even when the widget is limited to other sites @help-center @widget', async ({ agent, widget, llm, adminApi }) => {
  const site = await enableHelpCenter(adminApi)
  await setHelpCenterChat(adminApi, { agentId: agent.id, enabled: true })
  await setAllowedDomains(adminApi, widget.widgetId, ['shop.example.com'])
  await llm.script(agent, (s) => s.otherwise().reply('Ask me anything about our help articles.'))

  await widget.visit(site)
  await widget.open()
  await widget.send('Hi')
  await expect(widget.lastAgentMessage()).toHaveText('Ask me anything about our help articles.', AI_REPLY)
})
