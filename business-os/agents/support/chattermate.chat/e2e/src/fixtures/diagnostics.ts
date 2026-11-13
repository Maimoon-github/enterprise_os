import { existsSync, openSync, readSync, closeSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import type { TestInfo } from '@playwright/test'
import { FakeExternals } from '../fakes/externals'
import type { FakeLlm } from '../fakes/llm'

/** Where scripts/stack.sh writes each service's output (absent when Playwright started the services). */
const BACKEND_LOG = fileURLToPath(new URL('../../.stack/backend.log', import.meta.url))
const MAX_LOG_BYTES = 200_000

function logSize(): number {
  return existsSync(BACKEND_LOG) ? statSync(BACKEND_LOG).size : 0
}

function logSince(offset: number): string {
  if (!existsSync(BACKEND_LOG)) return ''
  const end = statSync(BACKEND_LOG).size
  const start = Math.max(offset, end - MAX_LOG_BYTES)
  if (end <= start) return ''
  const buffer = Buffer.alloc(end - start)
  const fd = openSync(BACKEND_LOG, 'r')
  try {
    readSync(fd, buffer, 0, buffer.length, start)
  } finally {
    closeSync(fd)
  }
  return buffer.toString('utf8')
}

/** Marks where a test starts, so a failure can attach only what happened during it. */
export function startDiagnostics(): { since: Date; logOffset: number } {
  return { since: new Date(), logOffset: logSize() }
}

/**
 * On failure, attaches what the backend did while the test ran: its log, the
 * model requests for every agent the test scripted, and every third-party call
 * (other parallel tests' calls included — they are timestamped). Passing tests
 * attach nothing.
 */
export async function attachDiagnostics(
  testInfo: TestInfo,
  start: { since: Date; logOffset: number },
  llm: FakeLlm,
  externals: FakeExternals,
): Promise<void> {
  if (testInfo.status === testInfo.expectedStatus) return
  const json = (value: unknown) => JSON.stringify(value, null, 2)

  const log = logSince(start.logOffset)
  if (log) await testInfo.attach('backend.log', { body: log, contentType: 'text/plain' })

  for (const agent of llm.scripted) {
    const requests = await llm.requests(agent).catch((e: unknown) => [`unavailable: ${e}`])
    await testInfo.attach(`llm-requests-${agent.scenarioId}.json`, { body: json(requests), contentType: 'application/json' })
  }

  const calls = await externals.callsSince(start.since).catch(() => [])
  if (calls.length) await testInfo.attach('third-party-calls.json', { body: json(calls), contentType: 'application/json' })
}
