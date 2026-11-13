import { createHmac } from 'node:crypto'
import { env } from '../env'
import type { ApiClient } from './client'

/** A widget app is a customer's server: its API key mints conversation tokens. */
export async function createWidgetApp(api: ApiClient, name: string): Promise<{ apiKey: string }> {
  const app = await api.post<{ api_key: string }>('/widget-apps', { data: { name } })
  return { apiKey: app.api_key }
}

/** What the customer's server does for a signed-in visitor before rendering the widget. */
export async function issueConversationToken(
  api: ApiClient,
  apiKey: string,
  widgetId: string,
  customer: { email: string; name: string },
  /** How long the token lives; the backend's minimum is 60 seconds. */
  ttlSeconds?: number,
): Promise<string> {
  const body = await api.withToken(apiKey).post<{ data: { token: string } }>('/generate-token', {
    data: { widget_id: widgetId, customer_email: customer.email, customer_name: customer.name, ttl_seconds: ttlSeconds },
  })
  return body.data.token
}

/** What the customer's server does when a visitor signs out: the token stops working at once. */
export async function revokeConversationToken(api: ApiClient, apiKey: string, token: string): Promise<void> {
  await api.withToken(apiKey).post('/revoke-token', { data: { token, reason: 'Visitor signed out' } })
}

/**
 * The same visitor's token as if the widget issued it long ago: it runs out in
 * `secondsLeft`, and like a real anonymous token it carries no `iat`, so nothing
 * rotates it first. Signed with the stack's secret, as the backend would.
 */
export function tokenRunningOut(token: string, secondsLeft: number): string {
  const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString('base64url')
  const claims = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8'))
  delete claims.iat
  const unsigned = `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode({ ...claims, exp: Math.floor(Date.now() / 1000) + secondsLeft })}`
  return `${unsigned}.${createHmac('sha256', env.conversationTokenSecret).update(unsigned).digest('base64url')}`
}

/** When a conversation token stops working (its `exp`), as the backend's clock reads it. */
export function conversationTokenExpiry(token: string): Date {
  const claims = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8')) as { exp: number }
  return new Date(claims.exp * 1000)
}
