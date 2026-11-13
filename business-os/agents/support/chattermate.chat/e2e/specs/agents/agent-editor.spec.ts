import { test, expect, scenarioMarker, unique, AI_REPLY } from '@e2e'

test.describe('agent editor', () => {
  test('an agent created and edited in the dashboard answers with its new instructions @agents', async ({ makeAgent, agentsPage, makeWidget, llm }) => {
    // With at least one agent, /ai-agents shows the list rather than onboarding.
    await makeAgent()
    const scenarioId = unique('scn')
    const name = `UI Agent ${scenarioId}`

    await agentsPage.goto()
    const agentId = await agentsPage.createAgent(name)
    await agentsPage.openAgent(agentId)
    await agentsPage.setInstructions(`Always sign off as the Acme team. ${scenarioMarker(scenarioId)}`)

    await llm.script({ name, scenarioId }, (s) => s.otherwise().reply('Hello from the Acme team!'))
    const widget = await makeWidget(agentId)
    await widget.embed()
    await widget.open()
    await widget.send('Hi there')

    await expect(widget.lastAgentMessage()).toHaveText('Hello from the Acme team!', AI_REPLY)
    const prompts = (await llm.requests({ name, scenarioId })).map((request) => request.system)
    expect(prompts.join('\n')).toContain('Always sign off as the Acme team.')
  })
})
