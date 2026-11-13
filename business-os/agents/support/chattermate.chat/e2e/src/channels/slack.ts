import type { APIRequestContext } from '@playwright/test'
import { installSlack, listChannelAccounts, routeToAgent, type ChannelAccount } from '../api/channels'
import type { ApiClient } from '../api/client'
import { env } from '../env'
import { FakeExternals } from '../fakes/externals'
import { unique } from '../support/ids'
import { step } from '../support/step'
import { Chat, digits, hmac, postWebhook, sentWith, type ChannelConnector } from './chat'

interface OAuthAnswer { team: { id: string }; access_token: string }
interface SlackPost { channel: string; text: string }

/** The "typing…" placeholder the backend posts and then edits into the reply. */
const TYPING_PLACEHOLDER = '_typing…_'

/** Slack's v0 request signature over `v0:<timestamp>:<body>`. */
export function slackSignature(json: string, timestamp: string): string {
  return `v0=${hmac('sha256', env.channelSecrets.slack, `v0:${timestamp}:${json}`).toString('hex')}`
}

export interface SlackWorkspace {
  account: ChannelAccount
  teamId: string
  botToken: string
}

/** Installs the Slack app in a fresh workspace through the OAuth flow. */
export async function installSlackWorkspace(api: ApiClient, request: APIRequestContext): Promise<SlackWorkspace> {
  const externals = new FakeExternals(request)
  const code = unique('slack-code')
  await installSlack(api, code)
  // The workspace is whatever Slack answered the code exchange with.
  const exchange = (await externals.calls('slack', 'oauth.v2.access', { contains: code }))[0]
  const answer = exchange?.response as OAuthAnswer | undefined
  const account = (await listChannelAccounts(api)).find((a) => a.channel_type === 'slack' && a.external_account_id === answer?.team.id)
  if (!answer || !account) throw new Error(`no Slack account after the OAuth callback for code ${code}`)
  return { account, teamId: answer.team.id, botToken: answer.access_token }
}

/** A Slack workspace installed through the OAuth flow; customers DM the bot. */
export const slack: ChannelConnector = ({ api, request, agentId }) =>
  step('Install the Slack app in a workspace', async () => {
    const { account, teamId, botToken } = await installSlackWorkspace(api, request)
    await routeToAgent(api, account.id, agentId)
    const externals = new FakeExternals(request)

    return {
      chatWith(customerName) {
        const user = `U${digits(10)}`
        const channel = `D${digits(10)}`
        return new Chat('Slack', customerName, async (text) => {
          const ts = `${Math.floor(Date.now() / 1000)}.${digits(6)}`
          const json = JSON.stringify({
            type: 'event_callback',
            team_id: teamId,
            event_id: `Ev${digits(10)}`,
            event: { type: 'message', channel_type: 'im', channel, user, text, ts },
          })
          const timestamp = String(Math.floor(Date.now() / 1000))
          await postWebhook(request, '/webhooks/slack', { json }, { 'x-slack-request-timestamp': timestamp, 'x-slack-signature': slackSignature(json, timestamp) })
        }, async () => (await externals.calls('slack', undefined, { contains: channel }))
          // A reply is the placeholder edited by chat.update, or a fresh chat.postMessage,
          // sent with this workspace's bot token.
          .filter((c) => (c.action === 'chat.update' || c.action === 'chat.postMessage') && c.status === 200 && sentWith(c, botToken))
          .map((c) => c.body as SlackPost)
          .filter((b) => b.channel === channel && b.text !== TYPING_PLACEHOLDER)
          .map((b) => b.text))
      },
    }
  })
