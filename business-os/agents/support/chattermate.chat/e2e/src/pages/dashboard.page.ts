import { expect, type Locator, type Page } from '@playwright/test'
import { step } from '../support/step'

/** The signed-in shell around every dashboard screen. */
export class Dashboard {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  async logout(): Promise<void> {
    await step('Log out', async () => {
      // The profile menu trigger is an avatar with no accessible name.
      await this.page.locator('.profile-trigger').click()
      await this.page.getByRole('button', { name: 'Logout' }).click()
      await expect(this.page).toHaveURL(/\/login/)
    })
  }

  get accessDenied(): Locator {
    return this.page.getByRole('heading', { name: 'Access Denied' })
  }
}
