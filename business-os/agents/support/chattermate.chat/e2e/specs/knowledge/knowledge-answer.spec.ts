import { test, expect, addKnowledgeText, unique, AI_REPLY } from '@e2e'

test.describe('knowledge base', () => {
  test('an answer is grounded in text added to the knowledge base @smoke @knowledge', async ({ agent, widget, llm, adminApi, org }) => {
    // A token no model could guess, so finding it in the search result proves the
    // text was indexed and retrieved — not echoed from the prompt.
    const policyCode = unique('RET')
    await addKnowledgeText(adminApi, {
      orgId: org.orgId,
      agentId: agent.id,
      title: `Returns policy ${policyCode}`, // titles are unique per org
      content: `Returns policy: items can be returned within 45 days of delivery. Quote reference ${policyCode} on the return label.`,
    })
    await llm.script(agent, (s) => s
      .when(/return/i).callTool('search_knowledge_base', { query: 'returns policy' })
      .thenReply('You can return items within 45 days of delivery.')
      .otherwise().reply('Happy to help!'))

    await widget.embed()
    await widget.open()
    await widget.send('What is your returns policy?')

    await expect(widget.lastAgentMessage()).toHaveText('You can return items within 45 days of delivery.', AI_REPLY)
    const searchResults = (await llm.requests(agent)).flatMap((request) => request.toolResults)
    expect(searchResults.join('\n')).toContain(policyCode)
  })
})
