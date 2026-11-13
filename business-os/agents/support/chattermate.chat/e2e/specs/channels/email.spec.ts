import { test, expect, channels, expectUnchanged, Mailbox, AI_REPLY } from '@e2e'

test('an email reply stays in the customer\'s thread @channels', async ({ agent, llm, adminApi, request }) => {
  await llm.script(agent, (s) => s.otherwise().reply('Happy to help with that.'))

  const chat = (await channels.Email({ api: adminApi, request, agentId: agent.id })).chatWith('Tess')
  await chat.send('Can I change my delivery address?')

  const mailbox = new Mailbox(request)
  await expect.poll(async () => (await mailbox.messagesTo(chat.address)).length, AI_REPLY).toBe(1)
  // One question, one model call, one email — a duplicate would arrive later.
  expect(await llm.requests(agent)).toHaveLength(1)
  await expectUnchanged('emails to the customer', async () => (await mailbox.messagesTo(chat.address)).length)
  const [reply] = await mailbox.messagesTo(chat.address)
  expect(reply.subject).toBe(`Re: ${chat.subject}`)
  // In-Reply-To is what makes mail clients file the answer under the question.
  expect((await mailbox.headers(reply.id))['In-Reply-To']).toEqual([chat.lastMessageId])
})

test('a customer\'s follow-up email continues the same conversation @channels', async ({ agent, llm, adminApi, request }) => {
  await llm.script(agent, (s) => s
    .when(/tuesday/i).reply('Tuesday works — I have noted it.')
    .otherwise().reply('Happy to help with that. Which day suits you?'))

  const chat = (await channels.Email({ api: adminApi, request, agentId: agent.id })).chatWith('Tess')
  await chat.send('Can I change my delivery day?')
  await expect.poll(() => chat.replies(), AI_REPLY).toHaveLength(1)
  await chat.send('Tuesday please')
  await expect.poll(() => chat.replies(), AI_REPLY).toEqual([
    'Happy to help with that. Which day suits you?',
    'Tuesday works — I have noted it.',
  ])

  // One conversation for this sender, holding both exchanges — not two.
  const conversations = await adminApi.get<Array<{ message_count: number }>>('/chats/recent', { params: { customer_email: chat.address } })
  expect(conversations).toHaveLength(1)
  expect(conversations[0].message_count).toBe(4)
})
