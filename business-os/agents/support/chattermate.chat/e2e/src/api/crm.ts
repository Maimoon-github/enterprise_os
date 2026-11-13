import type { ApiClient } from './client'

export type CrmProvider = 'hubspot' | 'pipedrive'

/**
 * CRMs connect through OAuth only: /install hands out a state, the CRM sends the
 * browser back to /callback with a code, and the backend trades it for tokens.
 * One connection per org and CRM — an org-wide change (`*.org.spec.ts`).
 */
export async function connectCrm(api: ApiClient, provider: CrmProvider, code: string): Promise<void> {
  const install = await api.raw('GET', `/crm/${provider}/install`, { maxRedirects: 0 })
  const state = new URL(install.headers().location ?? 'about:blank').searchParams.get('state')
  if (!state) throw new Error(`${provider} install → ${install.status()}: ${await install.text()}`)
  const callback = await api.raw('GET', `/crm/${provider}/callback`, { params: { code, state }, maxRedirects: 0 })
  const location = callback.headers().location ?? ''
  if (!location.includes('status=success')) throw new Error(`${provider} callback → ${location || callback.status()}`)
}

export async function disconnectCrm(api: ApiClient, provider: CrmProvider): Promise<void> {
  await api.raw('DELETE', `/crm/${provider}`)
}

/** "Sync now" on a person: pushes them to every connected CRM, synchronously. */
export async function syncPersonToCrm(api: ApiClient, personId: string): Promise<{ synced: Array<{ provider: string }> }> {
  return api.post(`/people/${personId}/crm-sync`)
}
