#!/usr/bin/env node
// A burst of real widget visitors, all loading the page at once (bootstrap,
// authorize, socket connect, chat history), while a probe times the API. Every
// visitor must get in and the API must keep answering: a database checkout that
// waits on the event loop froze the whole backend under this for minutes.
//
// OSS edition, on a fresh database (it runs the first-run setup):
//
//   scripts/stack.sh reset && node scripts/widget-burst.mjs [visitors=150]
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const require = createRequire(fileURLToPath(new URL('../../frontend/package.json', import.meta.url)))
const { io } = require('socket.io-client')

const BACKEND = 'http://127.0.0.1:18000'
const API = `${BACKEND}/api/v1`
const SITE = 'http://127.0.0.1:13000' // the customer page the widget is on
const FAKE_LLM = 'http://127.0.0.1:14010/v1'
const VISITORS = Number(process.argv[2] || 150)
const SOCKET_TIMEOUT_MS = 60_000
const PROBE_EVERY_MS = 100
// The API answering slower than this during the burst counts as a stall
const STALL_MS = 5_000

async function call(method, path, { body, token, ip } = {}) {
  const headers = { 'content-type': 'application/json', origin: SITE }
  if (token) headers.authorization = `Bearer ${token}`
  if (ip) headers['x-forwarded-for'] = ip // one visitor per address, as nginx reports them
  const response = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined })
  const text = await response.text()
  if (!response.ok) throw new Error(`${method} ${path.replace(/[0-9a-f-]{36}/g, ':id')} → ${response.status}`)
  return text ? JSON.parse(text) : null
}

async function setUpWidget() {
  const { access_token: admin } = await call('POST', '/organizations', { body: {
    name: 'Burst Org', domain: 'burst.example', timezone: 'UTC',
    admin_email: 'admin@burst.example', admin_name: 'Burst Admin', admin_password: 'Burst-Passw0rd!x',
  } })
  await call('POST', '/ai/setup', { token: admin, body: {
    model_type: 'OPENAI_COMPATIBLE', model_name: 'e2e-fake', api_key: 'e2e-fake-key', base_url: FAKE_LLM,
  } })
  const agent = await call('POST', '/agent', { token: admin, body: {
    name: 'Burst Agent', agent_type: 'customer_support', instructions: ['Be brief.'],
  } })
  return (await call('POST', '/widgets', { token: admin, body: { name: 'Burst Widget', agent_id: agent.id } })).id
}

/** One visitor's page load; resolves with what went wrong, or null. */
async function visit(widgetId, i) {
  const ip = `10.9.${Math.floor(i / 250)}.${(i % 250) + 1}`
  let token
  try {
    const boot = await call('POST', `/widgets/${widgetId}/bootstrap`, { body: { host_origin: SITE }, ip })
    token = (await call('GET', `/widgets/${widgetId}`, { token: boot.initialToken, ip })).token ?? boot.initialToken
  } catch (error) {
    return error.message
  }
  return new Promise(resolve => {
    // The framed widget connects from the frame's own origin: the API's here
    const socket = io(`${BACKEND}/widget`, {
      transports: ['websocket'], reconnection: false,
      auth: { conversation_token: token, page_url: `${SITE}/` }, extraHeaders: { origin: BACKEND },
    })
    const finish = problem => { clearTimeout(timer); socket.close(); resolve(problem) }
    const timer = setTimeout(() => finish('socket timed out'), SOCKET_TIMEOUT_MS)
    socket.on('connect', () => socket.emit('get_chat_history'))
    socket.on('chat_history', () => finish(null))
    socket.on('connect_error', error => finish(`socket refused: ${error?.data?.type || error?.message}`))
    socket.on('error', error => finish(`socket error: ${error?.type || 'unknown'}`))
  })
}

/** Times /health and a widget read every PROBE_EVERY_MS until stopped. */
function startProbe(widgetId) {
  const probe = { worstMs: 0, failures: 0, running: true }
  probe.done = (async () => {
    while (probe.running) {
      const started = Date.now()
      try {
        const answers = await Promise.all([fetch(`${BACKEND}/health`), fetch(`${API}/widgets/${widgetId}/frame`)])
        if (answers.some(answer => answer.status >= 500)) probe.failures++
        await Promise.all(answers.map(answer => answer.text()))
      } catch {
        probe.failures++
      }
      probe.worstMs = Math.max(probe.worstMs, Date.now() - started)
      await new Promise(resolve => setTimeout(resolve, PROBE_EVERY_MS))
    }
  })()
  return probe
}

const widgetId = await setUpWidget()
const probe = startProbe(widgetId)
const started = Date.now()
const problems = (await Promise.all(Array.from({ length: VISITORS }, (_, i) => visit(widgetId, i)))).filter(Boolean)
const seconds = (Date.now() - started) / 1000
probe.running = false
await probe.done

const counts = problems.reduce((all, problem) => ({ ...all, [problem]: (all[problem] ?? 0) + 1 }), {})
console.log(`${VISITORS - problems.length}/${VISITORS} visitors in ${seconds.toFixed(1)}s; ` +
  `API worst ${probe.worstMs}ms, ${probe.failures} probe failures`)
for (const [problem, count] of Object.entries(counts)) console.log(`  ${count} × ${problem}`)
process.exit(problems.length || probe.failures || probe.worstMs > STALL_MS ? 1 : 0)
