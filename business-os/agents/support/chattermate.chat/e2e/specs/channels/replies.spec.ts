import { test, expect, channels, expectUnchanged, AI_REPLY } from '@e2e'

// The core promise of every channel: a customer writes in, the agent's answer goes
// back out on the same channel, to that customer.
for (const [name, connect] of Object.entries(channels)) {
  test(`a customer on ${name} gets the agent's answer back there @channels`, async ({ agent, llm, adminApi, request }) => {
    await llm.script(agent, (s) => s
      .when(/opening hours/i).reply('We are open 9am to 5pm, Monday to Friday.')
      .otherwise().reply('Happy to help!'))

    const channel = await connect({ api: adminApi, request, agentId: agent.id })
    const chat = channel.chatWith('Tess')
    await chat.send('What are your opening hours?')

    // Exactly one answer, the scripted one, from this account — no duplicate, no default.
    await expect.poll(() => chat.replies(), AI_REPLY).toEqual(['We are open 9am to 5pm, Monday to Friday.'])
    await expectUnchanged(`${name} replies`, () => chat.replies())
  })
}
