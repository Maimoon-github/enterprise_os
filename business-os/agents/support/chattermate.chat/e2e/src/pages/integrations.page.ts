import { expect, type Locator, type Page } from '@playwright/test'
import { step } from '../support/step'

/** /settings/integrations: one card per integration, with Connect or Manage/Disconnect. */
export class IntegrationsPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  async goto(): Promise<void> {
    await this.page.goto('/settings/integrations')
    await expect(this.card('Jira')).toBeVisible()
  }

  card(name: string): Locator {
    return this.page.locator('.integration-card').filter({ has: this.page.getByText(name, { exact: true }) })
  }

  /**
   * Matches the card's "Access expired for …" warning when it names `account`.
   * The warning lists every account that needs reconnecting, and other tests
   * share the org, so this checks for one name within it.
   */
  expiredAccessFor(account: string): RegExp {
    const name = account.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    return new RegExp(`Access expired for [^—]*${name}[^—]*— reconnect to resume replies\\.`)
  }

  /** Opens the card's Manage dialog. */
  async manage(name: string): Promise<void> {
    await step(`Manage ${name}`, async () => {
      await this.card(name).getByRole('button', { name: 'Manage' }).click()
    })
  }

  /** The Manage dialog's prompt to reconnect an account Meta stopped accepting. */
  reconnectPrompt(): Locator {
    return this.page.getByText('Meta stopped accepting this account\'s access. Reconnect to resume replies.')
  }

  /** Starts the integration's OAuth flow; the provider's consent screen sends the browser back here. */
  async connect(name: string): Promise<void> {
    await step(`Connect ${name}`, async () => {
      await this.card(name).getByRole('button', { name: 'Connect' }).click()
      await expect(this.page).toHaveURL(/\/settings\/integrations/)
    })
  }
}
