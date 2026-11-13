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
import { describe, it, expect } from 'vitest'
import { looksLikeWebsite, websiteHost } from '@/utils/website'

describe('websiteHost', () => {
  it.each([
    ['acme.com', 'acme.com'],
    ['  https://WWW.Acme.com/pricing?plan=pro ', 'www.acme.com'],
    ['shop.acme.co.uk:8443/x', 'shop.acme.co.uk'],
    ['acme.com.', 'acme.com'],
    ['bücher.de', 'xn--bcher-kva.de'],
    ['', ''],
    ['   ', ''],
    ['acme .com', ''],
  ])('%j -> %j', (typed, host) => {
    expect(websiteHost(typed)).toBe(host)
  })
})

describe('looksLikeWebsite', () => {
  it.each(['acme.com', 'sub-domain.example.co.uk', 'my.cool-site.com', 'https://acme.com/', 'acme.com/', 'bücher.de'])(
    'accepts %j',
    (typed) => expect(looksLikeWebsite(typed)).toBe(true),
  )

  it.each(['', 'invalid', 'invalid@domain', 'invalid..', '-acme.com', 'acme-.com', 'acme .com', 'acme_shop.com'])(
    'refuses %j',
    (typed) => expect(looksLikeWebsite(typed)).toBe(false),
  )
})
