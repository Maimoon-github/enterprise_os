import { test, expect, AI_REPLY, createWidgetApp, customizeAgent, findPerson, issueConversationToken, unique } from '@e2e'

// An email typed into the widget is not proof of being that customer. Someone else
// who types it gets the same person in the inbox, but never their conversations,
// and never the right to change who they are.
test.describe('conversation ownership', () => {
  test.beforeEach(async ({ agent, adminApi }) => {
    await customizeAgent(adminApi, agent.id, { collect_email: true })
  })

  test('a second browser that gives a customer\'s email starts its own conversation @widget @security', async ({ agent, widget, makeVisitor, llm }) => {
    await llm.script(agent, (s) => s
      .when(/order/i).reply('Order 1234 ships tomorrow.')
      .otherwise().reply('Happy to help!'))

    await widget.embed()
    await widget.openToEmailGate()
    await widget.giveEmail()
    await widget.send('Where is my order 1234?')
    await expect(widget.lastAgentMessage()).toHaveText('Order 1234 ships tomorrow.', AI_REPLY)

    const stranger = await makeVisitor(widget.customer)
    await stranger.embed()
    await stranger.openToEmailGate()
    await stranger.giveEmail()
    await stranger.send('Hello')
    await expect(stranger.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)
    // Their reply has arrived, so the history has loaded: only their own message is in it.
    await expect(stranger.customerMessages).toHaveText(['Hello'])

    await widget.page.reload()
    await widget.open()
    await expect(widget.lastAgentMessage()).toHaveText('Order 1234 ships tomorrow.', AI_REPLY)
    await expect(widget.customerMessages).toHaveText(['Where is my order 1234?'])
  })

  test.describe('lead capture', () => {
    test.use({ agentSettings: { leadCapture: true } })

    test('a visitor who only typed a customer\'s email cannot rename them or make them a lead @widget @security @leads', async ({ agent, widget, makeVisitor, llm, adminApi }) => {
      const { email } = widget.customer
      await llm.script(agent, (s) => s
        .when(/Someone Else/).captureLead('Thanks, noted.', { email, name: 'Someone Else' })
        .otherwise().reply('Happy to help!'))

      await widget.embed()
      await widget.openToEmailGate()
      await widget.giveEmail()
      await widget.send('Hello')
      await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)

      const stranger = await makeVisitor(widget.customer)
      await stranger.embed()
      await stranger.openToEmailGate()
      await stranger.giveEmail()
      await stranger.send(`I am Someone Else, ${email}`)
      await expect(stranger.lastAgentMessage()).toHaveText('Thanks, noted.', AI_REPLY)

      const person = await findPerson(adminApi, email)
      expect(person.name).not.toBe('Someone Else')
      expect(person.lead_stage).toBe('visitor')
    })
  })

  test('an address claimed before its owner signs in gives the claimer none of their chats @widget @security', async ({ agent, widget, makeVisitor, llm, adminApi }) => {
    await llm.script(agent, (s) => s
      .when(/invoice/i).reply('Your invoice is on its way.')
      .otherwise().reply('Happy to help!'))
    const owner = { name: `Owner ${unique('owner')}`, email: `${unique('owner')}@example.com` }

    // Someone claims the address first, through the widget's email gate.
    const claimer = await makeVisitor(owner)
    await claimer.embed()
    await claimer.openToEmailGate()
    await claimer.giveEmail()
    await claimer.send('Hello')
    await expect(claimer.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)

    // Then the site signs its real owner in, and they chat.
    const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))
    const token = await issueConversationToken(adminApi, apiKey, widget.widgetId, owner)
    await widget.embed({ token })
    await widget.open()
    await widget.send('Where is my invoice?')
    await expect(widget.lastAgentMessage()).toHaveText('Your invoice is on its way.', AI_REPLY)

    // The claimer comes back: still able to chat, but in a conversation of their own.
    await claimer.page.reload()
    await claimer.open()
    await claimer.send('Anything new?')
    await expect(claimer.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)
    await expect(claimer.customerMessages).toHaveText(['Anything new?'])

    await widget.page.reload()
    await widget.open()
    await expect(widget.customerMessages).toHaveText(['Where is my invoice?'])
  })
})

// What scoping a conversation to its browser must not take away.
test.describe('a visitor keeps their own conversation', () => {
  test('a second tab of the same browser joins the same conversation @widget', async ({ agent, widget, llm }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Happy to help!'))

    await widget.embed()
    await widget.open()
    await widget.send('Hello from the first tab')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)

    const tab = await widget.inAnotherTab()
    await tab.embed()
    await tab.open()
    await expect(tab.customerMessages).toHaveText(['Hello from the first tab'])
  })

  test('a visitor the site signed in finds their conversation in another browser @widget', async ({ agent, widget, makeVisitor, llm, adminApi }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Happy to help!'))
    const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))

    await widget.embed({ token: await issueConversationToken(adminApi, apiKey, widget.widgetId, widget.customer) })
    await widget.open()
    await widget.send('Started on my laptop')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)

    const phone = await makeVisitor(widget.customer)
    await phone.embed({ token: await issueConversationToken(adminApi, apiKey, widget.widgetId, widget.customer) })
    await phone.open()
    await expect(phone.customerMessages).toHaveText(['Started on my laptop'])
  })

  test('a site that signs the visitor in with identify() hands the widget their conversation @widget', async ({ agent, widget, makeVisitor, llm, adminApi }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Happy to help!'))
    const { apiKey } = await createWidgetApp(adminApi, unique('acme-site'))

    await widget.embed({ token: await issueConversationToken(adminApi, apiKey, widget.widgetId, widget.customer) })
    await widget.open()
    await widget.send('Signed-in question')
    await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)

    // The same person opens the site signed out, then signs in on the page.
    const later = await makeVisitor(widget.customer)
    await later.embed()
    await later.open()
    await later.api('identify', await issueConversationToken(adminApi, apiKey, widget.widgetId, widget.customer))
    await later.open()
    await expect(later.customerMessages).toHaveText(['Signed-in question'])
  })
})
