import {
  test, expect, connectEmail, connectLine, connectMessenger, connectSms, connectWhatsAppNumber, digits,
  expectUnchanged, hmac, installSlackWorkspace, metaSignature, metaToken, phoneNumber, routeToAgent, sendWebhook,
  slackSignature, unique, whatsappPayload, TelegramBot,
} from '@e2e'

// Anyone can POST to a webhook URL. These are the requests a provider would never
// send: unsigned, wrongly signed, replayed — and events that are signed but must
// never start an AI turn (our own echoes, delivery receipts, other bots).

test.describe('forged webhooks are refused', () => {
  test('Meta (WhatsApp, Messenger, Instagram): a wrong or missing signature @channels @security', async ({ adminApi, request }) => {
    const { phoneNumberId } = await connectWhatsAppNumber(adminApi)
    const json = JSON.stringify(whatsappPayload(phoneNumberId, phoneNumber().slice(1), 'Mallory', { type: 'text', text: { body: 'hi' } }))

    const wrongKey = `sha256=${hmac('sha256', 'not-the-app-secret', json).toString('hex')}`
    expect((await sendWebhook(request, '/webhooks/meta', { json }, { 'x-hub-signature-256': wrongKey })).status()).toBe(403)
    expect((await sendWebhook(request, '/webhooks/meta', { json })).status()).toBe(403)
  })

  test('Slack: a wrong signature, or a correctly signed request replayed later @channels @security', async ({ request }) => {
    const json = JSON.stringify({ type: 'event_callback', team_id: 'T0FORGED', event: { type: 'message', channel: 'D1', user: 'U1', text: 'hi', ts: '1.1' } })
    const now = String(Math.floor(Date.now() / 1000))
    const tenMinutesAgo = String(Math.floor(Date.now() / 1000) - 600)

    const wrong = { 'x-slack-request-timestamp': now, 'x-slack-signature': 'v0=00' }
    expect((await sendWebhook(request, '/webhooks/slack', { json }, wrong)).status()).toBe(403)
    const replayed = { 'x-slack-request-timestamp': tenMinutesAgo, 'x-slack-signature': slackSignature(json, tenMinutesAgo) }
    expect((await sendWebhook(request, '/webhooks/slack', { json }, replayed)).status()).toBe(403)
  })

  test('Telegram: a wrong webhook secret @channels @security', async ({ adminApi, request, agent }) => {
    const { account } = await TelegramBot.connect(adminApi, request, agent.id)
    const response = await sendWebhook(request, `/webhooks/telegram/${account.id}`, {
      json: JSON.stringify({ update_id: 1, message: { message_id: 1, date: 0, chat: { id: 1, type: 'private' }, from: { id: 1, is_bot: false, first_name: 'M' }, text: 'hi' } }),
    }, { 'x-telegram-bot-api-secret-token': 'guessed' })
    expect(response.status()).toBe(403)
  })

  test('LINE: a signature made with the wrong channel secret @channels @security', async ({ adminApi, request }) => {
    const account = await connectLine(adminApi, unique('line-secret'), unique('line-token'))
    const json = JSON.stringify({ destination: account.external_account_id, events: [{ type: 'message', source: { type: 'user', userId: `U${digits(32)}` }, message: { type: 'text', id: '1', text: 'hi' } }] })
    const response = await sendWebhook(request, `/webhooks/line/${account.id}`, { json }, {
      'x-line-signature': hmac('sha256', 'not-the-channel-secret', json).toString('base64'),
    })
    expect(response.status()).toBe(403)
  })

  test('SMS: Twilio and Plivo signatures made with the wrong auth token @channels @security', async ({ adminApi, request }) => {
    const number = phoneNumber()
    const twilio = await connectSms(adminApi, 'twilio', number, { account_sid: unique('AC'), auth_token: unique('token') })
    const form = { From: phoneNumber(), To: number, Body: 'hi', MessageSid: unique('SM') }
    const forgedTwilio = await sendWebhook(request, `/webhooks/sms/twilio/${twilio.id}`, { form }, { 'x-twilio-signature': hmac('sha1', 'guessed', 'x').toString('base64') })
    expect(forgedTwilio.status()).toBe(403)

    const plivo = await connectSms(adminApi, 'plivo', phoneNumber(), { auth_id: unique('MA'), auth_token: unique('token') })
    const forgedPlivo = await sendWebhook(request, `/webhooks/sms/plivo/${plivo.id}`, { form: { From: '447700900000', To: '447700900001', Text: 'hi', MessageUUID: unique('u') } }, {
      'x-plivo-signature-v3': hmac('sha256', 'guessed', 'x').toString('base64'), 'x-plivo-signature-v3-nonce': 'n',
    })
    expect(forgedPlivo.status()).toBe(403)
  })

  test('email: an inbound-parse post without the inbox\'s token @channels @security', async ({ adminApi, request }) => {
    const inbox = await connectEmail(adminApi, `${unique('support')}@e2e.example.com`)
    const json = JSON.stringify({ from: 'mallory@example.com', to: inbox.external_account_id, subject: 'hi', text: 'hi' })
    expect((await sendWebhook(request, `/webhooks/email/${inbox.id}?token=guessed`, { json })).status()).toBe(403)
    expect((await sendWebhook(request, `/webhooks/email/${inbox.id}`, { json })).status()).toBe(403)
  })
})

