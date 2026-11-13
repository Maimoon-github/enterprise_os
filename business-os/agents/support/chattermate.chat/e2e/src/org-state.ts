import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { env } from './env'

/**
 * The contract between an edition's setup project and every spec: who the org is
 * and where the signed-in browser states live. Specs only READ this, so the same
 * OSS spec runs unchanged whichever edition's setup wrote it.
 */
export interface OrgState {
  edition: 'oss' | 'enterprise'
  orgId: string
  supportGroupId: string
  admin: { email: string; password: string; name: string; storageState: string }
  humanAgent: { id: string; email: string; password: string; name: string; storageState: string }
}

const file = join(env.authDir, 'org.json')

export const storageStatePath = (role: string) => join(env.authDir, `${role}.json`)

export function writeOrgState(state: OrgState): void {
  mkdirSync(env.authDir, { recursive: true })
  writeFileSync(file, JSON.stringify(state, null, 2))
}

let cached: OrgState | undefined

export function readOrgState(): OrgState {
  if (!cached) {
    try {
      cached = JSON.parse(readFileSync(file, 'utf8')) as OrgState
    } catch {
      throw new Error(`${file} is missing — run the 'setup' project first (it is a dependency of every project)`)
    }
  }
  return cached
}
