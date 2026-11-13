import type { ApiClient } from './client'

export interface User {
  id: string
  email: string
  full_name: string
}

interface Role {
  id: number
  name: string
}

interface Group {
  id: string
  name: string
  users?: User[]
}

export async function roleId(api: ApiClient, name: string): Promise<number> {
  const roles = await api.get<Role[]>('/roles')
  const role = roles.find((r) => r.name === name)
  if (!role) throw new Error(`no role named '${name}' (have: ${roles.map((r) => r.name).join(', ')})`)
  return role.id
}

export interface NewUser {
  email: string
  name: string
  password: string
  role: string
  /** The user form's chat-scope toggles; omitted = the role's own scope. */
  seeAllAiChats?: boolean
  seeAllOrgChats?: boolean
}

export async function createUser(api: ApiClient, user: NewUser): Promise<User> {
  const created = await api.post<User>('/users', {
    data: {
      email: user.email, full_name: user.name, password: user.password, role_id: await roleId(api, user.role),
      see_all_ai_chats: user.seeAllAiChats, see_all_org_chats: user.seeAllOrgChats,
    },
  })
  return { ...created, id: String(created.id) }
}

/** A new group with `members`. */
export async function createGroup(api: ApiClient, name: string, members: User[]): Promise<string> {
  const group = await api.post<Group>('/groups', { data: { name } })
  for (const member of members) await api.post(`/groups/${group.id}/users/${member.id}`)
  return String(group.id)
}

/** Creates the user unless one with that email exists — setup reruns against a reused DB. */
export async function ensureUser(
  api: ApiClient,
  user: NewUser,
): Promise<User> {
  const existing = (await api.get<User[]>('/users')).find((u) => u.email === user.email)
  if (existing) return { ...existing, id: String(existing.id) }
  return createUser(api, user)
}

export async function ensureGroup(api: ApiClient, name: string, members: User[]): Promise<string> {
  const groups = await api.get<Group[]>('/groups')
  const group = groups.find((g) => g.name === name) ?? (await api.post<Group>('/groups', { data: { name } }))
  const memberIds = new Set((group.users ?? []).map((u) => String(u.id)))
  for (const member of members) {
    if (!memberIds.has(member.id)) await api.post(`/groups/${group.id}/users/${member.id}`)
  }
  return String(group.id)
}
