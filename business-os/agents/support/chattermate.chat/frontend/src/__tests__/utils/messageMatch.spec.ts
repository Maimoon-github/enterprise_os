/*
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Message } from '@/types/chat'
import { findMessage, newClientId } from '@/utils/messageMatch'

const msg = (fields: Partial<Message>): Message => ({
  message_type: 'agent', created_at: '2026-10-11T00:00:00Z', session_id: 's1', ...fields
})

describe('findMessage', () => {
  it('matches by row id, client id or channel id', () => {
    const loaded = msg({ id: 10 })
    const pending = msg({ client_id: 'c-1' })
    const wa = msg({ id: 11, external_message_id: 'wamid.X' })
    const messages = [loaded, pending, wa]

    expect(findMessage(messages, { messageId: 10 })).toBe(loaded)
    expect(findMessage(messages, { clientId: 'c-1' })).toBe(pending)
    expect(findMessage(messages, { externalId: 'wamid.X' })).toBe(wa)
  })

  it('never guesses: an unknown receipt matches nothing', () => {
    // A failed message (no id yet) and a newer pending one: a receipt for
    // some other row must not land on either.
    const failed = msg({ client_id: 'c-1', attributes: { delivery_status: 'failed' } })
    const pending = msg({ client_id: 'c-2' })

    expect(findMessage([failed, pending], { messageId: 99, externalId: 'wamid.OTHER' })).toBeUndefined()
  })

  it('ignores empty references', () => {
    expect(findMessage([msg({})], {})).toBeUndefined()
    expect(findMessage([msg({})], { clientId: '', externalId: null })).toBeUndefined()
  })
})

describe('newClientId', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('uses randomUUID where the browser has it', () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'uuid-1' })
    expect(newClientId()).toBe('uuid-1')
  })

  it('still works on plain http, where randomUUID does not exist', () => {
    vi.stubGlobal('crypto', {})
    const a = newClientId()
    const b = newClientId()
    expect(a).toMatch(/^[a-z0-9]+-[a-z0-9]+$/)
    expect(a).not.toBe(b)
  })
})
