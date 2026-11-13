import { test, expect, channels, FakeExternals, unique, AI_REPLY } from '@e2e'

test.describe('when a channel refuses a message', () => {
  test.use({ agentSettings: { transferToHuman: true } })

  test('the teammate is told it was not delivered, and the next one goes through @channels @handover', async ({ agent, llm, adminApi, request, inbox }) => {
    await llm.script(agent, (s) => s.otherwise().handOver('Let me connect you with a teammate.'))
    const customer = unique('Wanda')
    const chat = (await channels.WhatsApp({ api: adminApi, request, agentId: agent.id })).chatWith(customer)
    await chat.send('I need a person')
    await expect.poll(() => chat.replies(), AI_REPLY).toHaveLength(1)

    await inbox.goto()
    await inbox.openConversationWith(customer)
    await inbox.takeOver()

    // WhatsApp refuses free-form messages outside the 24-hour window with error 131047.
    const restore = await new FakeExternals(request).fail({
      provider: 'graph',
      action: 'messages',
      contains: chat.waId,
      status: 400,
      body: { error: { message: 'Re-engagement message', type: 'OAuthException', code: 131047, fbtrace_id: 'e2e' } },
      times: 1,
    })
    await inbox.reply('Are you still there?')
    await expect(inbox.agentMessage('Are you still there?')).toContainText('Not delivered')
    await restore()

    await inbox.reply('Here is your tracking link.')
    await expect.poll(() => chat.replies(), AI_REPLY).toContain('Here is your tracking link.')
    await expect(inbox.agentMessage('Here is your tracking link.')).not.toContainText('Not delivered')
    expect(await chat.replies()).not.toContain('Are you still there?')
  })
})

test.describe('choices that do not fit a channel\'s buttons', () => {
  test.use({ agentSettings: { channelQuickReplies: true } })

  test('five options become a WhatsApp list within its limits, and a pick still gets its answer @channels', async ({ agent, llm, adminApi, request }) => {
    const options = ['Track my order', 'Returns', 'Change my delivery address', 'Billing question', 'Talk to someone']
    await llm.script(agent, (s) => s
      .when(/change my delivery address/i).reply('Sure — what is the new address?')
      .otherwise().reply('What can I help you with?', { quick_replies: options }))

    const chat = (await channels.WhatsApp({ api: adminApi, request, agentId: agent.id })).chatWith('Tess')
    await chat.send('Hi')
    // More than three buttons is a list; the fake rejects anything past WhatsApp's real limits.
    await expect.poll(() => chat.buttons(), AI_REPLY).toHaveLength(5)
    const titles = await chat.buttons()
    for (const title of titles) expect([...title].length).toBeLessThanOrEqual(24)

    await chat.tap(titles[2])
    await expect.poll(async () => (await chat.replies()).at(-1), AI_REPLY).toBe('Sure — what is the new address?')
  })

  test('a button title longer than WhatsApp allows is shortened, and the tap still works @channels', async ({ agent, llm, adminApi, request }) => {
    const long = 'Change my delivery address please'
    await llm.script(agent, (s) => s
      .when(/change my delivery address/i).reply('Sure — what is the new address?')
      .otherwise().reply('What can I help you with?', { quick_replies: [long, 'Returns'] }))

    const chat = (await channels.WhatsApp({ api: adminApi, request, agentId: agent.id })).chatWith('Tess')
    await chat.send('Hi')
    await expect.poll(() => chat.buttons(), AI_REPLY).toHaveLength(2)
    const [shortened] = await chat.buttons()
    expect([...shortened].length).toBeLessThanOrEqual(24)

    await chat.tap(shortened)
    await expect.poll(async () => (await chat.replies()).at(-1), AI_REPLY).toBe('Sure — what is the new address?')
  })
})
