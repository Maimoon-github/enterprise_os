// What each provider rejects, from its own published limits — deliberately NOT
// the backend's constants (backend/app/channels/interactive_limits.py), so a
// backend that drifts past a real limit gets the same 400 it would in production.
//
// Each check returns the provider-style error message, or null when the payload
// would be accepted.

type Body = Record<string, unknown> | null
// Provider payloads are walked loosely; typing every Graph/Bot API shape buys nothing here.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Loose = any

const len = (value: unknown): number => (typeof value === 'string' ? [...value].length : 0)
const bytes = (value: unknown): number => (typeof value === 'string' ? Buffer.byteLength(value) : 0)

function tooLong(field: string, value: unknown, max: number): string | null {
  return len(value) > max ? `${field} is ${len(value)} characters; the limit is ${max}` : null
}

function first(...checks: Array<string | null>): string | null {
  return checks.find((c) => c !== null) ?? null
}

// https://developers.facebook.com/docs/whatsapp/cloud-api/messages
function whatsapp(body: Body): string | null {
  if (!body || body.messaging_product !== 'whatsapp' || !body.type) return null // receipts, typing
  if (body.type === 'text') return tooLong('text.body', (body.text as Body)?.body, 4096)
  if (body.type !== 'interactive') return null
  const interactive = body.interactive as Record<string, Loose>
  const bodyText = tooLong('interactive.body.text', interactive?.body?.text, 1024)
  if (interactive?.type === 'button') {
    const buttons: Loose[] = interactive.action?.buttons ?? []
    if (buttons.length < 1 || buttons.length > 3) return `interactive buttons must number 1-3, got ${buttons.length}`
    return first(bodyText, ...buttons.map((b) => first(
      tooLong('button title', b.reply?.title, 20),
      bytes(b.reply?.id) > 256 ? 'button id is over 256 bytes' : null,
    )))
  }
  if (interactive?.type === 'list') {
    const sections: Loose[] = interactive.action?.sections ?? []
    const rows = sections.flatMap((s) => s.rows ?? [])
    if (sections.length > 10) return `a list allows 10 sections, got ${sections.length}`
    if (rows.length < 1 || rows.length > 10) return `a list allows 1-10 rows in total, got ${rows.length}`
    return first(bodyText, tooLong('list button', interactive.action?.button, 20), ...rows.map((r) => first(
      tooLong('row title', r.title, 24),
      tooLong('row description', r.description, 72),
      bytes(r.id) > 200 ? 'row id is over 200 bytes' : null,
    )))
  }
  return bodyText
}

// https://developers.facebook.com/docs/messenger-platform/send-messages/quick-replies
function pageSend(textMax: number) {
  return (body: Body): string | null => {
    const message = body?.message as Record<string, Loose> | undefined
    if (!message) return null // sender_action (typing)
    const replies: Loose[] = message.quick_replies ?? []
    if (replies.length > 13) return `quick_replies allows 13, got ${replies.length}`
    return first(tooLong('message.text', message.text, textMax), ...replies.map((q) => tooLong('quick reply title', q.title, 20)))
  }
}

// https://core.telegram.org/bots/api#sendmessage
function telegram(action: string, body: Body): string | null {
  if (action !== 'sendMessage') return null
  const keyboard: Loose[] = (body?.reply_markup as Record<string, Loose> | undefined)?.inline_keyboard?.flat() ?? []
  return first(
    tooLong('text', body?.text, 4096),
    ...keyboard.map((b) => (bytes(b.callback_data) > 64 ? 'callback_data is over 64 bytes' : null)),
  )
}

// https://developers.line.biz/en/reference/messaging-api/#send-push-message
function line(action: string, body: Body): string | null {
  if (action !== 'push') return null
  const messages: Loose[] = (body?.messages as Loose[]) ?? []
  if (messages.length < 1 || messages.length > 5) return `messages must number 1-5, got ${messages.length}`
  return first(...messages.map((m) => tooLong('text', m.text, 5000)))
}

/** The provider's rejection for this call, or null. `provider` is the fake's path prefix. */
export function rejection(provider: string, action: string, method: string, body: Body): string | null {
  if (method !== 'POST') return null
  switch (provider) {
    case 'graph': return action === 'messages' ? (body?.messaging_product ? whatsapp(body) : pageSend(2000)(body)) : null
    case 'graph-instagram': return action === 'messages' ? pageSend(1000)(body) : null
    case 'telegram': return telegram(action, body)
    case 'line': return line(action, body)
    case 'twilio': return action === 'Messages.json' ? tooLong('Body', body?.Body, 1600) : null
    case 'plivo': return action === 'Message' ? tooLong('text', body?.text, 1600) : null
    case 'slack': return action === 'chat.postMessage' || action === 'chat.update' ? tooLong('text', body?.text, 40000) : null
    default: return null
  }
}
