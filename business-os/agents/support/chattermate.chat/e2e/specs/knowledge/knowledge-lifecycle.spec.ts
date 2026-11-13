import { test, expect, addKnowledgeText, deleteKnowledge, unique, AI_REPLY, type TestAgent, type FakeLlm, type ChatWidget } from '@e2e'

// What the model is shown is what the knowledge base holds for *this* agent, now.

async function askAboutReturns(llm: FakeLlm, agent: TestAgent, widget: ChatWidget): Promise<string> {
  await llm.script(agent, (s) => s
    .when(/return/i).callTool('search_knowledge_base', { query: 'returns policy' })
    .thenReply('Let me check our policy.')
    .otherwise().reply('Happy to help!'))
  await widget.embed()
  await widget.open()
  await widget.send('What is your returns policy?')
  await expect(widget.lastAgentMessage()).toHaveText('Let me check our policy.', AI_REPLY)
  return (await llm.requests(agent)).flatMap((r) => r.toolResults).join('\n')
}

test.describe('knowledge base lifecycle', () => {
  test('deleted knowledge is no longer what the AI is shown @knowledge', async ({ agent, widget, llm, adminApi, org, makeWidget }) => {
    const code = unique('RET')
    const id = await addKnowledgeText(adminApi, {
      orgId: org.orgId, agentId: agent.id, title: `Returns policy ${code}`,
      content: `Returns policy: items can be returned within 45 days. Reference ${code}.`,
    })
    expect(await askAboutReturns(llm, agent, widget)).toContain(code)

    await deleteKnowledge(adminApi, id)
    const freshVisitor = await makeWidget(agent.id)
    expect(await askAboutReturns(llm, agent, freshVisitor)).not.toContain(code)
  })

  test('one agent\'s knowledge never reaches another agent\'s answers @knowledge', async ({ agent, widget, llm, adminApi, org, makeAgent }) => {
    const other = await makeAgent()
    const secret = unique('INTERNAL')
    await addKnowledgeText(adminApi, {
      orgId: org.orgId, agentId: other.id, title: `Staff returns rules ${secret}`,
      content: `Staff-only returns rules: discount code ${secret} for internal returns.`,
    })
    // `agent` searches the same org's knowledge base, for the same words.
    expect(await askAboutReturns(llm, agent, widget)).not.toContain(secret)
  })
})
