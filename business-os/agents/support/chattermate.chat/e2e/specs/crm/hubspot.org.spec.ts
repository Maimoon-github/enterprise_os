import { test, expect, connectCrm, disconnectCrm, findPerson, FakeExternals, runWorkerOnce, syncPersonToCrm, unique, AI_REPLY } from '@e2e'

// One HubSpot connection per org, so this runs in the serial `org` project and
// disconnects afterwards.

test.describe('HubSpot', () => {
  test.use({ agentSettings: { leadCapture: true } })

  test.afterEach(async ({ adminApi }) => { await disconnectCrm(adminApi, 'hubspot') })

  test('a captured lead is pushed to HubSpot with what they told us @crm', async ({ agent, widget, llm, adminApi, request }) => {
    const code = unique('hs-code')
    await connectCrm(adminApi, 'hubspot', code)

    const { email, name } = widget.customer
    await llm.script(agent, (s) => s
      .when(/@/).captureLead('Thanks! Someone from sales will reach out.', { email, name, company: 'Acme Corp' })
      .otherwise().reply('Happy to set that up — what is your email?'))
    await widget.embed()
    await widget.open()
    await widget.send('I would like a demo')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to set that up — what is your email?', AI_REPLY)
    await widget.send(`Sure, I am ${name}, ${email}`)
    await expect(widget.lastAgentMessage()).toHaveText('Thanks! Someone from sales will reach out.', AI_REPLY)

    const person = await findPerson(adminApi, email)
    const status = await syncPersonToCrm(adminApi, person.id)
    expect(status.synced.map((s) => s.provider)).toContain('hubspot')

    // What HubSpot received: the contact keyed by email, as a lead, with their company,
    // sent with the token this org's install was granted.
    const externals = new FakeExternals(request)
    const [upsert] = await externals.calls('hubspot', 'upsert', { contains: email })
    const [grant] = await externals.calls('hubspot', 'token', { contains: code })
    expect(upsert.headers.authorization).toBe(`Bearer ${(grant.response as { access_token: string }).access_token}`)
    expect(upsert.body).toMatchObject({
      inputs: [{ id: email, idProperty: 'email', properties: { email, company: 'Acme Corp', lifecyclestage: 'lead' } }],
    })
  })

  test('with HubSpot as the agent\'s CRM, a captured lead is pushed on its own @crm @workers', async ({ agent, widget, llm, adminApi, request }) => {
    await connectCrm(adminApi, 'hubspot', unique('hs-code'))
    await adminApi.put(`/agent/${agent.id}/lead-capture`, { data: { enabled: true, require_consent: false, crm_sync_target: 'hubspot' } })

    const { email, name } = widget.customer
    await llm.script(agent, (s) => s
      .when(/@/).captureLead('Thanks! Someone from sales will reach out.', { email, name, company: 'Globex' })
      .otherwise().reply('Happy to set that up — what is your email?'))
    await widget.embed()
    await widget.open()
    await widget.send('I would like a demo')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to set that up — what is your email?', AI_REPLY)
    await widget.send(`Sure, I am ${name}, ${email}`)
    await expect(widget.lastAgentMessage()).toHaveText('Thanks! Someone from sales will reach out.', AI_REPLY)

    // Capture queues a sync job; the CRM worker pushes it on its next pass.
    const externals = new FakeExternals(request)
    expect(await externals.calls('hubspot', 'upsert', { contains: email })).toHaveLength(0)
    await runWorkerOnce('crm-sync')
    const [upsert] = await externals.calls('hubspot', 'upsert', { contains: email })
    expect(upsert.body).toMatchObject({ inputs: [{ id: email, properties: { company: 'Globex', lifecyclestage: 'lead' } }] })
  })
})
