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

/** One validation problem in FastAPI's 422 body. */
interface ValidationDetail {
  msg?: string
}

/**
 * A sentence to show for a failed API call. FastAPI sends `detail` as a
 * string for errors we raise, but as a list of objects for request
 * validation (422) - shown raw, that list reads "[object Object]".
 */
export function apiErrorMessage(error: any, fallback: string): string {
  const data = error?.response?.data
  const detail = data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail)) {
    const msg = (detail as ValidationDetail[]).find((d) => typeof d?.msg === 'string')?.msg
    // Pydantic prefixes a validator's own message with "Value error, "
    if (msg) return msg.replace(/^Value error, /, '')
  }
  if (typeof data?.message === 'string' && data.message) return data.message
  return fallback
}
