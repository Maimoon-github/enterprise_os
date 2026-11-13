import type { ApiClient } from './client'

export interface Person {
  id: string
  name: string | null
  email: string | null
  phone: string | null
  lead_stage: 'visitor' | 'lead' | 'customer'
}

/** The one person whose email or phone matches `query` (People search). */
export async function findPerson(api: ApiClient, query: string): Promise<Person> {
  const { items } = await api.get<{ items: Person[] }>('/people', { params: { search: query } })
  if (items.length !== 1) throw new Error(`expected one person matching ${query}, found ${items.length}`)
  return api.get<Person>(`/people/${items[0].id}`)
}
