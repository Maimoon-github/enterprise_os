import { test, expect, channels, findPerson, phoneNumber, AI_REPLY } from '@e2e'

// The People directory's edit rules, at the API the drawer uses.

test.describe('People', () => {
  test('a contact can be renamed, given a phone and marked as a customer @leads', async ({ agent, llm, adminApi, request }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Thanks for writing in.'))
    const chat = (await channels.Email({ api: adminApi, request, agentId: agent.id })).chatWith('Tess')
    await chat.send('Hello')
    await expect.poll(() => chat.replies(), AI_REPLY).toHaveLength(1)
    const person = await findPerson(adminApi, chat.address)

    const phone = phoneNumber()
    await adminApi.patch(`/people/${person.id}`, { data: { full_name: 'Tess Tester', phone } })
    await adminApi.post(`/people/${person.id}/mark-customer`)

    expect(await adminApi.get(`/people/${person.id}`)).toMatchObject({ name: 'Tess Tester', phone, lead_stage: 'customer' })
  })

  test('a phone number must be international and can belong to only one person @leads', async ({ agent, llm, adminApi, request }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Thanks for writing in.'))
    const inbox = await channels.Email({ api: adminApi, request, agentId: agent.id })
    const ann = inbox.chatWith('Ann')
    const ben = inbox.chatWith('Ben')
    await ann.send('Hello')
    await ben.send('Hello')
    await expect.poll(() => ann.replies(), AI_REPLY).toHaveLength(1)
    await expect.poll(() => ben.replies(), AI_REPLY).toHaveLength(1)
    const annPerson = await findPerson(adminApi, ann.address)
    const benPerson = await findPerson(adminApi, ben.address)

    const local = await adminApi.raw('PATCH', `/people/${annPerson.id}`, { data: { phone: '07700 900123' } })
    expect(local.status()).toBe(400)
    expect(await local.text()).toContain('international format')

    const shared = phoneNumber()
    await adminApi.patch(`/people/${annPerson.id}`, { data: { phone: shared } })
    const taken = await adminApi.raw('PATCH', `/people/${benPerson.id}`, { data: { phone: shared } })
    expect(taken.status()).toBe(400)
    expect(await taken.text()).toContain('already belongs to another person')
  })

  test('once a WhatsApp contact has given a real email, their number can no longer be changed away @leads', async ({ makeAgent, llm, adminApi, request }) => {
    // Their phone is now the only thing an incoming WhatsApp message can find them by.
    const agent = await makeAgent({ leadCapture: true })
    const email = `wes.${Date.now()}@example.com`
    await llm.script(agent, (s) => s.otherwise().captureLead('Thanks, noted.', { email, name: 'Wes' }))
    const chat = (await channels.WhatsApp({ api: adminApi, request, agentId: agent.id })).chatWith('Wes')
    await chat.send(`It is ${email}`)
    await expect.poll(() => chat.replies(), AI_REPLY).toHaveLength(1)
    const person = await findPerson(adminApi, email)

    const response = await adminApi.raw('PATCH', `/people/${person.id}`, { data: { phone: phoneNumber() } })
    expect(response.status()).toBe(400)
    expect(await response.text()).toContain('how their WhatsApp messages find them')
    expect((await adminApi.get<{ phone: string }>(`/people/${person.id}`)).phone).toContain(chat.waId)
  })
})
