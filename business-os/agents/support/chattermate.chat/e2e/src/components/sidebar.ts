import type { Locator, Page } from '@playwright/test'

/** The dashboard's left navigation. */
export class Sidebar {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  /** Every nav link the signed-in user can see, in order. */
  get links(): Locator {
    // Scoped to the desktop sidebar; the mobile bottom bar repeats some links.
    return this.page.locator('nav.sidebar-nav').getByRole('link')
  }

  link(name: string): Locator {
    return this.links.filter({ hasText: new RegExp(`^\\s*${name}\\s*$`) })
  }
}
