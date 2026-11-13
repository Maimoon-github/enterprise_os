import { describe, it, expect } from 'vitest'

import { apiErrorMessage } from '@/utils/apiError'

const failed = (data: unknown) => ({ response: { data } })

describe('apiErrorMessage', () => {
  it('uses a plain detail as is', () => {
    expect(apiErrorMessage(failed({ detail: 'Agent not found' }), 'x')).toBe('Agent not found')
  })

  it("reads FastAPI's validation list instead of showing [object Object]", () => {
    const body = { detail: [{ type: 'value_error', loc: ['body', 'websites'], msg: 'Value error, URL must contain a valid domain with TLD', input: ['https://localhost'] }] }
    expect(apiErrorMessage(failed(body), 'x')).toBe('URL must contain a valid domain with TLD')
  })

  it('falls back to message, then to the given text', () => {
    expect(apiErrorMessage(failed({ message: 'Too many requests' }), 'x')).toBe('Too many requests')
    expect(apiErrorMessage(failed({ detail: [{}] }), 'Failed to add URLs')).toBe('Failed to add URLs')
    expect(apiErrorMessage(new Error('Network Error'), 'Failed to add URLs')).toBe('Failed to add URLs')
  })
})
