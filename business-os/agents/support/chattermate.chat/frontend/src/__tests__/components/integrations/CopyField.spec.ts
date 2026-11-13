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

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { toast } from 'vue-sonner'

import CopyField from '../../../components/integrations/CopyField.vue'

vi.mock('vue-sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

const mountField = () => mount(CopyField, {
  props: { fieldId: 'verify-token', label: 'Verify token', name: 'Verify token', value: 'tok-123' },
})

describe('CopyField', () => {
  beforeEach(() => vi.clearAllMocks())

  it('labels its input', () => {
    const wrapper = mountField()
    expect(wrapper.find('label').attributes('for')).toBe('verify-token')
    expect(wrapper.find('input').attributes('id')).toBe('verify-token')
  })

  it('copies the value', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    await mountField().find('button').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith('tok-123')
    expect(toast.success).toHaveBeenCalledWith('Verify token copied')
  })

  it('says so when the browser will not copy', async () => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error('insecure')) } })
    await mountField().find('button').trigger('click')
    await flushPromises()
    expect(toast.error).toHaveBeenCalled()
  })
})
