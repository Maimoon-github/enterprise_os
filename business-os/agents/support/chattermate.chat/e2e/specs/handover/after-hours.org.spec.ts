import { test, expect, channels, chatsWithAgent, setAlwaysClosed, setAlwaysOpen, unique, AI_REPLY } from '@e2e'

// Changes the org's business hours, so it runs in the serial `org` project and
// reopens the org afterwards (setup leaves it open 24/7).

test.describe('outside business hours', () => {
  test.use({ agentSettings: { transferToHuman: true } })

  test.afterEach(async ({ adminApi, org }) => { await setAlwaysOpen(adminApi, org.orgId) })

  test('a customer asking for a person is told the team will follow up, and the chat waits in the team\'s queue @handover', async ({ agent, llm, adminApi, request, org, handoverTeam }) => {
    await setAlwaysClosed(adminApi, org.orgId)
    await llm.script(agent, (s) => s.otherwise().handOver('We are closed now; the team will get back to you.'))

    const chat = (await channels.WhatsApp({ api: adminApi, request, agentId: agent.id })).chatWith(unique('Nora'))
    await chat.send('I need to talk to someone')
    await expect.poll(() => chat.replies(), AI_REPLY).toEqual(['We are closed now; the team will get back to you.'])

    // Queued for the team, unclaimed — whoever opens up next picks it up.
    const [conversation] = await chatsWithAgent(adminApi, agent.id)
    expect(conversation).toMatchObject({ status: 'transferred', group_id: (await handoverTeam()).groupId, user_id: null })
    // The reply was written knowing the team is closed.
    const prompts = (await llm.requests(agent)).map((r) => r.lastUser).join('\n')
    expect(prompts).toContain('Currently within business hours: False')
  })
})
