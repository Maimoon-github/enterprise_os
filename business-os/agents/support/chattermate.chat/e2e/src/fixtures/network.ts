import type { BrowserContext } from '@playwright/test'

/**
 * Everything off the local stack — fonts, analytics, geo-IP lookups, CDNs. No
 * journey depends on them, and blocking them keeps runs hermetic: nothing leaves
 * the machine, and an outage elsewhere can't fail a test. Text still renders
 * with fallback fonts.
 */
const OFF_STACK = /^https?:\/\/(?!(127\.0\.0\.1|localhost)[:/])/

export async function blockThirdParty(context: BrowserContext): Promise<void> {
  await context.route(OFF_STACK, (route) => route.abort())
}
