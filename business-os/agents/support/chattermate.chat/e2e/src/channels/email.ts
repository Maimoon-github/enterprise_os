import { connectEmail, routeToAgent } from '../api/channels'
import { env } from '../env'
import { Mailbox } from '../fakes/mailbox'
import { unique } from '../support/ids'
import { step } from '../support/step'
import { Chat, postWebhook, type ChannelChat, type ChannelConnector } from './chat'

/** An email chat, plus what only email has: the subject line every message carries. */
export interface EmailChat extends ChannelChat {
  readonly address: string
  readonly subject: string
  /** Message-ID of the customer's latest email, which a threaded reply points back at. */
  readonly lastMessageId: string | undefined
}

class EmailConversation extends Chat implements EmailChat {
  readonly address: string
  readonly subject: string
  private readonly sent: { messageId?: string }

  constructor(customerName: string, address: string, subject: string, sent: { messageId?: string }, deliver: (text: string) => Promise<void>, read: () => Promise<string[]>) {
    super('email', customerName, deliver, read)
    this.address = address
    this.subject = subject
    this.sent = sent
  }

  get lastMessageId(): string | undefined {
    return this.sent.messageId
  }
}

/**
 * A support inbox fed by an inbound-parse webhook (the per-account URL carries a
 * secret token, there is no signature). Replies go out over SMTP into the stack's
 * Mailpit, where the customer's address collects them.
 */
export const email: ChannelConnector<EmailChat> = ({ api, request, agentId }) =>
  step('Connect a support inbox', async () => {
    const inbox = `${unique('support')}@e2e.example.com`
    const account = await connectEmail(api, inbox)
    await routeToAgent(api, account.id, agentId)
    const token = new URL(account.webhook_url ?? '', env.backendUrl).searchParams.get('token')
    if (!token) throw new Error(`no token in the email webhook URL ${account.webhook_url}`)
    const mailbox = new Mailbox(request)

    return {
      chatWith(customerName) {
        const address = `${unique('customer').toLowerCase()}@customer.example.com`
        const subject = `Question from ${customerName}`
        const sent: { messageId?: string } = {}
        return new EmailConversation(customerName, address, subject, sent, async (text) => {
          sent.messageId = `<${unique('msg')}@customer.example.com>`
          await postWebhook(request, `/webhooks/email/${account.id}?token=${token}`, {
            json: JSON.stringify({ from: `${customerName} <${address}>`, to: inbox, subject, text, message_id: sent.messageId }),
          })
        }, async () => (await mailbox.messagesTo(address)).filter((m) => m.from === inbox).map((m) => m.text.trim()))
      },
    }
  })
