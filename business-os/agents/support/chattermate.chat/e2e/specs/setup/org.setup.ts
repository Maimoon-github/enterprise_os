import { test as setup, expect } from '@playwright/test'
import { login } from '../../src/api/auth'
import { ApiClient } from '../../src/api/client'
import { isSetUp } from '../../src/api/organizations'
import { seedOrg, seedUsers } from '../../src/env'
import { storageStatePath } from '../../src/org-state'
import { prepareOrg } from '../../src/org-setup'
import { LoginPage } from '../../src/pages/login.page'
import { SetupPage } from '../../src/pages/setup.page'

// OSS edition setup. Runs once per run, before every other project, and writes the
// org contract (src/org-state.ts) that all specs read.
//
// Idempotent: on a fresh database it goes through the real first-run form (which is
// also the test that the form works); on a database left by an earlier run it signs in.

setup('organization, AI and support team are ready', async ({ page, request, browser }) => {
  const anonymous = new ApiClient(request)
  const { admin } = seedUsers

  if (await isSetUp(anonymous)) {
    const loginPage = new LoginPage(page)
    await loginPage.goto()
    await loginPage.signIn(admin.email, admin.password)
    await expect(page).not.toHaveURL(/\/login/)
  } else {
    const setupPage = new SetupPage(page)
    await setupPage.goto()
    await setupPage.createOrganization({
      orgName: seedOrg.name,
      domain: seedOrg.domain,
      adminName: admin.name,
      adminEmail: admin.email,
      adminPassword: admin.password,
    })
  }
  const adminStorageState = storageStatePath('admin')
  await page.context().storageState({ path: adminStorageState })

  const session = await login(anonymous, admin.email, admin.password)
  await prepareOrg(browser, {
    orgId: session.organizationId,
    api: anonymous.withToken(session.token),
    adminStorageState,
    configureAi: true,
  })
})
