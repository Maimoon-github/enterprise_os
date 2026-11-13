import type { ApiClient } from './client'

interface TokenResponse {
  access_token: string
  user: { id: string; organization_id: string }
}

export interface Session {
  token: string
  userId: string
  organizationId: string
}

/** A client signed in as `email` that signs in again whenever its token expires. */
export async function signedInClient(api: ApiClient, email: string, password: string): Promise<{ api: ApiClient; session: Session }> {
  const session = await login(api, email, password)
  const renew = async () => (await login(api, email, password)).token
  return { api: api.withToken(session.token, renew), session }
}

/** Logs in through the real endpoint; the token is for seeding calls. */
export async function login(api: ApiClient, email: string, password: string): Promise<Session> {
  const body = await api.post<TokenResponse>('/users/login', { form: { username: email, password } })
  return { token: body.access_token, userId: String(body.user.id), organizationId: String(body.user.organization_id) }
}
