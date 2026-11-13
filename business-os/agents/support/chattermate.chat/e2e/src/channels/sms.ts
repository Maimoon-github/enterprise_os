import { connectSms, routeToAgent } from '../api/channels'
import { env } from '../env'
import { FakeExternals } from '../fakes/externals'
import { unique } from '../support/ids'
import { step } from '../support/step'
import { Chat, hmac, phoneNumber, postWebhook, samePhone, type ChannelConnector } from './chat'

// SMS webhooks are per account and signed over the public webhook URL, which the
// backend rebuilds from BACKEND_URL — the same URL the test posts to.

interface TwilioSend { From: string; To: string; Body: string }
interface PlivoSend { src: string; dst: string; text: string }

/** Twilio: X-Twilio-Signature = base64(HMAC-SHA1(auth token, url + sorted key/value pairs)). */
export const twilio: ChannelConnector = ({ api, request, agentId }) =>
  step('Connect a Twilio number', async () => {
    const authToken = unique('twilio-token')
    const businessNumber = phoneNumber()
    const accountSid = unique('AC')
    const account = await connectSms(api, 'twilio', businessNumber, { account_sid: accountSid, auth_token: authToken })
    await routeToAgent(api, account.id, agentId)
    const externals = new FakeExternals(request)
    const path = `/webhooks/sms/twilio/${account.id}`

    return {
      chatWith(customerName) {
        const customerNumber = phoneNumber()
        return new Chat('SMS (Twilio)', customerName, async (text) => {
          const form = { From: customerNumber, To: businessNumber, Body: text, MessageSid: unique('SM') }
          const signed = `${env.apiUrl}${path}` + Object.keys(form).sort().map((k) => k + form[k as keyof typeof form]).join('')
          await postWebhook(request, path, { form }, { 'x-twilio-signature': hmac('sha1', authToken, signed).toString('base64') })
        }, async () => (await externals.calls('twilio', 'Messages.json', { contains: accountSid }))
          // Sent through this account (its SID in the path) from this number.
          .filter((c) => c.status === 200 && c.path.includes(`/Accounts/${accountSid}/`))
          .map((c) => c.body as TwilioSend)
          .filter((b) => samePhone(b.To, customerNumber) && samePhone(b.From, businessNumber))
          .map((b) => b.Body))
      },
    }
  })

/** Plivo: X-Plivo-Signature-V3 = base64(HMAC-SHA256(auth token, url + nonce)). */
export const plivo: ChannelConnector = ({ api, request, agentId }) =>
  step('Connect a Plivo number', async () => {
    const authToken = unique('plivo-token')
    const businessNumber = phoneNumber()
    const authId = unique('MA')
    const account = await connectSms(api, 'plivo', businessNumber, { auth_id: authId, auth_token: authToken })
    await routeToAgent(api, account.id, agentId)
    const externals = new FakeExternals(request)
    const path = `/webhooks/sms/plivo/${account.id}`

    return {
      chatWith(customerName) {
        // Plivo sends numbers without the leading +.
        const customerNumber = phoneNumber().slice(1)
        return new Chat('SMS (Plivo)', customerName, async (text) => {
          const nonce = unique('nonce')
          await postWebhook(request, path, {
            form: { From: customerNumber, To: businessNumber.slice(1), Text: text, MessageUUID: unique('uuid') },
          }, {
            'x-plivo-signature-v3': hmac('sha256', authToken, `${env.apiUrl}${path}${nonce}`).toString('base64'),
            'x-plivo-signature-v3-nonce': nonce,
          })
        }, async () => (await externals.calls('plivo', 'Message', { contains: authId }))
          .filter((c) => c.status === 200 && c.path.includes(`/Account/${authId}/`))
          .map((c) => c.body as PlivoSend)
          .filter((b) => samePhone(b.dst, customerNumber) && samePhone(b.src, businessNumber))
          .map((b) => b.text))
      },
    }
  })
