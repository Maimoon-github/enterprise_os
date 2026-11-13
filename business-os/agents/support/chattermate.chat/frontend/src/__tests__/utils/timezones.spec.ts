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

import { describe, expect, it, vi } from 'vitest'

vi.mock('timezone-select-js', () => ({
  listTz: () => [
    { value: 'Europe/London', label: '(GMT+00:00) London', included: ['Europe/London', 'GB'] },
    { value: 'Asia/Kolkata', label: '(GMT+05:30) Kolkata', included: ['Asia/Kolkata', 'Asia/Calcutta'] },
  ],
  clientTz: () => 'UTC',
}))

import { defaultTimezone, timezoneOptions } from '@/utils/timezones'

describe('timezones', () => {
  it('offers UTC, which the library list lacks', () => {
    expect(timezoneOptions()[0].value).toBe('UTC')
  })

  it('defaults a UTC browser to UTC rather than leaving the select empty', () => {
    // Found by the e2e suite: a CI browser in UTC could not submit first-run setup.
    expect(defaultTimezone()).toBe('UTC')
  })

  it('maps an alias to the listed zone', () => {
    expect(defaultTimezone(timezoneOptions(), 'Asia/Calcutta')).toBe('Asia/Kolkata')
  })

  it('falls back to UTC for a zone the list does not know', () => {
    expect(defaultTimezone(timezoneOptions(), 'Mars/Olympus_Mons')).toBe('UTC')
  })
})
