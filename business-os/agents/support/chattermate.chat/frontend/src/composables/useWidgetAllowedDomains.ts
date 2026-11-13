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

import { ref, watch, type Ref } from 'vue'
import { widgetService } from '@/services/widget'

/**
 * A widget's allowed domains, edited in place: every add or remove is saved straight
 * away, and the list shown is always what the server stored (it normalises entries,
 * so "https://Shop.com/" comes back as "shop.com").
 */
export function useWidgetAllowedDomains(widgetId: Ref<string | undefined>) {
  const domains = ref<string[]>([])
  const draft = ref('')
  // Saving replaces the whole list, so nothing is saved until the real one loaded
  const loaded = ref(false)
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')

  const messageFrom = (err: any, fallback: string): string => {
    const detail = err?.response?.data?.detail
    if (typeof detail === 'string') return detail
    // A request-shape refusal (a list of field errors): its first message
    const first = Array.isArray(detail) ? detail[0]?.msg : undefined
    return typeof first === 'string' ? first : fallback
  }

  const load = async () => {
    const id = widgetId.value
    domains.value = []
    loaded.value = false
    if (!id) return
    loading.value = true
    error.value = ''
    try {
      const list = await widgetService.getAllowedDomains(id)
      if (id !== widgetId.value) return // switched widgets meanwhile: not this list
      domains.value = list
      loaded.value = true
    } catch (err) {
      if (id === widgetId.value) error.value = messageFrom(err, 'Couldn’t load the allowed domains.')
    } finally {
      if (id === widgetId.value) loading.value = false
    }
  }

  const save = async (next: string[]): Promise<boolean> => {
    const id = widgetId.value
    if (!id || !loaded.value) return false
    saving.value = true
    error.value = ''
    try {
      const saved = await widgetService.setAllowedDomains(id, next)
      if (id !== widgetId.value) return false
      domains.value = saved
      return true
    } catch (err) {
      error.value = messageFrom(err, 'Couldn’t save the allowed domains.')
      return false
    } finally {
      saving.value = false
    }
  }

  const add = async () => {
    const entry = draft.value.trim()
    if (!entry || saving.value) return
    if (await save([...domains.value, entry])) draft.value = ''
  }

  const remove = async (domain: string) => {
    if (saving.value) return
    await save(domains.value.filter((d) => d !== domain))
  }

  watch(widgetId, () => void load(), { immediate: true })

  return { domains, draft, loaded, loading, saving, error, add, remove }
}
