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

import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import MetaOwnAppWebhook from '../../../components/integrations/MetaOwnAppWebhook.vue'
import type { ChannelAccount } from '../../../services/channels'

vi.mock('vue-sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

const account = (channel_type: 'whatsapp' | 'messenger', webhook_auto_configured?: boolean): ChannelAccount => ({
  id: 'acc-1',
  channel_type,
  external_account_id: 'PN1',
  is_active: true,
  webhook_url: 'https://api.example.com/api/v1/webhooks/meta/acc-1',
  webhook_verify_token: 'tok-123',
  webhook_auto_configured,
})

const text = (a: ChannelAccount) => mount(MetaOwnAppWebhook, { props: { account: a } }).text()

describe('MetaOwnAppWebhook', () => {
  it('shows the callback URL and verify token', () => {
    const inputs = mount(MetaOwnAppWebhook, { props: { account: account('whatsapp', true) } }).findAll('input')
    expect(inputs.map(i => (i.element as HTMLInputElement).value)).toEqual([
      'https://api.example.com/api/v1/webhooks/meta/acc-1', 'tok-123'])
  })

  it('says a WhatsApp number is set up only when Meta took the callback', () => {
    expect(text(account('whatsapp', true))).toContain('Nothing to set up')
    expect(text(account('whatsapp', false))).toContain('WhatsApp → Configuration')
  })

  it('tells Messenger where the values go', () => {
    expect(text(account('messenger'))).toContain('Messenger → Settings → Webhooks')
  })
})
