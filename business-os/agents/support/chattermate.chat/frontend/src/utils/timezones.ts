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

import { clientTz, listTz } from 'timezone-select-js'

export interface TimezoneOption {
  value: string
  label: string
  /** Other IANA names the library files under this entry. */
  included?: string[]
}

const UTC_OPTION: TimezoneOption = { value: 'UTC', label: '(GMT+00:00) UTC' }

/**
 * The timezones an organization can pick. The library's list has no plain UTC —
 * the zone servers, containers and CI browsers report — so it is added.
 */
export function timezoneOptions(): TimezoneOption[] {
  const options: TimezoneOption[] = listTz()
  return options.some((option) => option.value === UTC_OPTION.value) ? options : [UTC_OPTION, ...options]
}

/**
 * The browser's timezone as one of `options` — by name, then by alias — or UTC.
 * A value the select doesn't list leaves the required field empty, and the
 * first-run setup form could not be submitted at all.
 */
export function defaultTimezone(options: TimezoneOption[] = timezoneOptions(), zone: string = clientTz()): string {
  const match = options.find((option) => option.value === zone || option.included?.includes(zone))
  return match ? match.value : UTC_OPTION.value
}
