import { test, expect, AI_REPLY } from '@e2e'

interface People { items: Array<{ id: string; email: string | null }> }
interface Person { name: string | null; email: string | null; lead_stage: string; captured_attributes: Record<string, unknown> }

test.describe('lead capture', () => {
  test.use({ agentSettings: { leadCapture: true } })

  test('a visitor who shares their details shows up as a lead, with what they told us @leads', async ({ agent, widget, llm, peoplePage, adminApi }) => {
    const { email, name } = widget.customer
    await llm.script(agent, (s) => s
      .when(/@/).captureLead('Thanks! Someone from sales will reach out.', { email, name, company: 'Acme Corp' })
      .otherwise().reply('Happy to set that up — what is your email?'))

    await widget.embed()
    await widget.open()
    await widget.send('I would like a demo')
    // A visitor answers the question once it is asked; replies to back-to-back
    // messages are produced concurrently and may arrive in either order.
    await expect(widget.lastAgentMessage()).toHaveText('Happy to set that up — what is your email?', AI_REPLY)
    await widget.send(`Sure, I am ${name}, ${email}`)
    await expect(widget.lastAgentMessage()).toHaveText('Thanks! Someone from sales will reach out.', AI_REPLY)

    await peoplePage.goto()
    await peoplePage.findLead(email)
    await expect(peoplePage.person(email)).toContainText('Lead')

    const [found] = (await adminApi.get<People>('/people', { params: { search: email } })).items
    const person = await adminApi.get<Person>(`/people/${found.id}`)
    expect(person).toMatchObject({ name, email })
    expect(JSON.stringify(person.captured_attributes)).toContain('Acme Corp')
  })
})
