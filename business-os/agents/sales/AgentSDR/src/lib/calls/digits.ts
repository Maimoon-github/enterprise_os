/**
 * A phone number or chat title reduced to its digits — how the app and the
 * recorder extension compare numbers ("+91 98765-43210" → "919876543210").
 * Pure and dependency-free, so the extension can bundle it.
 */
export function digitsOnly(value: string): string {
  return value.replace(/\D/g, "");
}
