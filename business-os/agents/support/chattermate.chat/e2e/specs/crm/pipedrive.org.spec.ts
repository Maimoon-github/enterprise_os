import { test, expect, connectCrm, disconnectCrm, findPerson, FakeExternals, syncPersonToCrm, unique, AI_REPLY } from '@e2e'

// One Pipedrive connection per org, so this runs in the serial `org` project and
// disconnects afterwards.

interface PipedriveGrant { access_token: string; api_domain: string }

test.describe('Pipedrive', () => {
  test.use({ agentSettings: { leadCapture: true } })

  test.afterEach(async ({ adminApi }) => { await disconnectCrm(adminApi, 'pipedrive') })

  test('a captured lead becomes a Pipedrive person, organisation and lead with a note @crm', async ({ agent, widget, llm, adminApi, request }) => {
    const code = unique('pd-code')
    await connectCrm(adminApi, 'pipedrive', code)

    const { email, name } = widget.customer
    const company = unique('Initech')
    await llm.script(agent, (s) => s
      .when(/@/).captureLead('Thanks! Someone from sales will reach out.', { email, name, company })
      .otherwise().reply('Happy to set that up — what is your email?'))
    await widget.embed()
    await widget.open()
    await widget.send('I would like a demo')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to set that up — what is your email?', AI_REPLY)
    await widget.send(`Sure, I am ${name}, ${email}`)
    await expect(widget.lastAgentMessage()).toHaveText('Thanks! Someone from sales will reach out.', AI_REPLY)

    const person = await findPerson(adminApi, email)
    const status = await syncPersonToCrm(adminApi, person.id)
    expect(status.synced.map((s) => s.provider)).toContain('pipedrive')

    // The install traded the code with the app's own credentials (Basic auth), and
    // every API call went to the company's api_domain with the token it was granted.
    const externals = new FakeExternals(request)
    const [grant] = await externals.calls('pipedrive-oauth', 'token', { contains: code })
    const basic = `Basic ${Buffer.from('e2e-pipedrive-client-id:e2e-pipedrive-client-secret').toString('base64')}`
    expect(grant.headers.authorization).toBe(basic)
    const { access_token: token } = grant.response as PipedriveGrant

    const [organization] = await externals.calls('pipedrive', 'organizations', { contains: company })
    expect(organization.body).toEqual({ name: company })
    const [created] = await externals.calls('pipedrive', 'persons', { contains: email })
    expect(created.method).toBe('POST')
    expect(created.headers.authorization).toBe(`Bearer ${token}`)
    expect(created.body).toMatchObject({
      name, emails: [{ value: email, primary: true }], org_id: (organization.response as { data: { id: number } }).data.id,
    })

    const personId = (created.response as { data: { id: number } }).data.id
    const [lead] = (await externals.calls('pipedrive', 'leads', { contains: `"person_id":${personId}` })).filter((c) => c.method === 'POST')
    expect(lead.body).toMatchObject({ title: `${name} — ChatterMate lead`, person_id: personId })
    const leadId = (lead.response as { data: { id: string } }).data.id
    const [note] = await externals.calls('pipedrive', 'notes', { contains: leadId })
    expect(note.body).toMatchObject({ lead_id: leadId, content: expect.stringContaining('Lead captured by ChatterMate') })
  })
})
