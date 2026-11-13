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
 * The widget's frame host, for the CSP note beside the embed code. `loaded` stays
 * false until it's known, or if it couldn't be: the note just isn't shown then.
 */
export function useWidgetFrameHost(widgetId: Ref<string | undefined>) {
  const frameHost = ref<string | null>(null)
  const loaded = ref(false)

  const load = async () => {
    const id = widgetId.value
    frameHost.value = null
    loaded.value = false
    if (!id) return
    try {
      const host = await widgetService.getFrameHost(id)
      if (id !== widgetId.value) return
      frameHost.value = host
      loaded.value = true
    } catch (err) {
      console.error('Failed to load the widget frame host:', err)
    }
  }

  watch(widgetId, load, { immediate: true })
  return { frameHost, loaded }
}
