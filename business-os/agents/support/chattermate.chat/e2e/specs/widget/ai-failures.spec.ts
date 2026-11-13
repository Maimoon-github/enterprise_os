import { test, expect, AI_REPLY } from '@e2e'

// When the model fails, the customer gets an apology rather than silence or debris,
// and the very next message is answered normally.

const APOLOGY = 'I apologize, but I encountered an error, please try again later.'

test.describe('when the AI provider fails', () => {
  test('an error from the provider becomes an apology, and the chat carries on @widget', async ({ agent, llm, widget }) => {
    await llm.script(agent, (s) => s
      .when(/broken/).fail(500, 'upstream exploded')
      .otherwise().reply('Back to normal.'))

    await widget.embed()
    await widget.open()
    await widget.send('this is broken')
    await expect(widget.lastAgentMessage()).toHaveText(APOLOGY, AI_REPLY)
    await widget.send('hello again')
    await expect(widget.lastAgentMessage()).toHaveText('Back to normal.', AI_REPLY)
  })

  test('a provider that never answers is given up on, with an apology @widget @slow', async ({ agent, llm, widget }) => {
    // Longer than AGENT_RUN_TIMEOUT (.env.e2e), so the backend stops waiting.
    await llm.script(agent, (s) => s
      .when(/broken/).after(25_000).reply('Far too late.')
      .otherwise().reply('Back to normal.'))

    await widget.embed()
    await widget.open()
    await widget.send('this is broken')
    await expect(widget.lastAgentMessage()).toHaveText(APOLOGY, AI_REPLY)
    await widget.send('hello again')
    await expect(widget.lastAgentMessage()).toHaveText('Back to normal.', AI_REPLY)
    await expect(widget.agentMessages.filter({ hasText: 'Far too late.' })).toHaveCount(0)
  })

  test('a reply that is not the JSON asked for never reaches the customer raw @widget', async ({ agent, llm, widget }) => {
    await llm.script(agent, (s) => s
      .when(/broken/).malformed()
      .otherwise().reply('Back to normal.'))

    await widget.embed()
    await widget.open()
    await widget.send('this is broken')
    await expect(widget.lastAgentMessage()).toHaveText(APOLOGY, AI_REPLY)
    await widget.send('hello again')
    await expect(widget.lastAgentMessage()).toHaveText('Back to normal.', AI_REPLY)
  })
})
