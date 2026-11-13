import { test, expect, connectJira, disconnectJira, fakeJira, routeTicketsToJira, FakeExternals, IntegrationsPage, unique, AI_REPLY } from '@e2e'

// One Jira site per org, so this runs in the serial `org` project and disconnects afterwards.

interface JiraGrant { access_token: string }
interface JiraSite { id: string; url: string }

test.describe('Jira', () => {
  test.afterEach(async ({ adminApi }) => { await disconnectJira(adminApi) })

  test('an admin connects Jira from Settings and the card links to their site @integrations', async ({ page, request }) => {
    const since = new Date()
    const integrations = new IntegrationsPage(page)
    await integrations.goto()
    await integrations.connect('Jira')
    await expect(page.getByText('Jira connected successfully!')).toBeVisible()

    // The code Atlassian's consent screen sent back was traded with the app's own
    // credentials, and the site is the one that token reaches.
    const externals = new FakeExternals(request)
    const [grant] = (await externals.callsSince(since)).filter((c) => c.provider === 'jira-auth' && c.action === 'token')
    const [resources] = (await externals.callsSince(since)).filter((c) => c.action === 'accessible-resources')
    expect(grant.body).toMatchObject({ grant_type: 'authorization_code', client_id: 'e2e-jira-client-id', redirect_uri: 'http://127.0.0.1:18000/api/v1/jira/callback' })
    expect(resources.headers.authorization).toBe(`Bearer ${(grant.response as JiraGrant).access_token}`)
    const [site] = resources.response as JiraSite[]
    await expect(integrations.card('Jira').getByRole('link', { name: /Visit Jira Site/ })).toHaveAttribute('href', site.url)
  })

  test('the AI files a Jira issue from a chat, in the project the agent is set up for @integrations', async ({ agent, widget, llm, adminApi, request }) => {
    const code = unique('jira-code')
    await connectJira(adminApi, code)
    await routeTicketsToJira(adminApi, agent.id)

    const summary = unique('Refund not received')
    await llm.script(agent, (s) => s
      .when(/refund/i).callTool('create_jira_ticket', { summary, description: 'Charged twice for one order; wants one payment back.', priority: 'High' })
      .thenReply('I have raised this with our billing team.')
      .otherwise().reply('How can I help?'))
    await widget.embed()
    await widget.open()
    await widget.send('My refund never arrived')
    await expect(widget.lastAgentMessage()).toHaveText('I have raised this with our billing team.', AI_REPLY)

    // Jira received the issue in the agent's project and type, at the priority the
    // model chose, sent with this org's token.
    const externals = new FakeExternals(request)
    const [grant] = await externals.calls('jira-auth', 'token', { contains: code })
    const [created] = await externals.calls('jira', 'issue', { contains: summary })
    expect(created.method).toBe('POST')
    expect(created.headers.authorization).toBe(`Bearer ${(grant.response as JiraGrant).access_token}`)
    expect(created.body).toMatchObject({
      fields: { summary, project: { key: fakeJira.projectKey }, issuetype: { id: fakeJira.taskTypeId }, priority: { id: '2' } },
    })

    // The model is told the issue key and its link on the connected site.
    const { key } = created.response as { key: string }
    const toolResults = (await llm.requests(agent)).flatMap((r) => r.toolResults).join('\n')
    expect(toolResults).toContain(`.atlassian.net/browse/${key}`)
  })
})
