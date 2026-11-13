import { env, seedOrg } from '../env'
import type { ApiClient } from './client'

/**
 * Points the org's AI at the fake LLM. The backend live-tests the key on save, so
 * the fake must already be running (playwright.config.ts starts it).
 */
export async function useFakeLlm(api: ApiClient): Promise<void> {
  await api.post('/ai/setup', {
    data: {
      model_type: 'OPENAI_COMPATIBLE',
      model_name: seedOrg.llmModel,
      api_key: 'e2e-fake-key',
      base_url: `${env.fakeLlmUrl}/v1`,
    },
  })
}

export interface AiConfig {
  model_type: string
  model_name: string
}

export async function currentAiConfig(api: ApiClient): Promise<AiConfig> {
  return api.get<AiConfig>('/ai/config')
}

/**
 * Puts the org back on the AI it had before a test changed it: the fake LLM, or
 * (enterprise) the ChatterMate AI its signup created, which reaches the fake too.
 */
export async function restoreAi(api: ApiClient, before: AiConfig): Promise<void> {
  if (before.model_type.toUpperCase() === 'CHATTERMATE') {
    // As the dashboard's onboarding sends it: the backend injects the key.
    await api.post('/ai/setup', { data: { model_type: 'CHATTERMATE', model_name: 'chattermate', api_key: '' } })
  } else {
    await useFakeLlm(api)
  }
}
