import { test, expect, AI_REPLY } from '@e2e'

// The dashboard also offers an iframe snippet: the chat page itself, served by
// the API. Its socket comes from the API's own origin, which must be allowed
// whether or not the operator listed it in CORS_ORIGINS.

test('a customer chats through the iframe snippet @widget', async ({ agent, widget, llm }) => {
  await llm.script(agent, (s) => s.otherwise().reply('Hello from the iframe'))

  await widget.embed({ snippet: 'iframe' })
  await widget.expectReady()
  await widget.send('Hi')
  await expect(widget.lastAgentMessage()).toHaveText('Hello from the iframe', AI_REPLY)
})
