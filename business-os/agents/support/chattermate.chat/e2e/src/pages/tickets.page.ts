import { expect, type Locator, type Page } from '@playwright/test'
import { step } from '../support/step'

/** /tickets and /tickets/:id. */
export class TicketsPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  async goto(): Promise<void> {
    await this.page.goto('/tickets')
    await expect(this.page.getByRole('main').getByRole('heading', { name: 'Tickets', exact: true })).toBeVisible()
  }

  /** Ticket rows are clickable divs; the title is the summary the AI gave. */
  row(title: string): Locator {
    return this.page.locator('.table-row').filter({ hasText: title })
  }

  async open(title: string): Promise<void> {
    await step(`Open ticket "${title}"`, async () => {
      await this.row(title).click()
      await expect(this.page).toHaveURL(/\/tickets\/[^/]+$/)
      await expect(this.status).toBeEnabled()
    })
  }

  get status(): Locator {
    return this.page.getByLabel('Status', { exact: true })
  }

  async setStatus(label: string): Promise<void> {
    await step(`Set ticket status to ${label}`, async () => {
      const saved = this.page.waitForResponse((r) => r.request().method() === 'PATCH' && /\/tickets\/[^/]+$/.test(r.url()))
      await this.status.selectOption({ label })
      expect((await saved).ok()).toBe(true)
    })
  }

  /** The label of the selected status option. */
  get statusLabel(): Locator {
    return this.status.locator('option:checked')
  }
}
