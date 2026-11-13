import { test } from '@playwright/test'

/**
 * Runs `body` as a named report step, so traces and reports read as user actions
 * ("Customer sends 'I want a human'") instead of raw clicks. Page objects and
 * components wrap every public action in this.
 */
export function step<T>(title: string, body: () => Promise<T>): Promise<T> {
  return test.step(title, body, { box: true })
}
