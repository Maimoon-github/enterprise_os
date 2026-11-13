import { test, expect, chatMessages, chatsWithAgent, runWorkerOnce, sql, unique, uuid, AI_REPLY } from '@e2e'

test.describe('tickets', () => {
  test('the AI opens a ticket that an agent then works in the dashboard @tickets', async ({ agent, widget, llm, ticketsPage }) => {
    const summary = `Checkout button does nothing ${unique('T')}`
    await llm.script(agent, (s) => s
      .when(/broken|does nothing/i).createTicket('I have logged this for our team.', summary)
      .otherwise().reply('Happy to help!'))

    await widget.embed()
    await widget.open()
    await widget.send('The checkout button does nothing when I click it')
    await expect(widget.lastAgentMessage()).toHaveText('I have logged this for our team.', AI_REPLY)

    await ticketsPage.goto()
    await ticketsPage.open(summary)
    await ticketsPage.setStatus('In progress')
    await ticketsPage.page.reload()
    await expect(ticketsPage.statusLabel).toHaveText('In progress')
  })
})

test.describe('resolving a ticket', () => {
  test('the customer hears about the fix in the chat the ticket came from @tickets', async ({ agent, widget, llm, ticketsPage, adminApi }) => {
    const summary = `Coupon code rejected ${unique('T')}`
    await llm.script(agent, (s) => s
      .when(/coupon/i).createTicket('I have logged this for our team.', summary)
      .otherwise().reply('Happy to help!'))
    await widget.embed()
    await widget.open()
    await widget.send('My coupon code is rejected at checkout')
    await expect(widget.lastAgentMessage()).toHaveText('I have logged this for our team.', AI_REPLY)

    await ticketsPage.goto()
    await ticketsPage.open(summary)
    const ticketId = new URL(ticketsPage.page.url()).pathname.split('/').at(-1)
    await adminApi.post(`/tickets/${ticketId}/resolve`, {
      data: { outcome: 'fixed', resolution_summary: 'Expired promotion table', customer_message: 'Good news: your coupon works again.' },
    })

    await expect(widget.lastAgentMessage()).toContainText('Good news: your coupon works again.', AI_REPLY)
    await ticketsPage.page.reload()
    await expect(ticketsPage.statusLabel).toHaveText('Resolved · confirming')
  })
})

// The rating request comes from the ticket worker, a separate process; it reaches
// the visitor's open widget through Redis, as in production — so @redis (nightly).
test.describe('ticket satisfaction', () => {
  test.use({ agentSettings: { askForRating: true } })

  test('a resolved ticket closes after its confirmation window and asks the customer for a rating, which is kept @tickets @workers @redis', async ({ agent, widget, llm, ticketsPage, adminApi }) => {
    const summary = `Invoice shows the wrong VAT ${unique('T')}`
    await llm.script(agent, (s) => s
      .when(/invoice/i).createTicket('I have logged this for our team.', summary)
      .otherwise().reply('Happy to help!'))
    await widget.embed()
    await widget.open()
    await widget.send('My invoice shows the wrong VAT')
    await expect(widget.lastAgentMessage()).toHaveText('I have logged this for our team.', AI_REPLY)

    await ticketsPage.goto()
    await ticketsPage.open(summary)
    const ticketId = uuid(new URL(ticketsPage.page.url()).pathname.split('/').at(-1)!)
    await adminApi.post(`/tickets/${ticketId}/resolve`, { data: { outcome: 'fixed', customer_message: 'Fixed: a corrected invoice is on its way.' } })
    await expect(widget.lastAgentMessage()).toContainText('Fixed: a corrected invoice is on its way.', AI_REPLY)

    // The customer never replies; the confirmation window (72h by default) runs out.
    sql(`UPDATE tickets SET confirmation_requested_at = now() - interval '73 hours' WHERE id = '${ticketId}'`)
    await runWorkerOnce('ticket-lifecycle')

    await expect(widget.ratingPrompt).toBeVisible(AI_REPLY)
    await widget.rate(4)
    await expect(widget.ratingThanks).toBeVisible()
    await expect.poll(async () => (await adminApi.get<{ ticket: { status: string; csat_score: number | null } }>(`/tickets/${ticketId}`)).ticket)
      .toMatchObject({ status: 'closed', csat_score: 4 })

    // The ask is part of the conversation, so agents see it in the thread too.
    const [chat] = await chatsWithAgent(adminApi, agent.id)
    const asks = (await chatMessages(adminApi, chat.session_id)).filter((m) => m.message?.startsWith('How did we do on ticket'))
    expect(asks).toHaveLength(1)
  })
})
