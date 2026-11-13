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

Joins the per-org inbox room on the /agent namespace, where live updates
about any of the org's conversations arrive (delivery receipts on
AI-handled chats have no agent of their own to address). Only for people who
can see chats nobody owns — the backend refuses everyone else.
*/

import { onBeforeUnmount, onMounted } from 'vue'
import { socketService } from '@/services/socket'
import { userService } from '@/services/user'
import { permissionChecks } from '@/utils/permissions'

export function useOrgInboxRoom() {
  const orgId = userService.getCurrentUser()?.organization_id
  const room = orgId && permissionChecks.canViewUnassignedChats() ? `org_inbox_${orgId}` : null

  const joinRoom = () => {
    if (room) socketService.emit('join_room', { session_id: room })
  }

  onMounted(() => {
    if (!room) return
    joinRoom()
    socketService.onReconnect(joinRoom)
  })

  onBeforeUnmount(() => {
    if (!room) return
    socketService.emit('leave_room', { session_id: room })
    socketService.offReconnect(joinRoom)
  })
}
