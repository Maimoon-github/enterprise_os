import { expect, type APIRequestContext } from '@playwright/test'
import { env } from '../env'

interface MailpitMessage {
  ID: string
  Subject: string
  Created: string
  From: { Address: string; Name: string }
}

export interface Email {
  id: string
  from: string
  subject: string
  text: string
}

interface Lookup {
  /** Only emails received after this moment — e.g. a second code to the same address. */
  since?: Date
}

/**
 * Client for the stack's Mailpit (SMTP capture). Everything the backend emails —
 * verification codes, notifications — lands here instead of a real inbox.
 */
export class Mailbox {
  private readonly request: APIRequestContext

  constructor(request: APIRequestContext) {
    this.request = request
  }

  /** The newest email to `address`, waiting for it to arrive. */
  async latestTo(address: string, { since }: Lookup = {}): Promise<{ subject: string; text: string }> {
    let latest: MailpitMessage | undefined
    await expect.poll(async () => {
      const newest = (await this.search(`to:"${address}"`))[0]
      latest = newest && (!since || new Date(newest.Created) >= since) ? newest : undefined
      return latest?.ID
    }, { message: `an email to ${address}`, timeout: 15_000 }).toBeTruthy()
    const message = await (await this.request.get(`${env.mailUrl}/api/v1/message/${latest!.ID}`)).json()
    return { subject: latest!.Subject, text: String(message.Text ?? '') }
  }

  /** Subjects of every email to `address` (newest first), optionally only those since a time. */
  async subjectsTo(address: string, { since }: Lookup = {}): Promise<string[]> {
    return (await this.search(`to:"${address}"`)).filter((m) => !since || new Date(m.Created) >= since).map((m) => m.Subject)
  }

  /** Every email to `address` so far, oldest first — no waiting; poll it. */
  async messagesTo(address: string): Promise<Email[]> {
    const messages = await this.search(`to:"${address}"`)
    return Promise.all(messages.reverse().map(async (m) => ({
      id: m.ID,
      from: m.From.Address,
      subject: m.Subject,
      text: String((await (await this.request.get(`${env.mailUrl}/api/v1/message/${m.ID}`)).json()).Text ?? ''),
    })))
  }

  /** One email's raw headers, e.g. In-Reply-To for threading. */
  async headers(id: string): Promise<Record<string, string[]>> {
    return (await this.request.get(`${env.mailUrl}/api/v1/message/${id}/headers`)).json()
  }

  private async search(query: string): Promise<MailpitMessage[]> {
    const response = await this.request.get(`${env.mailUrl}/api/v1/search`, { params: { query } })
    return ((await response.json()) as { messages: MailpitMessage[] }).messages
  }

  /** The 6-digit verification code in the newest email to `address`. */
  async verificationCode(address: string, lookup: Lookup = {}): Promise<string> {
    const { text } = await this.latestTo(address, lookup)
    const code = /\b(\d{6})\b/.exec(text)?.[1]
    if (!code) throw new Error(`no 6-digit code in the email to ${address}:\n${text.slice(0, 500)}`)
    return code
  }
}
