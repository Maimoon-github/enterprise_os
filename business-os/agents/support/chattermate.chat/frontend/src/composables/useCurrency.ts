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

/**
 * Composable for currency formatting utilities
 */
/** Decimal places a currency is normally shown with (2 for USD, 0 for JPY). */
const fractionDigits = (currencyCode?: string): number => {
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: currencyCode || 'USD' })
      .resolvedOptions().maximumFractionDigits ?? 2
  } catch {
    return 2 // not an ISO 4217 code
  }
}

export function useCurrency() {
  // Currency symbol mapping
  const currencySymbols: Record<string, string> = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥',
    'INR': '₹',
    'CAD': 'CA$',
    'AUD': 'A$',
    'CNY': '¥',
    'CHF': 'CHF',
    'SEK': 'kr',
    'NOK': 'kr',
    'DKK': 'kr',
    'NZD': 'NZ$',
    'SGD': 'S$',
    'HKD': 'HK$',
    'KRW': '₩',
    'MXN': 'MX$',
    'BRL': 'R$',
    'ZAR': 'R',
    'RUB': '₽',
    'TRY': '₺',
    'THB': '฿',
    'PLN': 'zł',
    'AED': 'د.إ',
    'SAR': '﷼',
    'ILS': '₪',
    'MYR': 'RM'
  };

  /**
   * Format price with proper currency symbol
   * @param price - The price value
   * @param currencyCode - ISO 4217 currency code (e.g., 'USD', 'EUR')
   * @returns Formatted price string with currency symbol
   */
  const formatCurrency = (price: string | number | null | undefined, currencyCode?: string): string => {
    if (!price && price !== 0) return '';

    // Get currency symbol, fallback to currency code or empty string
    const symbol = currencyCode ? (currencySymbols[currencyCode] || currencyCode) : '';

    // Numbers get the currency's usual decimals ($600.00, ¥600), so a price
    // that arrives as "600.0" or 600 doesn't render as "$600.0" or "$600".
    const amount = typeof price === 'number' ? price : Number(price)
    const priceValue = Number.isFinite(amount)
      ? amount.toLocaleString('en-US', {
          minimumFractionDigits: fractionDigits(currencyCode),
          maximumFractionDigits: fractionDigits(currencyCode)
        })
      : String(price)

    return symbol ? `${symbol}${priceValue}` : priceValue;
  };

  /**
   * Get currency symbol for a given currency code
   * @param currencyCode - ISO 4217 currency code
   * @returns Currency symbol or code if not found
   */
  const getCurrencySymbol = (currencyCode: string): string => {
    return currencySymbols[currencyCode] || currencyCode;
  };

  return {
    formatCurrency,
    getCurrencySymbol,
    currencySymbols
  };
}
