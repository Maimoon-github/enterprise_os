import { expect, type Browser } from '@playwright/test'
import { useFakeLlm } from './api/ai'
import type { ApiClient } from './api/client'
import { setAlwaysOpen } from './api/organizations'
import { ensureGroup, ensureUser } from './api/team'
import { disableAutoInvestigation } from './api/tickets'
import { env, seedOrg, seedUsers } from './env'
import { storageStatePath, writeOrgState } from './org-state'
import { LoginPage } from './pages/login.page'

export interface PreparedOrg {
  orgId: string
  /** Signed-in admin seeding client. */
  api: ApiClient
  /** storageState file already saved for the signed-in admin. */
  adminStorageState: string
  /**
   * OSS points the org at the fake LLM itself. Enterprise orgs keep the
   * ChatterMate AI their signup created, which reaches the fake through
   * OPENAI_BASE_URL.
   */
  configureAi: boolean
}

/**
 * Everything both editions' setup projects do once an admin is signed in: make
 * the org deterministic, create Sam Agent and the support group handover needs,
 * save Sam's signed-in state, and write the org contract every spec reads.
 * Idempotent, so it is safe on a database left by an earlier run.
 */
export async function prepareOrg(browser: Browser, org: PreparedOrg): Promise<void> {
  const { api, orgId } = org
  const { admin, humanAgent } = seedUsers

  if (org.configureAi) await useFakeLlm(api)
  await setAlwaysOpen(api, orgId)
  await disableAutoInvestigation(api)
  const sam = await ensureUser(api, { ...humanAgent, role: 'Agent' })
  const supportGroupId = await ensureGroup(api, seedOrg.supportGroup, [sam])

  // Signing in is what marks Sam online — handover needs an online group member.
  const agentContext = await browser.newContext({ baseURL: env.frontendUrl })
  const agentLogin = new LoginPage(await agentContext.newPage())
  await agentLogin.goto()
  await agentLogin.signIn(humanAgent.email, humanAgent.password)
  await expect(agentLogin.page).not.toHaveURL(/\/login/)
  const agentState = storageStatePath('human-agent')
  await agentContext.storageState({ path: agentState })
  await agentContext.close()

  writeOrgState({
    edition: env.edition,
    orgId,
    supportGroupId,
    admin: { ...admin, storageState: org.adminStorageState },
    humanAgent: { ...humanAgent, id: sam.id, storageState: agentState },
  })
}
