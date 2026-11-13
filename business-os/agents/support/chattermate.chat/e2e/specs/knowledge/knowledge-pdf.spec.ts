import { test, expect, runWorkerOnce, textPdf, unique, unfinishedKnowledge, uploadKnowledgePdf, AI_REPLY, KNOWLEDGE_INDEXED } from '@e2e'

test('an uploaded PDF becomes knowledge the AI answers from @knowledge @workers', async ({ agent, widget, llm, adminApi, org }) => {
  const code = unique('WARRANTY')
  await uploadKnowledgePdf(adminApi, {
    orgId: org.orgId, agentId: agent.id, filename: `${code}.pdf`,
    pdf: textPdf(['Warranty policy', `Every product carries a two-year warranty. Reference ${code}.`]),
  })
  // Production indexes it on the knowledge worker's next poll; here, now.
  await runWorkerOnce('knowledge')
  // Tests run in parallel: another test's pass may be the one indexing it.
  await expect.poll(() => unfinishedKnowledge(adminApi, agent.id), KNOWLEDGE_INDEXED).toEqual([])

  await llm.script(agent, (s) => s
    .when(/warranty/i).callTool('search_knowledge_base', { query: 'warranty policy' })
    .thenReply('Every product has a two-year warranty.')
    .otherwise().reply('Happy to help!'))
  await widget.embed()
  await widget.open()
  await widget.send('What warranty do you offer?')

  await expect(widget.lastAgentMessage()).toHaveText('Every product has a two-year warranty.', AI_REPLY)
  expect((await llm.requests(agent)).flatMap((r) => r.toolResults).join('\n')).toContain(code)
})
