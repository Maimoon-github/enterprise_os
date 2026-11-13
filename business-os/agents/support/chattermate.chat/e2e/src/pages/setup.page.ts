import { expect, type Page } from '@playwright/test'
import { step } from '../support/step'

export interface OrgDetails {
  orgName: string
  domain: string
  adminName: string
  adminEmail: string
  adminPassword: string
}

/** First-run setup: the form a self-hoster fills in on an empty install. */
export class SetupPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  async goto(): Promise<void> {
    await this.page.goto('/setup')
    await expect(this.page.getByRole('heading', { name: 'Welcome to ChatterMate' })).toBeVisible()
  }

  async createOrganization(details: OrgDetails): Promise<void> {
    await step('Create the organization', async () => {
      const form = this.page
      await form.getByLabel('Organization Name', { exact: true }).fill(details.orgName)
      await form.getByLabel('Your website', { exact: true }).fill(details.domain)
      await form.getByLabel('Admin Name', { exact: true }).fill(details.adminName)
      await form.getByLabel('Admin Email', { exact: true }).fill(details.adminEmail)
      await form.getByLabel('Admin Password', { exact: true }).fill(details.adminPassword)
      await form.getByLabel('Confirm Password', { exact: true }).fill(details.adminPassword)
      await form.getByRole('button', { name: 'Create Organization' }).click()
      await expect(this.page).toHaveURL(/\/ai-agents/)
    })
  }
}
