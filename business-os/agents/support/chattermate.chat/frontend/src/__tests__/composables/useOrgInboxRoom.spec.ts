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

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

const socket = vi.hoisted(() => ({
  emit: vi.fn(),
  onReconnect: vi.fn(),
  offReconnect: vi.fn(),
}))
const user = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/services/socket', () => ({ socketService: socket }))
vi.mock('@/services/user', () => ({ userService: { getCurrentUser: () => user.current } }))

import { useOrgInboxRoom } from '@/composables/useOrgInboxRoom'

const withPermissions = (...names: string[]) => ({
  organization_id: 'org-1',
  role: { permissions: names.map((name) => ({ name })) }
})

const mountRoom = () =>
  mount(defineComponent({ setup: () => { useOrgInboxRoom(); return () => h('div') } }))

describe('useOrgInboxRoom', () => {
  beforeEach(() => vi.clearAllMocks())

  it('joins the org room, rejoins on reconnect, leaves on unmount', () => {
    user.current = withPermissions('view_unassigned_chats')
    const wrapper = mountRoom()

    expect(socket.emit).toHaveBeenCalledWith('join_room', { session_id: 'org_inbox_org-1' })
    expect(socket.onReconnect).toHaveBeenCalledOnce()

    wrapper.unmount()
    expect(socket.emit).toHaveBeenCalledWith('leave_room', { session_id: 'org_inbox_org-1' })
    expect(socket.offReconnect).toHaveBeenCalledOnce()
  })

  it('stays out when the user cannot see chats nobody owns', () => {
    user.current = withPermissions('view_assigned_chats')
    mountRoom().unmount()
    expect(socket.emit).not.toHaveBeenCalled()
  })
})
