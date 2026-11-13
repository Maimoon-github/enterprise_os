import { test, expect, env, ApiClient, ChatWidget, requestFrameAfterHop, AI_REPLY } from '@e2e'

// The widget runs in a frame on a host of its own (WIDGET_FRAME_URL), never where the
// dashboard's sign-in cookies live: a page in the frame must not ride a signed-in
// user's session. On the stack that host is localhost:18000; the dashboard and its
// cookies are on 127.0.0.1.

test.describe('the widget frame host', () => {
  // eslint-disable-next-line playwright/no-skipped-test -- a capability of the stack, not a broken test
  test.skip(!env.widgetFrameUrl, 'The stack frames the widget on the API\'s own origin (E2E_WIDGET_FRAME_URL is empty)')

  test('a signed-in dashboard user chats on a customer site without their cookies reaching the widget @security', async ({ page, agent, widget, llm }) => {
    // `page` is the admin's browser, signed in to the dashboard: its cookies are on 127.0.0.1
    expect((await page.context().cookies()).map((c) => `${c.name}@${c.domain}`)).toContain('access_token@127.0.0.1')
    await llm.script(agent, (s) => s.otherwise().reply('Hello, whoever you are.'))
    const visitor = new ChatWidget(page, widget.widgetId)
    const frameRequests = await visitor.recordFrameRequests()

    await visitor.embed()
    await visitor.open()
    await visitor.send('Hi')
    await expect(visitor.lastAgentMessage()).toHaveText('Hello, whoever you are.', AI_REPLY)

    expect(visitor.frameOrigin()).toBe(env.widgetFrameUrl)
    const requests = frameRequests()
    expect(requests.map((r) => r.kind)).toEqual(expect.arrayContaining(['start', 'socket']))
    for (const request of requests) {
      expect(new URL(request.url).host, request.url).toBe(new URL(env.widgetFrameUrl!).host)
      expect(request.cookie, `${request.kind} request ${request.url}`).toBeNull()
    }
    // Nothing to send there either: the browser keeps no cookie for the frame host
    expect(await visitor.cookiesOnFrameHost()).toEqual([])
  })

  test('a frame request that comes back to a cookie host is refused and serves no widget @security', async ({ widget, request }) => {
    const answer = await requestFrameAfterHop(new ApiClient(request), widget.widgetId)

    expect(answer.status).toBe(421)
    expect(answer.servesWidget).toBe(false)
  })
})
