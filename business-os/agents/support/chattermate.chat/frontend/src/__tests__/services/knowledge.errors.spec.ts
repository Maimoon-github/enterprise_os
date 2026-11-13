import { describe, it, expect, vi } from 'vitest'

vi.mock('@/services/api', () => ({ default: { post: vi.fn() } }))

import api from '@/services/api'
import { knowledgeService } from '@/services/knowledge'

describe('knowledgeService errors', () => {
  it('a URL the server refuses reads as a sentence, not [object Object]', async () => {
    vi.mocked(api.post).mockRejectedValue({
      response: { status: 422, data: { detail: [{ loc: ['body', 'websites'], msg: 'Value error, URL must contain a valid domain with TLD' }] } },
    })
    await expect(knowledgeService.addUrls('org-1', ['https://localhost'])).rejects.toThrow('URL must contain a valid domain with TLD')
  })
})
