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
import MessageStatusTicks from '@/components/conversations/MessageStatusTicks.vue'

const stubs = { global: { stubs: { 'font-awesome-icon': true } } }

describe('MessageStatusTicks', () => {
  it.each([
    ['sent', 'Sent'],
    ['delivered', 'Delivered'],
    ['read', 'Read'],
  ])('labels a %s message', (status, label) => {
    const ticks = mount(MessageStatusTicks, { props: { status }, ...stubs })
    expect(ticks.find('.status-ticks').attributes('aria-label')).toBe(label)
    expect(ticks.find(`.status-ticks--${status}`).exists()).toBe(true)
  })

  it.each([null, undefined, 'failed', 'unknown'])(
    'shows nothing for %s — a failure has its own notice',
    (status) => {
      const ticks = mount(MessageStatusTicks, { props: { status }, ...stubs })
      expect(ticks.find('.status-ticks').exists()).toBe(false)
    },
  )
})

describe('MessageStatusTicks on an accent bubble', () => {
  it('marks read with the inverted badge', () => {
    const ticks = mount(MessageStatusTicks, { props: { status: 'read', onAccent: true }, ...stubs })
    expect(ticks.find('.status-ticks--on-accent.status-ticks--read').exists()).toBe(true)
  })
})