test.describe('signed events that must not start an AI turn', () => {
  test('a Messenger echo of our own message, a WhatsApp delivery receipt and another bot\'s Slack message @channels', async ({ adminApi, request, agent, llm }) => {
    await llm.script(agent, (s) => s.otherwise().reply('This should never be sent.'))

    // Messenger: Meta echoes the page's own sends back with is_echo.
    const pageId = digits(15)
    const page = await connectMessenger(adminApi, pageId, metaToken(pageId))
    await routeToAgent(adminApi, page.id, agent.id)
    const echo = { object: 'page', entry: [{ id: pageId, messaging: [{ sender: { id: pageId }, recipient: { id: digits(16) }, timestamp: Date.now(), message: { mid: unique('m'), text: 'Hello from us', is_echo: true } }] }] }
    expect((await sendWebhook(request, '/webhooks/meta', { json: JSON.stringify(echo) }, metaSignature(JSON.stringify(echo)))).ok()).toBe(true)

    // WhatsApp: delivery/read receipts arrive as `statuses`, with no messages.
    const number = await connectWhatsAppNumber(adminApi)
    await routeToAgent(adminApi, number.account.id, agent.id)
    const receipt = { object: 'whatsapp_business_account', entry: [{ id: '1', changes: [{ field: 'messages', value: { messaging_product: 'whatsapp', metadata: { phone_number_id: number.phoneNumberId }, statuses: [{ id: 'wamid.x', status: 'read', timestamp: '1', recipient_id: '447700900000' }] } }] }] }
    expect((await sendWebhook(request, '/webhooks/meta', { json: JSON.stringify(receipt) }, metaSignature(JSON.stringify(receipt)))).ok()).toBe(true)

    // Slack: messages posted by a bot (including ours) carry bot_id.
    const workspace = await installSlackWorkspace(adminApi, request)
    await routeToAgent(adminApi, workspace.account.id, agent.id)
    const teamId = workspace.teamId
    const now = String(Math.floor(Date.now() / 1000))
    const botMessage = JSON.stringify({ type: 'event_callback', team_id: teamId, event_id: unique('Ev'), event: { type: 'message', channel_type: 'im', channel: 'D1', bot_id: 'B1', text: 'beep', ts: `${now}.000100` } })
    expect((await sendWebhook(request, '/webhooks/slack', { json: botMessage }, { 'x-slack-request-timestamp': now, 'x-slack-signature': slackSignature(botMessage, now) })).ok()).toBe(true)

    // Each was accepted (a provider would retry a refusal) and none reached the model.
    await expectUnchanged('model calls', async () => (await llm.requests(agent)).length, 5_000)
    expect(await llm.requests(agent)).toHaveLength(0)
  })
})
