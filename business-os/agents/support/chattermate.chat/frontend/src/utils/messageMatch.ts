/*
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

import type { Message } from '@/types/chat'

/**
 * An id for a message the inbox is about to send, so the backend's events
 * about it can be matched exactly. crypto.randomUUID only exists in secure
 * contexts — a self-hosted dashboard served over plain http on a LAN address
 * has none — so fall back to a time-plus-random id, unique enough for one tab.
 */
export function newClientId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

/** The ways a live event can name a message in the open conversation. */
export interface MessageRef {
  /** The stored chat_history row id */
  messageId?: number | null
  /** The id the inbox gave a message it sent, before the row id is known */
  clientId?: string | null
  /** The channel's id for the message (WhatsApp wamid) */
  externalId?: string | null
}

/**
 * The message an event (delivery receipt, delivery error, stored ack) is
 * about — matched exactly, never guessed: a receipt that names no message on
 * screen is ignored and shows after the next refetch instead.
 */
export function findMessage(messages: Message[], ref: MessageRef): Message | undefined {
  return messages.find(m =>
    (ref.messageId != null && m.id === ref.messageId) ||
    (!!ref.clientId && m.client_id === ref.clientId) ||
    (!!ref.externalId && m.external_message_id === ref.externalId))
}
