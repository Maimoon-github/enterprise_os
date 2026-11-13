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
import { useCurrency } from '@/composables/useCurrency'

const { formatCurrency } = useCurrency()

describe('formatCurrency', () => {
    it.each([
        ['600.0', 'USD', '$600.00'],
        [600, 'USD', '$600.00'],
        [699.95, 'USD', '$699.95'],
        ['1299.5', 'USD', '$1,299.50'],
        [0, 'USD', '$0.00'],
        [600, 'JPY', '¥600'],
        ['49.9', 'EUR', '€49.90'],
        [12.5, undefined, '12.50'],
        [12.5, 'XYZ', 'XYZ12.50'],
    ])('%o in %s shows %s', (price, currency, expected) => {
        expect(formatCurrency(price as string | number, currency)).toBe(expected)
    })

    it('leaves empty and non-numeric prices alone', () => {
        expect(formatCurrency(null, 'USD')).toBe('')
        expect(formatCurrency(undefined, 'USD')).toBe('')
        expect(formatCurrency('', 'USD')).toBe('')
        expect(formatCurrency('Free', 'USD')).toBe('$Free')
    })
})
