import { expect, type Locator, type Page } from '@playwright/test'
import { step } from '../support/step'

/**
 * The agent editor's Widget tab: the "Allowed domains" editor, which saves every
 * add and remove straight away and shows the list as the server stored it.
 */
export class WidgetAllowedDomainsPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  async goto(agentId: string): Promise<void> {
    await this.page.goto(`/ai-agents?agent=${agentId}&tab=widget`)
    // The editor applies ?tab= only after its integration checks answer; a person
    // would just click the tab
    await this.page.getByRole('button', { name: 'Widget', exact: true }).click()
    await expect(this.section.getByRole('heading', { name: 'Allowed domains' })).toBeVisible()
    // Editable once the stored list has loaded
    await expect(this.input).toBeEditable()
  }

  /** Types `entry` and adds it; resolves once the server has answered. */
  async add(entry: string): Promise<void> {
    await step(`Allow "${entry}"`, async () => {
      await this.input.fill(entry)
      await this.saved(() => this.section.getByRole('button', { name: 'Add', exact: true }).click())
    })
  }

  async remove(domain: string): Promise<void> {
    await step(`Remove "${domain}"`, async () => {
      await this.saved(() => this.section.getByRole('button', { name: `Remove ${domain}`, exact: true }).click())
    })
  }

  /** The saved list's entries, in order. */
  get domains(): Locator {
    return this.section.getByRole('list', { name: 'Allowed domains' }).getByRole('listitem')
  }

  /** Why the last add or remove was refused. */
  get error(): Locator {
    return this.section.getByRole('alert')
  }

  /** Shown instead of the list when it is empty. */
  get anySiteNotice(): Locator {
    return this.section.getByText('Any site can show this widget.')
  }

  /**
   * The Content-Security-Policy lines shown beside each embed code: the script
   * snippet's first, then the iframe snippet's. CSS: plain code blocks with no
   * accessible name of their own.
   */
  get cspSources(): Locator {
    return this.page.locator('.csp-note pre')
  }

  private get input(): Locator {
    return this.section.getByLabel('Domain to allow')
  }

  /** CSS: the editor is a plain block on the Widget tab, with no landmark of its own. */
  private get section(): Locator {
    return this.page.locator('.allowed-domains')
  }

  private async saved(action: () => Promise<void>): Promise<void> {
    const answered = this.page.waitForResponse((r) => r.url().endsWith('/embed-settings') && r.request().method() === 'PUT')
    await action()
    await answered
  }
}
