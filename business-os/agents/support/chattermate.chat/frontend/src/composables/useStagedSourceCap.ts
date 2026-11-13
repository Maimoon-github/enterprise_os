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

import type { Ref } from 'vue'
import { subscriptionStorage } from '@/utils/storage'

/**
 * Keeps a staged batch of knowledge sources within the plan's source cap.
 *
 * The server rejects a whole batch that would go over the cap, so staging one
 * source too many loses all of them. On a one-source plan the onboarding wizard
 * pre-stages the signup domain; a second add then swaps the staged source
 * rather than queuing a batch that is bound to fail.
 *
 * `inUseCount` is every source already counting against the cap (indexed or
 * still crawling), mirroring the server's count.
 *
 * A cap of 0 means the plan sets none we know of (self-hosted, or limits not
 * loaded yet) and the server stays the only check.
 */
export function useStagedSourceCap(
  inUseCount: Ref<number>,
  urls: Ref<string[]>,
  files: Ref<File[]>,
) {
  // Read on every call: the subscription can land in storage after mount.
  const cap = () => subscriptionStorage.getPlanLimits().maxKnowledgeSources
  const room = () => cap() - inUseCount.value
  const capMessage = (detail: string) =>
    `Your plan includes ${cap()} knowledge source${cap() === 1 ? '' : 's'}${detail}`

  /**
   * Call right after staging `added` sources onto the end of `newest`. Older
   * staged sources (the other list first, then the front of `newest`) are
   * dropped until the batch fits the cap. If the new sources can't fit on
   * their own they are unstaged instead and the message to show is returned;
   * null means the batch fits.
   */
  const fitToCap = (newest: 'urls' | 'files', added = 1): string | null => {
    if (cap() <= 0) return null
    const latest: Ref<unknown[]> = newest === 'urls' ? urls : files
    const other: Ref<unknown[]> = newest === 'urls' ? files : urls
    if (added > room()) {
      latest.value = latest.value.slice(0, -added)
      return room() > 0 ? capMessage(`. Pick up to ${room()}.`) : capMessage(", and it's already in use.")
    }
    let overflow = latest.value.length + other.value.length - room()
    const fromOther = Math.min(Math.max(overflow, 0), other.value.length)
    other.value = other.value.slice(fromOther)
    overflow -= fromOther
    if (overflow > 0) latest.value = latest.value.slice(overflow)
    return null
  }

  return { fitToCap }
}
