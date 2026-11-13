import { test, expect, connectWhatsAppNumber, deliverMeta, expectUnchanged, phoneNumber, routeToAgent, whatsappPayload, FakeExternals, AI_REPLY } from '@e2e'

// Providers retry a webhook they think failed. Dedupe lives in Redis, which only
// the nightly Redis run turns on (scripts/stack.sh E2E_REDIS_URL); playwright.config.ts
// leaves @redis tests out otherwise.

test('a provider delivering the same message twice gets one answer @channels @redis', async ({ agent, llm, adminApi, request }) => {
  await llm.script(agent, (s) => s.otherwise().reply('Answered once.'))
  const number = await connectWhatsAppNumber(adminApi)
  await routeToAgent(adminApi, number.account.id, agent.id)
  const waId = phoneNumber().slice(1)

  // The exact same delivery, message id included, twice.
  const payload = whatsappPayload(number.phoneNumberId, waId, 'Rita', { type: 'text', text: { body: 'Hello?' } })
  await deliverMeta(request, payload)
  await deliverMeta(request, payload)

  const sent = async () => (await new FakeExternals(request).calls('graph', 'messages', { contains: waId }))
    .filter((c) => (c.body as { type?: string }).type === 'text').length
  await expect.poll(sent, AI_REPLY).toBe(1)
  await expectUnchanged('replies to the retried message', sent)
  expect(await llm.requests(agent)).toHaveLength(1)
})
