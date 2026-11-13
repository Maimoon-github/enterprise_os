import { expect, type Locator, type Page } from '@playwright/test'
import { step } from '../support/step'

export interface NewTeamMember {
  name: string
  email: string
  password: string
  role: 'Admin' | 'Agent'
}

/** /human-agents — people, teams and roles. */
export class HumanAgentsPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  async goto(): Promise<void> {
    await this.page.goto('/human-agents')
    await expect(this.page.getByRole('main').getByRole('heading', { name: 'Human Agents', exact: true })).toBeVisible()
  }

  async invite(member: NewTeamMember): Promise<void> {
    await step(`Add ${member.email} as ${member.role}`, async () => {
      await this.page.getByRole('button', { name: 'Invite agent' }).click()
      const dialog = this.page.getByRole('dialog', { name: 'Create New User' })
      await dialog.getByLabel('Full Name').fill(member.name)
      await dialog.getByLabel('Email').fill(member.email)
      await dialog.getByLabel('Role').selectOption({ label: member.role })
      await dialog.getByLabel('Password', { exact: true }).fill(member.password)
      await dialog.getByLabel('Confirm Password').fill(member.password)
      await dialog.getByRole('button', { name: 'Create', exact: true }).click()
      await expect(dialog).toBeHidden()
    })
  }

  member(email: string): Locator {
    return this.page.getByRole('main').getByText(email)
  }
}
