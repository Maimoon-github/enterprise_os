import { test, expect, channelsWithButtons, AI_REPLY } from '@e2e'

test.describe('reply buttons', () => {
  test.use({ agentSettings: { channelQuickReplies: true } })

  for (const [name, connect] of Object.entries(channelsWithButtons)) {
    test(`the AI offers buttons on ${name} and a tap gets the next answer @channels`, async ({ agent, llm, adminApi, request }) => {
      await llm.script(agent, (s) => s
        .when(/track my order/i).reply('Your order ships tomorrow.')
        .otherwise().reply('What can I help you with?', { quick_replies: ['Track my order', 'Returns'] }))

      const chat = (await connect({ api: adminApi, request, agentId: agent.id })).chatWith('Tess')
      await chat.send('Hi')
      await expect.poll(() => chat.buttons(), AI_REPLY).toEqual(['Track my order', 'Returns'])

      await chat.tap('Track my order')
      await expect.poll(async () => (await chat.replies()).at(-1), AI_REPLY).toContain('Your order ships tomorrow.')
      expect(await chat.replies()).toHaveLength(2)
    })
  }
})
