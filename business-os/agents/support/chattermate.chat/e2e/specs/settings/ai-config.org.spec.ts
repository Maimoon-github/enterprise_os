import { test, expect, env, seedOrg, currentAiConfig, restoreAi, AI_REPLY, type AiConfig } from '@e2e'

// Changes the org's AI provider, so it runs in the serial `org` project, and puts
// it back afterwards so later specs (and later local runs) see the usual AI.

const fakeModel = { baseUrl: `${env.fakeLlmUrl}/v1`, model: seedOrg.llmModel }
const INVALID_KEY_MESSAGE = 'The provided API key is invalid or does not have access to the selected model.'

test.describe('AI configuration', () => {
  let before: AiConfig

  test.beforeEach(async ({ adminApi }) => { before = await currentAiConfig(adminApi) })

  test.afterEach(async ({ adminApi }) => { await restoreAi(adminApi, before) })

  test('a key the provider rejects is reported and the agents keep working @settings', async ({ aiConfigPage, agent, widget, llm }) => {
    await aiConfigPage.goto()
    await aiConfigPage.useOpenAiCompatible({ ...fakeModel, apiKey: 'e2e-invalid-key' })
    await expect(aiConfigPage.error).toHaveText(INVALID_KEY_MESSAGE)

    // The rejected key was not saved: a customer still gets answers, through the old key.
    await llm.script(agent, (s) => s.otherwise().reply('Still here to help.'))
    await widget.embed()
    await widget.open()
    await widget.send('Hello?')
    await expect(widget.lastAgentMessage()).toHaveText('Still here to help.', AI_REPLY)
    expect((await llm.requests(agent)).map((r) => r.keySuffix)).not.toContain('id-key')
  })

  test('a working key is saved and is the one the agents use @settings', async ({ aiConfigPage, agent, widget, llm }) => {
    await aiConfigPage.goto()
    await aiConfigPage.useOpenAiCompatible({ ...fakeModel, apiKey: 'e2e-fake-key-rotated' })
    await expect(aiConfigPage.error).toBeHidden()

    await aiConfigPage.goto()
    await expect(aiConfigPage.page.getByLabel('Base URL')).toHaveValue(fakeModel.baseUrl)

    await llm.script(agent, (s) => s.otherwise().reply('Answered with the new key.'))
    await widget.embed()
    await widget.open()
    await widget.send('Hello?')
    await expect(widget.lastAgentMessage()).toHaveText('Answered with the new key.', AI_REPLY)
    const lastRequest = (await llm.requests(agent)).at(-1)
    expect(lastRequest?.keySuffix).toBe('otated')
    expect(lastRequest?.model).toBe(fakeModel.model)
  })
})
