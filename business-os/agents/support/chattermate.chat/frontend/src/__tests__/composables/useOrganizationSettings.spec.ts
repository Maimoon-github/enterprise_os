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
import { ref } from 'vue'

const updateOrganization = vi.fn()

vi.mock('@/composables/useAuth', () => ({
  useAuth: () => ({ user: ref({ organization_id: 'org-1' }) }),
}))

vi.mock('@/services/organization', () => ({
  organizationService: {
    getOrganization: vi.fn(),
    getOrganizationStats: vi.fn(),
    updateOrganization: (...args: unknown[]) => updateOrganization(...args),
  },
}))

const { useOrganizationSettings } = await import('@/composables/useOrganizationSettings')

describe('useOrganizationSettings – save errors', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the API detail when the website is refused', async () => {
    updateOrganization.mockRejectedValueOnce({
      message: 'Request failed with status code 400',
      response: { status: 400, data: { detail: "Localhost can't be used as your website. Use the site where you'll add the widget." } },
    })
    const settings = useOrganizationSettings()
    settings.formData.value.domain = 'localhost'

    await settings.updateOrganization()

    expect(updateOrganization).toHaveBeenCalledWith('org-1', expect.objectContaining({ domain: 'localhost' }))
    expect(settings.error.value).toBe("Localhost can't be used as your website. Use the site where you'll add the widget.")
    expect(settings.message.value).toBe('')
    expect(settings.hasChanges.value).toBe(true)
  })

  it('falls back to a generic message when there is no API detail', async () => {
    updateOrganization.mockRejectedValueOnce({})
    const settings = useOrganizationSettings()
    settings.formData.value.name = 'Renamed'

    await settings.updateOrganization()

    expect(settings.error.value).toBe('Failed to update organization')
  })
})
