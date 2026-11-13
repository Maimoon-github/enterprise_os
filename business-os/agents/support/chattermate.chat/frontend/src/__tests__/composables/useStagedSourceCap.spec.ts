import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

const planLimits = vi.fn()
vi.mock('@/utils/storage', () => ({
  subscriptionStorage: { getPlanLimits: () => planLimits() }
}))

import { useStagedSourceCap } from '@/composables/useStagedSourceCap'

const file = (name: string) => new File(['x'], name, { type: 'application/pdf' })

const setup = (cap: number, indexed: number, urls: string[], files: File[]) => {
  planLimits.mockReturnValue({ maxKnowledgeSources: cap })
  const u = ref(urls)
  const f = ref(files)
  return { u, f, ...useStagedSourceCap(ref(indexed), u, f) }
}

describe('useStagedSourceCap', () => {
  beforeEach(() => planLimits.mockReset())

  it('does nothing when the plan sets no cap', () => {
    const { u, f, fitToCap } = setup(0, 3, ['a', 'b'], [file('x.pdf')])
    expect(fitToCap('urls')).toBeNull()
    expect(u.value).toEqual(['a', 'b'])
    expect(f.value).toHaveLength(1)
  })

  it('drops staged files before older URLs, oldest first', () => {
    const { u, f, fitToCap } = setup(2, 0, ['a', 'b'], [file('x.pdf')])
    expect(fitToCap('urls')).toBeNull()
    expect(f.value).toEqual([])
    expect(u.value).toEqual(['a', 'b'])
  })

  it('drops the oldest URL when only URLs are staged', () => {
    const { u, fitToCap } = setup(2, 0, ['a', 'b', 'c'], [])
    expect(fitToCap('urls')).toBeNull()
    expect(u.value).toEqual(['b', 'c'])
  })

  it('unstages new files that cannot fit and says how many can', () => {
    const { u, f, fitToCap } = setup(3, 1, ['a'], [file('x.pdf'), file('y.pdf'), file('z.pdf')])
    expect(fitToCap('files', 3)).toBe('Your plan includes 3 knowledge sources. Pick up to 2.')
    expect(f.value).toEqual([])
    expect(u.value).toEqual(['a'])
  })

  it('reports a cap already filled by indexed sources', () => {
    const { u, fitToCap } = setup(1, 1, ['a'], [])
    expect(fitToCap('urls')).toBe("Your plan includes 1 knowledge source, and it's already in use.")
    expect(u.value).toEqual([])
  })
})
