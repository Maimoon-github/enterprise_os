import type { APIRequestContext } from '@playwright/test'
import { env } from '../env'

// The dashboard's live-chat (/agent) socket, driven at the protocol level the
// way another site's page would reach it: with the browser's sign-in cookies
// and an Origin of the page's choosing (or none).

const SOCKET = `${env.backendUrl}/socket.io/?EIO=4`

export type SocketOutcome = 'signed in' | 'refused'

/** The sign-in cookies a browser would attach, as a Cookie header. */
export async function signInCookies(request: APIRequestContext, email: string, password: string): Promise<string> {
  const response = await request.post(`${env.apiUrl}/users/login`, { form: { username: email, password } })
  if (!response.ok()) throw new Error(`login ${email} → ${response.status()}`)
  const { cookies } = await request.storageState()
  return cookies.filter((c) => ['access_token', 'refresh_token'].includes(c.name)).map((c) => `${c.name}=${c.value}`).join('; ')
}

/**
 * Open /agent over a WebSocket, as the dashboard does. Only the namespace's own
 * answer counts: a handshake refused before it (the origin not allowed at all)
 * rejects rather than passing as a refusal.
 */
export function agentSocketOverWebSocket(origin: string, cookie: string): Promise<SocketOutcome> {
  return new Promise((resolve, reject) => {
    // Node's WebSocket takes headers, which a page can't set but a browser sends for it
    const ws = new WebSocket(`${SOCKET.replace(/^http/, 'ws')}&transport=websocket`, { headers: { Origin: origin, Cookie: cookie } } as never)
    const fail = (why: string) => { clearTimeout(timer); ws.close(); reject(new Error(`${origin}: ${why}`)) }
    const timer = setTimeout(() => fail('no answer to the namespace connect'), 10_000)
    ws.onmessage = ({ data }) => {
      const packet = String(data)
      if (packet.startsWith('0')) ws.send('40/agent,')
      else if (packet.startsWith('40/agent')) settle('signed in')
      else if (packet.startsWith('44/agent')) settle('refused')
    }
    ws.onerror = () => fail('the socket handshake was refused before the namespace answered')
    function settle(outcome: SocketOutcome) { clearTimeout(timer); ws.onerror = null; ws.close(); resolve(outcome) }
  })
}

/**
 * Open /agent over polling: the handshake with `handshake` headers and `query`
 * (a <script> tag sends `j=0`, the cookies and no Origin), then the namespace
 * connect and the read from `pageOrigin`. socket.io signs the namespace in with
 * the handshake's headers, which is what this exercises.
 */
export async function agentSocketOverPolling(
  request: APIRequestContext, cookie: string, pageOrigin: string, handshake: Record<string, string>, query = '',
): Promise<SocketOutcome> {
  const opened = await (await request.get(`${SOCKET}&transport=polling${query}`, { headers: { Cookie: cookie, ...handshake } })).text()
  const sid = opened.match(/sid\\?":\\?"([^"\\]+)/)?.[1]
  if (!sid) throw new Error(`the handshake answered ${opened.slice(0, 80)}`)
  const session = `${SOCKET}&transport=polling&sid=${sid}`
  await request.post(session, { headers: { Origin: pageOrigin, 'Content-Type': 'text/plain' }, data: '40/agent,' })
  const answer = await (await request.get(session, { headers: { Origin: pageOrigin } })).text()
  return answer.includes('40/agent,{"sid"') ? 'signed in' : 'refused'
}
