import { test, expect, env, orgDomain, setOrgDomain, ApiClient } from '@e2e'

// The org's website is what lets its site call the API. Changing it is org-wide,
// so this runs in the serial `org` project and puts the website back. With
// several backend workers the others learn of a change over Redis a moment
// later, so every check polls.

const OLD_SITE = 'https://old-site.e2e.example'
const NEW_SITE = 'https://new-site.e2e.example'

async function allowedOrigin(api: ApiClient, origin: string): Promise<string | undefined> {
  // A plain request, not a preflight: every CORS layer adds its header to these,
  // so a stale copy of the old origin list would still answer for the old site.
  const response = await api.raw('GET', '/organizations/setup-status', { headers: { Origin: origin } })
  return response.headers()['access-control-allow-origin']
}

let website: string

test.beforeEach(async ({ adminApi, org }) => { website = await orgDomain(adminApi, org.orgId) })

test.afterEach(async ({ adminApi, org }) => { await setOrgDomain(adminApi, org.orgId, website) })

test.describe('organization website and API access', () => {
  test('changing the website moves API access to the new site and revokes the old one @security', async ({ adminApi, org, request }) => {
    const anonymous = new ApiClient(request)

    await setOrgDomain(adminApi, org.orgId, new URL(OLD_SITE).host)
    await expect.poll(() => allowedOrigin(anonymous, OLD_SITE)).toBe(OLD_SITE)

    await setOrgDomain(adminApi, org.orgId, new URL(NEW_SITE).host)
    await expect.poll(() => allowedOrigin(anonymous, NEW_SITE)).toBe(NEW_SITE)
    await expect.poll(() => allowedOrigin(anonymous, OLD_SITE)).toBeUndefined()

    // Saving the same website again, then switching back, still allows only the current site
    await setOrgDomain(adminApi, org.orgId, new URL(NEW_SITE).host)
    await expect.poll(() => allowedOrigin(anonymous, NEW_SITE)).toBe(NEW_SITE)
    await setOrgDomain(adminApi, org.orgId, new URL(OLD_SITE).host)
    await expect.poll(() => allowedOrigin(anonymous, OLD_SITE)).toBe(OLD_SITE)
    await expect.poll(() => allowedOrigin(anonymous, NEW_SITE)).toBeUndefined()
  })
})

test.describe('organization website and sign-in cookies', () => {
  test('an org\'s website can call the API but never with a signed-in user\'s cookies @security', async ({ adminApi, org, request }) => {
    // Any signed-up domain lands in the CORS list, unverified: it must not be
    // able to read the dashboard's cookie-authenticated responses
    await setOrgDomain(adminApi, org.orgId, new URL(NEW_SITE).host)
    const anonymous = new ApiClient(request)
    await expect.poll(() => allowedOrigin(anonymous, NEW_SITE)).toBe(NEW_SITE)

    const simple = await anonymous.raw('GET', '/users/me', { headers: { Origin: NEW_SITE, Cookie: 'access_token=x' } })
    expect(simple.headers()['access-control-allow-origin']).toBe(NEW_SITE)
    expect(simple.headers()['access-control-allow-credentials']).toBeUndefined()

    const preflight = await anonymous.raw('OPTIONS', '/users/me', {
      headers: { Origin: NEW_SITE, 'Access-Control-Request-Method': 'GET' },
    })
    expect(preflight.headers()['access-control-allow-credentials']).toBeUndefined()

    // and the rebuilt CORS layer still lets the dashboard use them
    const dashboard = await anonymous.raw('GET', '/users/me', { headers: { Origin: env.frontendUrl } })
    expect(dashboard.headers()['access-control-allow-origin']).toBe(env.frontendUrl)
    expect(dashboard.headers()['access-control-allow-credentials']).toBe('true')
  })
})
