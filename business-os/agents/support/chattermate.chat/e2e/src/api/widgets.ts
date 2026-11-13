import type { ApiClient } from './client'

export interface Widget {
  id: string
}

export async function createWidget(api: ApiClient, agentId: string, name: string): Promise<Widget> {
  const created = await api.post<{ id: string }>('/widgets', { data: { name, agent_id: agentId } })
  return { id: String(created.id) }
}

/**
 * The widget's first request on a page, as a visitor's browser on `origin`
 * sends it (through our nginx, which appends the client IP). `api` should be
 * anonymous, like a visitor.
 */
export async function loadWidgetFrom(api: ApiClient, widgetId: string, origin: string, visitorIp: string): Promise<void> {
  // The endpoint serves the widget's HTML, not JSON: only the status matters
  const response = await api.raw('GET', `/widgets/${widgetId}/data`, {
    headers: { Origin: origin, 'X-Forwarded-For': visitorIp },
  })
  if (!response.ok()) throw new Error(`widget load from ${origin} → ${response.status()}`)
}

/** Limit where the widget may be embedded; an empty list allows any site. */
export async function setAllowedDomains(api: ApiClient, widgetId: string, domains: string[]): Promise<string[]> {
  const saved = await api.put<{ allowed_domains: string[] }>(`/widgets/${widgetId}/embed-settings`, { data: { allowed_domains: domains } })
  return saved.allowed_domains
}

/**
 * The framed widget starting on a visitor's page at `origin`: what it sends to
 * /bootstrap once the host page has handed it over. `api` should be anonymous.
 */
export async function openFramedWidgetFrom(api: ApiClient, widgetId: string, origin: string, visitorIp: string): Promise<void> {
  const response = await api.raw('POST', `/widgets/${widgetId}/bootstrap`, {
    data: { host_origin: origin },
    headers: { 'X-Forwarded-For': visitorIp },
  })
  if (!response.ok()) throw new Error(`widget bootstrap from ${origin} → ${response.status()}`)
}

/** A page at `origin` framing the widget, as the browser requests it. Only the status matters. */
export async function requestFrameFrom(api: ApiClient, widgetId: string, origin: string): Promise<void> {
  const response = await api.raw('GET', `/widgets/${widgetId}/frame`, {
    headers: { 'Sec-Fetch-Dest': 'iframe', Referer: `${origin}/` },
  })
  if (!response.ok()) throw new Error(`widget frame for ${origin} → ${response.status()}`)
}

/**
 * A frame request already sent on to the frame host (`cm_hop=1`) that arrived on the
 * API's own host instead, where the dashboard's sign-in cookies live: what a
 * misrouted proxy, or someone crafting the URL, would get.
 */
export async function requestFrameAfterHop(api: ApiClient, widgetId: string): Promise<{ status: number; servesWidget: boolean }> {
  const response = await api.raw('GET', `/widgets/${widgetId}/frame`, {
    params: { host: 1, cm_hop: 1 },
    headers: { 'Sec-Fetch-Dest': 'iframe' },
    maxRedirects: 0,
  })
  const page = await response.text()
  return { status: response.status(), servesWidget: page.includes('/assets/widget.js') || page.includes('__CM_FRAME__') }
}
