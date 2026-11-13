import { test, expect, channels, chatsWithAgent, createGroup, createUser, unique, AI_REPLY } from '@e2e'

test('with nobody from the team online, the customer is told the team will follow up, and the chat waits in its queue @handover', async ({ makeAgent, llm, adminApi, request }) => {
  // A team whose only member has never signed in, so nobody is online.
  const id = unique('offline')
  const member = await createUser(adminApi, { name: `Offline ${id}`, email: `${id}@e2e.example.com`, password: 'E2e-Offline-Passw0rd!', role: 'Agent' })
  const groupId = await createGroup(adminApi, `Team ${id}`, [member])
  const agent = await makeAgent({ transferToHuman: true }, [groupId])
  await llm.script(agent, (s) => s.otherwise().handOver('Our team will get back to you shortly.'))

  const chat = (await channels.WhatsApp({ api: adminApi, request, agentId: agent.id })).chatWith(unique('Nora'))
  await chat.send('I need to talk to someone')
  await expect.poll(() => chat.replies(), AI_REPLY).toEqual(['Our team will get back to you shortly.'])

  const [conversation] = await chatsWithAgent(adminApi, agent.id)
  expect(conversation).toMatchObject({ status: 'transferred', group_id: groupId, user_id: null })
  // The reply was written knowing nobody is online.
  const prompts = (await llm.requests(agent)).map((r) => r.lastUser).join('\n')
  expect(prompts).toContain('(0 online)')
})
