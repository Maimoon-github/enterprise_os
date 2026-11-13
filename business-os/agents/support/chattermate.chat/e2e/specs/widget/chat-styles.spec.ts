import { test, expect, AI_REPLY, customizeAgent, findPerson } from '@e2e'

// Each way a visitor reaches the chat, and each again when the first answer that
// binds them to a customer goes missing (the socket then gets the page's anonymous
// token and the widget has to authorize again).
for (const lost of [false, true]) {
  const when = lost ? ', even when its first authorization goes missing' : ''

  test.describe(`chat styles${lost ? ' (first authorization lost)' : ''}`, () => {
    test.beforeEach(async ({ widget }) => {
      if (lost) await widget.loseFirstAuthorization()
    })

    test(`an email-first agent: the visitor gives an email and gets the answer${when} @widget`, async ({ agent, widget, llm, adminApi }) => {
      await customizeAgent(adminApi, agent.id, { collect_email: true })
      await llm.script(agent, (s) => s.otherwise().reply('Thanks, how can I help?'))

      await widget.embed()
      await widget.openToEmailGate()
      await widget.giveEmail()
      await widget.send('Hello')

      await expect(widget.lastAgentMessage()).toHaveText('Thanks, how can I help?', AI_REPLY)
      expect((await findPerson(adminApi, widget.customer.email)).email).toBe(widget.customer.email)
    })

    test(`an Ask anything agent answers in its panel, with no email asked${when} @widget`, async ({ agent, widget, llm, adminApi }) => {
      await customizeAgent(adminApi, agent.id, { chat_style: 'ASK_ANYTHING' })
      await llm.script(agent, (s) => s.otherwise().reply('We ship worldwide.'))

      await widget.embed()
      await widget.openAskAnything()
      await widget.ask('Do you ship abroad?')

      await expect(widget.lastAnswer()).toHaveText('We ship worldwide.', AI_REPLY)
    })

    test.describe('lead capture', () => {
      test.use({ agentSettings: { leadCapture: true } })

      test(`a visitor with no email asked shares details and becomes a lead${when} @widget @leads`, async ({ agent, widget, llm, adminApi }) => {
        const { email, name } = widget.customer
        await llm.script(agent, (s) => s
          .when(/@/).captureLead('Thanks! Someone from sales will reach out.', { email, name })
          .otherwise().reply('Happy to help — what is your email?'))

        await widget.embed()
        await widget.open()
        await widget.send('I want a demo')
        await expect(widget.lastAgentMessage()).toHaveText('Happy to help — what is your email?', AI_REPLY)
        await widget.send(`I am ${name}, ${email}`)
        await expect(widget.lastAgentMessage()).toHaveText('Thanks! Someone from sales will reach out.', AI_REPLY)

        expect((await findPerson(adminApi, email)).lead_stage).toBe('lead')
      })
    })
  })
}
