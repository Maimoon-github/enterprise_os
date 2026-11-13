import { expect } from '@playwright/test'

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Asserts that `read()` keeps returning what it returns now, for `ms`. For the
 * "and nothing else happens" half of a journey — the AI staying quiet after a
 * takeover, a rejected webhook producing no reply — which no single check proves.
 * Call it after a positive signal that the backend has handled the event.
 */
export async function expectUnchanged<T>(what: string, read: () => Promise<T>, ms = 3_000): Promise<void> {
  const initial = await read()
  const until = Date.now() + ms
  while (Date.now() < until) {
    await sleep(250)
    expect(await read() as unknown, `${what} changed`).toEqual(initial)
  }
}
