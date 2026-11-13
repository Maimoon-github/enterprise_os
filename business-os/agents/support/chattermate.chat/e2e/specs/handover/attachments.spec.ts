import { test, expect, env, unique, AI_REPLY } from '@e2e'

test.describe('attachments', () => {
  test.use({ agentSettings: { transferToHuman: true, allowAttachments: true } })

  test('a customer sends a file to the teammate, who can open it — and only through a signed link @handover', async ({ agent, widget, inbox, llm, request }) => {
    await llm.script(agent, (s) => s.otherwise().handOver('Let me connect you with a teammate.'))
    await widget.embed()
    await widget.open()
    await widget.send('I need a person')
    await widget.shareContactDetails()
    await inbox.goto()
    await inbox.openConversationWith(widget.customer.name)
    await inbox.takeOver()
    await inbox.reply('Please send me the receipt.')
    await expect(widget.lastAgentMessage()).toHaveText('Please send me the receipt.', AI_REPLY)

    const content = `Receipt ${unique('R')} — total 42.00`
    await widget.sendFile({ name: 'receipt.txt', mimeType: 'text/plain', content }, 'Here it is')

    const link = inbox.attachment('receipt.txt')
    await expect(link).toBeVisible(AI_REPLY)
    const href = await link.getAttribute('href')
    expect((await (await inbox.page.request.get(href!)).text())).toBe(content)

    // The stored file is not reachable without the signature.
    const unsigned = new URL(href!, 'http://x').pathname
    expect((await request.get(`${env.backendUrl}${unsigned}`)).status()).toBe(403)
  })
})
