import { test, expect } from '@e2e'

interface AgentPerformance { bot_agents: Array<{ id: string; avg_rating: number; rating_count: number }> }

test.describe('chat rating', () => {
  test.use({ agentSettings: { askForRating: true } })

  test('a customer rates the chat when the agent wraps up, and the rating is recorded against the agent @widget', async ({ agent, widget, llm, adminApi }) => {
    await llm.script(agent, (s) => s
      .when(/that is all|thanks/i).endChat('Glad I could help. Goodbye!')
      .otherwise().reply('Sure thing.'))

    await widget.embed()
    await widget.open()
    await widget.send('That is all, thanks')

    await expect(widget.ratingPrompt).toBeVisible()
    await widget.rate(4)
    await expect(widget.ratingThanks).toBeVisible()

    // The thanks is client-side; the agent's numbers are what the team actually sees.
    const ratingOf = async () => (await adminApi.get<AgentPerformance>('/analytics/agent-performance', { params: { time_range: '24h' } }))
      .bot_agents.find((a) => a.id === agent.id)
    await expect.poll(ratingOf).toMatchObject({ rating_count: 1, avg_rating: 4 })
  })
})
