import { test, expect, AI_REPLY } from '@e2e'

interface AgentPerformance { bot_agents: Array<{ id: string; total_chats: number }> }

test.describe('analytics', () => {
  test('a conversation shows up in the agent\'s numbers, and the dashboard renders without errors @analytics', async ({ agent, widget, llm, adminApi, page }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Happy to help!'))
    await widget.embed()
    await widget.open()
    await widget.send('Hello')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)

    const chatsOf = async () => (await adminApi.get<AgentPerformance>('/analytics/agent-performance', { params: { time_range: '24h' } }))
      .bot_agents.find((a) => a.id === agent.id)?.total_chats
    await expect.poll(chatsOf).toBe(1)

    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto('/analytics')
    await expect(page.getByRole('main').getByRole('heading', { name: 'Total Conversations' })).toBeVisible()
    // The shared test org has hundreds of agents; the dashboard lists the busiest,
    // so this one's row is checked through the API above.
    expect(errors).toEqual([])
  })
})
