import { test, expect, expectUnchanged, AI_REPLY } from '@e2e'

test.describe('human handover', () => {
  test.use({ agentSettings: { transferToHuman: true } })

  test('a customer asks for a person, the teammate\'s reply reaches them, and the AI stays out of it @smoke @handover', async ({ agent, widget, inbox, llm }) => {
    await llm.script(agent, (s) => s
      .when(/human|person/i).handOver('Let me connect you with a teammate.')
      .otherwise().reply('Happy to help!'))

    await widget.embed()
    await widget.open()
    await widget.send('I want to talk to a human')
    await widget.shareContactDetails()

    await inbox.goto()
    await inbox.openConversationWith(widget.customer.name)
    await inbox.takeOver()
    await inbox.reply('Hi, this is Sam. How can I help?')
    await expect(widget.lastAgentMessage()).toHaveText('Hi, this is Sam. How can I help?', AI_REPLY)

    const modelCalls = (await llm.requests(agent)).length
    await widget.send('My parcel never arrived')
    await expect(inbox.lastCustomerMessage()).toContainText('My parcel never arrived')
    // A person owns the chat now: the model is not asked, and no bot answer appears.
    await expectUnchanged('model calls after takeover', async () => (await llm.requests(agent)).length)
    expect((await llm.requests(agent))).toHaveLength(modelCalls)
    await expect(widget.lastAgentMessage()).toHaveText('Hi, this is Sam. How can I help?')
  })
})
