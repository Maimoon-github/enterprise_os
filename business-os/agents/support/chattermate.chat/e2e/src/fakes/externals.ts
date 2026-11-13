import { expect, type APIRequestContext } from '@playwright/test'
import type { Fault, RecordedCall } from '../../services/fake-externals/server'
import { env } from '../env'
import { unique } from '../support/ids'
import { AI_REPLY } from '../support/timeouts'

export type { RecordedCall }

export interface CallFilter {
  /** Only calls whose path or body contains this — e.g. a customer id or the account's phone number id. */
  contains?: string
  /** Only calls recorded at or after this moment. */
  since?: Date
}

/** Test-side client for services/fake-externals: what the backend sent to third parties. */
export class FakeExternals {
  private readonly request: APIRequestContext

  constructor(request: APIRequestContext) {
    this.request = request
  }

  /** Recorded calls to `provider` (optionally one `action`), oldest first. Filtering happens in the fake. */
  async calls(provider: string, action?: string, { contains, since }: CallFilter = {}): Promise<RecordedCall[]> {
    const params: Record<string, string> = { provider }
    if (action) params.action = action
    if (contains) params.contains = contains
    if (since) params.since = since.toISOString()
    const response = await this.request.get(`${env.fakeExternalsUrl}/__calls`, { params })
    return (await response.json()) as RecordedCall[]
  }

  /** Every call to any provider since `since` — failure diagnostics. */
  async callsSince(since: Date): Promise<RecordedCall[]> {
    const response = await this.request.get(`${env.fakeExternalsUrl}/__calls`, { params: { since: since.toISOString() } })
    return (await response.json()) as RecordedCall[]
  }

  /** Waits for the first call matching `match` and returns its body. */
  async waitForCall<T = Record<string, unknown>>(
    provider: string,
    action: string,
    match: (body: T) => boolean = () => true,
  ): Promise<T> {
    let found: T | undefined
    await expect.poll(async () => {
      found = (await this.calls(provider, action)).map((c) => c.body as T).find(match)
      return found !== undefined
    }, { message: `a ${provider} ${action} call`, ...AI_REPLY }).toBe(true)
    return found!
  }

  /**
   * Makes matching calls fail the way the provider would (e.g. WhatsApp's 24-hour
   * window error) until the returned function is called. Scope it with `contains`
   * so parallel tests are untouched.
   */
  async fail(fault: Fault): Promise<() => Promise<void>> {
    return this.script(fault)
  }

  /**
   * Answers matching calls with exactly this — for a provider the fake has no
   * built-in answers for (e.g. one only a private suite uses). Same scoping rules.
   */
  async respond(answer: Fault): Promise<() => Promise<void>> {
    return this.script(answer)
  }

  private async script(fault: Fault): Promise<() => Promise<void>> {
    const id = unique('fault')
    const response = await this.request.put(`${env.fakeExternalsUrl}/__faults/${id}`, { data: fault })
    if (!response.ok()) throw new Error(`fake-externals rejected the fault: ${await response.text()}`)
    return async () => {
      await this.request.delete(`${env.fakeExternalsUrl}/__faults/${id}`)
    }
  }
}
