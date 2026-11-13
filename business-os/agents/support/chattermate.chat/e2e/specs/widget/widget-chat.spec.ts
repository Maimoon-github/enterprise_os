import { test, expect, AI_REPLY } from '@e2e'

test.describe('widget chat', () => {
  test('a customer gets the agent\'s answer @smoke @widget', async ({ agent, widget, llm }) => {
    await llm.script(agent, (s) => s
      .when(/opening hours/i).reply('We are open 9am to 5pm, Monday to Friday.')
      .otherwise().reply('Happy to help!'))

    await widget.embed()
    await widget.open()
    await widget.send('What are your opening hours?')

    await expect(widget.lastAgentMessage()).toHaveText('We are open 9am to 5pm, Monday to Friday.', AI_REPLY)
  })

  test('the conversation is still there after the customer reloads the page @widget', async ({ agent, widget, llm }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Your order ships tomorrow.'))

    await widget.embed()
    await widget.open()
    await widget.send('Where is my order?')
    await expect(widget.lastAgentMessage()).toHaveText('Your order ships tomorrow.', AI_REPLY)

    await widget.page.reload()
    await widget.open()
    await expect(widget.customerMessages.last()).toHaveText('Where is my order?')
    await expect(widget.lastAgentMessage()).toHaveText('Your order ships tomorrow.', AI_REPLY)
  })

  test('a visitor whose first authorization went missing can still chat @widget', async ({ agent, widget, llm }) => {
    await llm.script(agent, (s) => s.otherwise().reply('Happy to help!'))

    // The socket refuses the anonymous token; the widget authorizes again and connects.
    await widget.loseFirstAuthorization()
    await widget.embed()
    await widget.open()
    await widget.send('Hello?')

    await expect(widget.lastAgentMessage()).toHaveText('Happy to help!', AI_REPLY)
  })
})
