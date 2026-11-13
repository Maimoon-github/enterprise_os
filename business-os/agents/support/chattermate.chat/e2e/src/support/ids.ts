import { randomBytes } from 'node:crypto'

let counter = 0

/**
 * A name no other test (or earlier run against a reused database) will have.
 * Every resource a test creates gets one, so tests never depend on each other's data.
 */
export function unique(prefix: string): string {
  counter += 1
  const random = randomBytes(3).toString('hex')
  return `${prefix}-${Date.now().toString(36)}${counter}${random}`
}
