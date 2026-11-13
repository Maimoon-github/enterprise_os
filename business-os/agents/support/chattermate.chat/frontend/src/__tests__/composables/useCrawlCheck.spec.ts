import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import type { QueueItem } from '@/types/knowledge'
import { useCrawlCheck } from '@/composables/useCrawlCheck'

const item = (source: string, status: QueueItem['status'], id = 1): QueueItem =>
  ({ id, source, source_type: 'website', status, created_at: '' }) as QueueItem

const setup = (queueAfterFetch: QueueItem[], fetchFails = false) => {
  const queue = ref<QueueItem[]>([])
  const fetch = vi.fn(async () => {
    if (fetchFails) throw new Error('network down')
    queue.value = queueAfterFetch
  })
  return { fetch, ...useCrawlCheck(fetch, queue) }
}

describe('useCrawlCheck', () => {
  it('reports a source that already failed (a domain refused on add)', async () => {
    const { firstFailure } = setup([item('https://x.com', 'failed')])
    expect((await firstFailure(['https://x.com']))?.status).toBe('failed')
  })

  it.each(['pending', 'processing'] as const)('does not wait for a %s crawl', async (status) => {
    const { firstFailure, fetch } = setup([item('https://x.com', status)])
    expect(await firstFailure(['https://x.com'])).toBeNull()
    expect(fetch).toHaveBeenCalledTimes(1) // one look, no polling
  })

  it('a source that already finished is not a failure', async () => {
    const { firstFailure } = setup([]) // completed items drop off the list
    expect(await firstFailure(['https://x.com'])).toBeNull()
  })

  it('judges a retry by its newest row, not an older failure', async () => {
    const { firstFailure } = setup([item('https://x.com', 'pending', 2), item('https://x.com', 'failed', 1)])
    expect(await firstFailure(['https://x.com'])).toBeNull()
  })

  it('matches a source however its slash and case were typed', async () => {
    const { firstFailure } = setup([item('https://X.com/', 'failed')])
    expect(await firstFailure(['https://x.com'])).not.toBeNull()
  })

  it('ignores failures of sources it was not asked about', async () => {
    const { firstFailure } = setup([item('https://other.com', 'failed')])
    expect(await firstFailure(['https://x.com'])).toBeNull()
  })

  it('a cancelled check reports nothing', async () => {
    const { firstFailure, cancel } = setup([item('https://x.com', 'failed')])
    const result = firstFailure(['https://x.com'])
    cancel()
    expect(await result).toBeNull()
  })

  it('a failed queue fetch lets the wizard move on instead of getting stuck', async () => {
    const { firstFailure } = setup([], true)
    vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(await firstFailure(['https://x.com'])).toBeNull()
  })
})
