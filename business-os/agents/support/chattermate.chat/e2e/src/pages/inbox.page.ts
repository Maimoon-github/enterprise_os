import { expect, type Locator, type Page } from '@playwright/test'
import { step } from '../support/step'

/** /conversations — where human agents pick up chats. */
export class InboxPage {
  readonly page: Page

  constructor(page: Page) {
    this.page = page
  }

  async goto(): Promise<void> {
    await this.page.goto('/conversations')
    await expect(this.page.getByRole('heading', { name: 'Conversations', exact: true })).toBeVisible()
  }

  /**
   * The list is not pushed new chats over the socket, so keep reloading until the
   * conversation shows up — the same thing an agent would do.
   */
  async openConversationWith(customerName: string): Promise<void> {
    await step(`Agent opens the chat with ${customerName}`, async () => {
      const item = this.page.getByRole('button', { name: `Conversation with ${customerName}`, exact: true })
      await expect(async () => {
        await this.page.reload()
        await item.click({ timeout: 2_000 })
      }).toPass({ timeout: 30_000 })
      await expect(this.page.getByRole('heading', { name: customerName })).toBeVisible()
    })
  }

  async takeOver(): Promise<void> {
    await step('Agent takes over the chat', async () => {
      await this.page.getByRole('button', { name: 'Take over chat', exact: true }).click()
      await expect(this.messageInput).toBeEditable()
    })
  }

  async reply(text: string): Promise<void> {
    await step(`Agent replies "${text}"`, async () => {
      await this.messageInput.fill(text)
      await this.page.getByRole('button', { name: 'Send', exact: true }).click()
      await expect(this.page.locator('.message.agent .message-bubble').last()).toContainText(text)
    })
  }

  get messageInput(): Locator {
    return this.page.getByPlaceholder('Type a message or paste a screenshot')
  }

  /** The agent's message bubble that carries `text`. */
  agentMessage(text: string): Locator {
    return this.page.locator('.message.agent').filter({ hasText: text })
  }

  /** The download link for an attachment in the open chat. */
  attachment(filename: string): Locator {
    return this.page.locator('.attachment-link').filter({ hasText: filename })
  }

  /** The bubble also shows a relative time ("less than a minute ago"), so assert with toContainText. */
  lastCustomerMessage(): Locator {
    return this.page.locator('.message.user .message-bubble').last()
  }
}
