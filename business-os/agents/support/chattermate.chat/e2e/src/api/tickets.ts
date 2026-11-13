import type { ApiClient } from './client'

/**
 * New tickets are queued for the AI investigator by default; the e2e stack runs no
 * worker, so setup turns that off and tickets stay exactly as the test made them.
 */
export async function disableAutoInvestigation(api: ApiClient): Promise<void> {
  await api.put('/tickets/settings', { data: { auto_investigate_on_create: false } })
}
