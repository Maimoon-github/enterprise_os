import type { ApiClient } from './client'
import type { Schemas } from './types'

export type ChatOverview = Schemas['ChatOverviewResponse']

/** The org's conversations with one AI agent, newest first (admin view). */
export async function chatsWithAgent(api: ApiClient, agentId: string): Promise<ChatOverview[]> {
  return api.get<ChatOverview[]>('/chats/recent', { params: { agent_id: agentId, limit: 100 } })
}

export type ChatMessage = Schemas['Message']

/** Every stored message in one conversation, oldest first (admin view). */
export async function chatMessages(api: ApiClient, sessionId: string): Promise<ChatMessage[]> {
  return (await api.get<Schemas['ChatDetailResponse']>(`/chats/${sessionId}`)).messages
}
