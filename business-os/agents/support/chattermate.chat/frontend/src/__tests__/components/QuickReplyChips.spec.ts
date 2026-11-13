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

import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import QuickReplyChips from '@/components/conversations/QuickReplyChips.vue'
import MessageTag from '@/components/conversations/MessageTag.vue'

const sent = (asText = false) => ({
  as_text: asText,
  choices: [{ id: 'qr_0', text: 'Today' }, { id: 'qr_1', text: 'Tomorrow' }]
})

describe('QuickReplyChips', () => {
  it('lists the choices that were sent, in order', () => {
    const chips = mount(QuickReplyChips, { props: { sent: sent() } })
    expect(chips.findAll('.quick-reply-chip').map((c) => c.text())).toEqual(['Today', 'Tomorrow'])
    expect(chips.find('.quick-reply-chips').attributes('aria-label')).toBe('Choices offered')
  })

  it('says when the choices went out as a numbered list', () => {
    const chips = mount(QuickReplyChips, { props: { sent: sent(true) } })
    expect(chips.find('.quick-reply-chips').attributes('aria-label')).toContain('numbered list')
  })

  it('renders nothing without a record', () => {
    expect(mount(QuickReplyChips, { props: { sent: null } }).find('.quick-reply-chips').exists()).toBe(false)
    expect(mount(QuickReplyChips, { props: { sent: { choices: [] } } }).find('.quick-reply-chips').exists()).toBe(false)
  })
})

describe('MessageTag', () => {
  it('shows its icon and label', () => {
    const tag = mount(MessageTag, {
      props: { icon: 'fa-solid fa-plug', label: 'Sent by CoachIQ' },
      global: { stubs: { 'font-awesome-icon': true } }
    })
    expect(tag.text()).toBe('Sent by CoachIQ')
    expect(tag.find('font-awesome-icon-stub').attributes('icon')).toBe('fa-solid fa-plug')
  })
})
