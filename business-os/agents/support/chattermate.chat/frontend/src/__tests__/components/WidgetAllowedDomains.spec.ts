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

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const getAllowedDomains = vi.fn()
const setAllowedDomains = vi.fn()

vi.mock('@/services/widget', () => ({
  widgetService: {
    getAllowedDomains: (...args: unknown[]) => getAllowedDomains(...args),
    setAllowedDomains: (...args: unknown[]) => setAllowedDomains(...args),
  },
}))

const { default: WidgetAllowedDomains } = await import('@/components/agent/WidgetAllowedDomains.vue')

function render(widgetId: string | null = 'w-1') {
  return mount(WidgetAllowedDomains, {
    props: { widgetId: widgetId ?? undefined },
    global: { stubs: { 'font-awesome-icon': true } },
  })
}

const chips = (wrapper: ReturnType<typeof render>) =>
  wrapper.findAll('.allowed-domains-name').map((chip) => chip.text())

describe('WidgetAllowedDomains', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getAllowedDomains.mockResolvedValue([])
  })

  it('says any site can show the widget when the list is empty', async () => {
    const wrapper = render()
    await flushPromises()

    expect(getAllowedDomains).toHaveBeenCalledWith('w-1')
    expect(wrapper.text()).toContain('Any site can show this widget.')
  })

  it('lists the saved domains', async () => {
    getAllowedDomains.mockResolvedValue(['acme.com', 'localhost:3000'])
    const wrapper = render()
    await flushPromises()

    expect(chips(wrapper)).toEqual(['acme.com', 'localhost:3000'])
  })

  it('adds a domain and shows it as the server stored it', async () => {
    setAllowedDomains.mockResolvedValue(['acme.com'])
    const wrapper = render()
    await flushPromises()

    await wrapper.find('input').setValue('  https://ACME.com/  ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(setAllowedDomains).toHaveBeenCalledWith('w-1', ['https://ACME.com/'])
    expect(chips(wrapper)).toEqual(['acme.com'])
    expect((wrapper.find('input').element as HTMLInputElement).value).toBe('')
  })

  it('keeps what was typed and explains a refused domain', async () => {
    setAllowedDomains.mockRejectedValue({ response: { status: 422, data: { detail: "'bad domain' isn't a valid domain" } } })
    const wrapper = render()
    await flushPromises()

    await wrapper.find('input').setValue('bad domain')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toBe("'bad domain' isn't a valid domain")
    expect((wrapper.find('input').element as HTMLInputElement).value).toBe('bad domain')
    expect(chips(wrapper)).toEqual([])
  })

  it('shows a plain message for an unexpected failure', async () => {
    setAllowedDomains.mockRejectedValue(new Error('network'))
    const wrapper = render()
    await flushPromises()

    await wrapper.find('input').setValue('acme.com')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toBe('Couldn’t save the allowed domains.')
  })

  it('removes a domain', async () => {
    getAllowedDomains.mockResolvedValue(['acme.com', 'shop.acme.com'])
    setAllowedDomains.mockResolvedValue(['shop.acme.com'])
    const wrapper = render()
    await flushPromises()

    await wrapper.find('[aria-label="Remove acme.com"]').trigger('click')
    await flushPromises()

    expect(setAllowedDomains).toHaveBeenCalledWith('w-1', ['shop.acme.com'])
    expect(chips(wrapper)).toEqual(['shop.acme.com'])
  })

  it('removing the last domain opens the widget to any site again', async () => {
    getAllowedDomains.mockResolvedValue(['acme.com'])
    setAllowedDomains.mockResolvedValue([])
    const wrapper = render()
    await flushPromises()

    await wrapper.find('[aria-label="Remove acme.com"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Any site can show this widget.')
  })

  it('does not add an empty entry', async () => {
    const wrapper = render()
    await flushPromises()

    await wrapper.find('input').setValue('   ')
    await wrapper.find('form').trigger('submit')

    expect(setAllowedDomains).not.toHaveBeenCalled()
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('locks the form while saving', async () => {
    let finish: (value: string[]) => void = () => {}
    setAllowedDomains.mockReturnValue(new Promise((resolve) => { finish = resolve }))
    const wrapper = render()
    await flushPromises()

    await wrapper.find('input').setValue('acme.com')
    await wrapper.find('form').trigger('submit')
    expect(wrapper.find('input').attributes('disabled')).toBeDefined()

    finish(['acme.com'])
    await flushPromises()
    expect(wrapper.find('input').attributes('disabled')).toBeUndefined()
  })

  it('says when the list could not be loaded, and saves nothing over it', async () => {
    getAllowedDomains.mockRejectedValue({ response: { status: 403 } })
    const wrapper = render()
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toBe('Couldn’t load the allowed domains.')
    // Saving replaces the whole list, so an unknown one must not be overwritten
    expect(wrapper.find('input').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).not.toContain('Any site can show this widget.')
    await wrapper.find('form').trigger('submit')
    expect(setAllowedDomains).not.toHaveBeenCalled()
  })

  it('loads nothing until it knows the widget', async () => {
    render(null)
    await flushPromises()
    expect(getAllowedDomains).not.toHaveBeenCalled()
  })

  it('never shows one widget\'s list under another after a quick switch', async () => {
    let answerA: (list: string[]) => void = () => {}
    getAllowedDomains
      .mockImplementationOnce(() => new Promise((resolve) => { answerA = resolve }))
      .mockResolvedValueOnce(['b.example.com'])
    const wrapper = render('w-a')
    await wrapper.setProps({ widgetId: 'w-b' })
    await flushPromises()

    answerA(['a.example.com'])
    await flushPromises()

    expect(chips(wrapper)).toEqual(['b.example.com'])
  })
})
