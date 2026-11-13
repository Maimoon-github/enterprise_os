import { test, expect, storageStatePath } from '@e2e'

test.describe('signed out', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('admin signs in and lands on the dashboard @smoke @auth', async ({ loginPage, org, page }) => {
    await loginPage.goto()
    await loginPage.signIn(org.admin.email, org.admin.password)
    await expect(page).toHaveURL(/\/ai-agents/)
  })

  test('a wrong password keeps you on the sign-in page with an error @auth', async ({ loginPage, org, page }) => {
    await loginPage.goto()
    await loginPage.signIn(org.admin.email, 'not-the-password')
    await expect(loginPage.error).toHaveText('Incorrect email or password')
    await expect(page).toHaveURL(/\/login/)
  })

  test('signing out returns to the sign-in page @auth', async ({ loginPage, dashboard, org, page }) => {
    // A fresh session, not the shared admin state — logging out must not affect other tests.
    await loginPage.goto()
    await loginPage.signIn(org.admin.email, org.admin.password)
    await expect(page).toHaveURL(/\/ai-agents/)
    await dashboard.logout()
    await page.goto('/conversations')
    await expect(page).toHaveURL(/\/login/)
  })
})

test.describe('as a human agent', () => {
  // A path, not a read: spec files load before the setup project writes the state.
  test.use({ storageState: storageStatePath('human-agent') })

  test('the Agent role cannot open AI settings @auth', async ({ dashboard, page }) => {
    await page.goto('/settings/ai-config')
    await expect(dashboard.accessDenied).toBeVisible()
  })
})
