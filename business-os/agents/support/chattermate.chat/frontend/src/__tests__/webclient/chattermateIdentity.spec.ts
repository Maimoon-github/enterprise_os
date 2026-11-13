/*
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  BASE_URL, FRAME_ORIGIN, WIDGET_ID,
  api, bringUp, cleanupPage, flush, frame, frames, fromFrame, handshake,
  loadLoader, resetPage, spyOnFrame, tokenFor,
} from './loaderHarness'

/**
 * Keeping an identified visitor identified, from the embed loader's side.
 *
 * A signed-in visitor who starts a new chat must stay signed in, the host page has to
 * be told when a conversation is created, and re-authenticating the same visitor must
 * not cost them the chat they are in.
 */
describe('ChatterMate identity continuity', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    resetPage()
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(cleanupPage)

  describe('conversations', () => {
    it('reports a new conversation to the host page', async () => {
      await loadLoader()
      bringUp()
      const created = vi.fn()
      api().on('chatCreated', created)

      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-1', authenticated: true, created: true })

      expect(created).toHaveBeenCalledWith({ sessionId: 's-1', authenticated: true })
    })

    it('says when the new conversation is no longer the identified visitor', async () => {
      await loadLoader()
      bringUp()
      const created = vi.fn()
      api().on('chatCreated', created)

      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-2', authenticated: false, created: true })

      expect(created).toHaveBeenCalledWith({ sessionId: 's-2', authenticated: false })
    })

    it('stays quiet when the frame merely reconnects to the conversation in progress', async () => {
      await loadLoader()
      bringUp()
      const created = vi.fn()
      api().on('chatCreated', created)

      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-3', authenticated: true, created: false })

      expect(created).not.toHaveBeenCalled()
    })
  })

  describe('an identity that expires while the chat is open', () => {
    it('asks the host for a token and hands it to the live frame', async () => {
      const replacement = tokenFor('cust-1', 'fresh')
      ;(window as any).chattermateConfig = { tokenProvider: () => Promise.resolve(replacement) }
      await loadLoader()
      bringUp()
      const expired = vi.fn()
      api().on('identityExpired', expired)
      const post = spyOnFrame()
      const before = frame()

      fromFrame({ type: 'IDENTITY_EXPIRED' })
      await flush()

      expect(expired).toHaveBeenCalled()
      expect(post).toHaveBeenCalledWith({ type: 'TOKEN_REFRESH', token: replacement }, FRAME_ORIGIN)
      expect(localStorage.getItem('ctid')).toBe(replacement)
      // The visitor is looking at a conversation; fixing the token must not take it away.
      expect(frame()).toBe(before)
    })

    it('lets the frame carry on anonymously when the host has no tokenProvider', async () => {
      await loadLoader()
      bringUp()
      const post = spyOnFrame()

      fromFrame({ type: 'IDENTITY_EXPIRED' })
      await flush()

      expect(post).toHaveBeenCalledWith({ type: 'IDENTITY_UNAVAILABLE' }, FRAME_ORIGIN)
    })

    it('survives a tokenProvider that throws', async () => {
      ;(window as any).chattermateConfig = { tokenProvider: () => Promise.reject(new Error('no session')) }
      await loadLoader()
      bringUp()
      vi.spyOn(console, 'error').mockImplementation(() => {})
      const post = spyOnFrame()

      fromFrame({ type: 'IDENTITY_EXPIRED' })
      await flush()

      expect(frames()).toHaveLength(1)
      expect(post).toHaveBeenCalledWith({ type: 'IDENTITY_UNAVAILABLE' }, FRAME_ORIGIN)
    })

    it('asks the host only once per load, so a bad token cannot loop', async () => {
      const provider = vi.fn().mockResolvedValue(tokenFor('cust-1', 'stale'))
      ;(window as any).chattermateConfig = { tokenProvider: provider }
      await loadLoader()
      bringUp()

      fromFrame({ type: 'IDENTITY_EXPIRED' })
      await flush()
      fromFrame({ type: 'IDENTITY_EXPIRED' })
      await flush()

      expect(provider).toHaveBeenCalledTimes(1)
    })
  })

  describe('a frame that refuses to start', () => {
    it('re-identifies through the tokenProvider when the stored identity has lapsed', async () => {
      const fresh = tokenFor('cust-1', 'fresh')
      ;(window as any).chattermateToken = tokenFor('cust-1', 'old')
      ;(window as any).chattermateConfig = { tokenProvider: () => Promise.resolve(fresh) }
      await loadLoader()
      handshake()
      const expired = vi.fn()
      api().on('identityExpired', expired)
      const first = frame()

      fromFrame({ type: 'WIDGET_ERROR', code: 'identity_expired' })
      await flush()

      expect(expired).toHaveBeenCalled()
      expect(frame()).not.toBe(first)
      expect(handshake()?.message.token).toBe(fresh)
    })

    it('falls back to anonymous when nobody can renew a lapsed identity', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      handshake()

      fromFrame({ type: 'WIDGET_ERROR', code: 'identity_expired' })
      await flush()

      expect(localStorage.getItem('ctid')).toBeNull()
      expect(handshake()?.message.token).toBeNull()
    })

    it('does not loop when the renewed identity is refused too', async () => {
      const provider = vi.fn().mockResolvedValue(tokenFor('cust-1', 'still-bad'))
      ;(window as any).chattermateToken = tokenFor('cust-1', 'old')
      ;(window as any).chattermateConfig = { tokenProvider: provider }
      await loadLoader()
      handshake()

      fromFrame({ type: 'WIDGET_ERROR', code: 'identity_expired' })
      await flush()
      handshake()
      fromFrame({ type: 'WIDGET_ERROR', code: 'identity_expired' })
      await flush()

      expect(provider).toHaveBeenCalledTimes(1)
      // Second refusal: start over as an anonymous visitor rather than give up.
      expect(handshake()?.message.token).toBeNull()
    })

    it('shows the configuration error when the agent only talks to identified visitors', async () => {
      localStorage.setItem('ctid', 'tok-anon')
      await loadLoader()
      handshake()

      fromFrame({ type: 'WIDGET_ERROR', code: 'token_required' })

      expect(document.querySelector('.chattermate-error-ui')?.textContent).toContain('not currently configured')
      expect(frames()).toHaveLength(0)
      expect(localStorage.getItem('ctid')).toBeNull()
    })

    it('says chat is unavailable for any other failure', async () => {
      await loadLoader()
      handshake()

      fromFrame({ type: 'WIDGET_ERROR', code: 'unavailable' })

      expect(document.querySelector('.chattermate-error-ui')?.textContent).toContain('Chat is unavailable right now')
    })

    it.each(['javascript:alert(1)//', 'data:text/html,<script>alert(1)</script>//'])(
      'never frames an API base that isn\'t a web address (%s)', async (base) => {
        ;(window as any).chattermateBaseUrl = base
        await loadLoader()

        expect(frames()).toHaveLength(0)
        expect(document.querySelector('.chattermate-error-ui')?.textContent).toContain('not currently configured')
      })

    it('frames the widget under a web API base', async () => {
      await loadLoader()

      expect(frame().src).toBe(`${BASE_URL}/widgets/${WIDGET_ID}/frame?host=1`)
    })

    it('tries again when the visitor opens the chat after it was unavailable', async () => {
      await loadLoader()
      handshake()
      fromFrame({ type: 'WIDGET_ERROR', code: 'unavailable' })
      expect(frames()).toHaveLength(0)

      api().open()

      expect(document.querySelector('.chattermate-error-ui')).toBeNull()
      expect(frames()).toHaveLength(1)
    })

    it('tries only once per failure, and not after a configuration error', async () => {
      await loadLoader()
      handshake()
      fromFrame({ type: 'WIDGET_ERROR', code: 'token_required' })

      api().open()
      api().close()
      api().open()

      expect(document.querySelector('.chattermate-error-ui')?.textContent).toContain('not currently configured')
      expect(frames()).toHaveLength(0)
    })
  })

  describe('switching visitor', () => {
    it('swaps a fresher token for the same visitor in place', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1', 'a')
      await loadLoader()
      bringUp()
      const post = spyOnFrame()
      const before = frame()
      const rotated = tokenFor('cust-1', 'b')

      api().identify(rotated)
      await flush()

      expect(post).toHaveBeenCalledWith({ type: 'TOKEN_REFRESH', token: rotated }, FRAME_ORIGIN)
      expect(frame()).toBe(before)
      expect(localStorage.getItem('ctid')).toBe(rotated)
    })

    it('still rebuilds the frame for a different visitor', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      const before = frame()

      api().identify(tokenFor('cust-2'))
      await flush()

      expect(frame()).not.toBe(before)
    })

    it('has the frame close the conversation it leaves behind, then rebuilds', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      bringUp()
      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-9', authenticated: true, created: true })
      const post = spyOnFrame()
      const before = frame()

      api().logout()
      await flush()

      // The frame holds the outgoing visitor's token, so it closes their session
      expect(post).toHaveBeenCalledWith({ type: 'END_CHAT', sessionId: 's-9' }, FRAME_ORIGIN)
      expect(frame()).toBe(before)
      expect(fetchMock).not.toHaveBeenCalled()

      fromFrame({ type: 'END_CHAT_DONE' })
      expect(frame()).not.toBe(before)
      expect(handshake()?.message.token).toBeNull()
    })

    it('does not wait for long on a frame that never answers', async () => {
      vi.useFakeTimers()
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader({ fakeTimers: true })
      bringUp()
      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-9', authenticated: true, created: true })
      const before = frame()

      api().logout()
      await vi.advanceTimersByTimeAsync(999)
      expect(frame()).toBe(before)

      await vi.advanceTimersByTimeAsync(1)
      expect(frame()).not.toBe(before)
    })

    it('rebuilds once when the visitor changes twice while the frame is closing up', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      bringUp()
      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-9', authenticated: true, created: true })
      const before = frame()

      api().identify(tokenFor('cust-2'))
      api().identify(tokenFor('cust-3'))
      await flush()
      expect(frame()).toBe(before)

      fromFrame({ type: 'END_CHAT_DONE' })
      const after = frame()
      expect(after).not.toBe(before)
      // …as the latest visitor
      expect(handshake()?.message.token).toBe(tokenFor('cust-3'))
    })

    it('rebuilds straight away when the frame never got a conversation going', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      bringUp()
      const post = spyOnFrame()
      const before = frame()

      api().logout()
      await flush()

      expect(post.mock.calls.some(([m]) => (m as any).type === 'END_CHAT')).toBe(false)
      expect(frame()).not.toBe(before)
    })

    it('rebuilds straight away when the frame has not said hello yet', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      const before = frame()

      api().logout()
      await flush()

      expect(frame()).not.toBe(before)
    })
  })

  describe('identity given while the frame is starting', () => {
    it('starts the frame again with it once it has mounted, rather than mid-start', async () => {
      // Handing it over while the widget is still starting raced its own start-up
      ;(window as any).chattermateToken = tokenFor('cust-1', 'a')
      await loadLoader()
      handshake()
      const starting = frame()
      const fresher = tokenFor('cust-1', 'b')

      api().identify(fresher)
      expect(frame()).toBe(starting)

      fromFrame({ type: 'WIDGET_READY' })
      expect(frame()).not.toBe(starting)
      expect(handshake()?.message.token).toBe(fresher)
    })

    it('goes in the hello answer when the frame has not said hello yet', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1', 'a')
      await loadLoader()
      const fresher = tokenFor('cust-1', 'b')

      api().identify(fresher)
      expect(handshake()?.message.token).toBe(fresher)

      const post = spyOnFrame()
      fromFrame({ type: 'WIDGET_READY' })
      expect(post.mock.calls.some(([m]) => (m as any).type === 'TOKEN_REFRESH')).toBe(false)
    })

    it('starts over with it when the token the frame began with had lapsed', async () => {
      // Without a tokenProvider, recovering would throw the fresh token away
      ;(window as any).chattermateToken = tokenFor('cust-1', 'yesterday')
      await loadLoader()
      handshake()
      const fresh = tokenFor('cust-1', 'today')
      api().identify(fresh)
      const first = frame()

      fromFrame({ type: 'WIDGET_ERROR', code: 'identity_expired' })
      await flush()

      expect(frame()).not.toBe(first)
      expect(handshake()?.message.token).toBe(fresh)
      expect(localStorage.getItem('ctid')).toBe(fresh)
    })
  })

  describe('while the outgoing visitor\'s frame closes up', () => {
    async function closingUp() {
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      bringUp()
      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-9', authenticated: true, created: true })
      const outgoing = frame()
      api().logout()
      await flush()
      return outgoing
    }

    it('keeps its token news from bringing the logged-out visitor back', async () => {
      const outgoing = await closingUp()

      fromFrame({ type: 'TOKEN_UPDATE', token: tokenFor('cust-1', 'rotated') })
      fromFrame({ type: 'END_CHAT_DONE' })

      expect(frame()).not.toBe(outgoing)
      expect(localStorage.getItem('ctid')).toBeNull()
      expect(handshake()?.message.token).toBeNull()
    })

    it('ignores a session it reports late', async () => {
      await closingUp()
      const created = vi.fn()
      api().on('chatCreated', created)
      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-10', authenticated: true, created: true })
      expect(created).not.toHaveBeenCalled()
    })

    it('sends a same-visitor token to the rebuilt frame, not the outgoing one', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1', 'a')
      await loadLoader()
      bringUp()
      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-9', authenticated: true, created: true })
      api().identify(tokenFor('cust-2'))
      await flush()
      const post = spyOnFrame()

      const later = tokenFor('cust-2', 'b')
      api().identify(later)
      expect(post.mock.calls.some(([m]) => (m as any).type === 'TOKEN_REFRESH')).toBe(false)

      fromFrame({ type: 'END_CHAT_DONE' })
      expect(handshake()?.message.token).toBe(later)
    })

    it('rebuilds once when reload() lands in the middle', async () => {
      vi.useFakeTimers()
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader({ fakeTimers: true })
      bringUp()
      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-9', authenticated: true, created: true })
      api().logout()
      api().reload()
      const rebuilt = frame()

      await vi.advanceTimersByTimeAsync(2000)
      expect(frame()).toBe(rebuilt)
    })
  })

  it('forgets a token the frame dropped, wherever the page kept it', async () => {
    ;(window as any).chattermateToken = tokenFor('cust-1')
    await loadLoader()
    bringUp()

    fromFrame({ type: 'TOKEN_CLEAR' })

    expect((window as any).chattermateToken).toBeNull()
  })

  describe('answers that arrive after the page changed its mind', () => {
    it('keeps a token the page set from inside its identityExpired handler', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1', 'old')
      await loadLoader()
      handshake()
      const fresh = tokenFor('cust-1', 'new')
      api().on('identityExpired', () => api().identify(fresh))

      fromFrame({ type: 'WIDGET_ERROR', code: 'identity_expired' })
      await flush()

      expect(localStorage.getItem('ctid')).toBe(fresh)
      expect(handshake()?.message.token).toBe(fresh)
    })

    it('drops a renewed token that comes back after logout', async () => {
      let answer: (token: string) => void = () => {}
      ;(window as any).chattermateConfig = { tokenProvider: () => new Promise((resolve) => { answer = resolve }) }
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      bringUp()
      fromFrame({ type: 'IDENTITY_EXPIRED' })

      api().logout()
      await flush()
      const post = spyOnFrame()
      answer(tokenFor('cust-1', 'renewed'))
      await flush()

      expect(localStorage.getItem('ctid')).toBeNull()
      expect(post.mock.calls.some(([m]) => (m as any).type === 'TOKEN_REFRESH')).toBe(false)
    })

    it('drops a recovered token that comes back after logout, and builds one frame', async () => {
      let answer: (token: string) => void = () => {}
      ;(window as any).chattermateConfig = { tokenProvider: () => new Promise((resolve) => { answer = resolve }) }
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      handshake()
      fromFrame({ type: 'WIDGET_ERROR', code: 'identity_expired' })
      await flush()

      api().logout()
      await flush()
      const afterLogout = frame()
      answer(tokenFor('cust-1', 'recovered'))
      await flush()

      expect(frames()).toHaveLength(1)
      expect(frame()).toBe(afterLogout)
      expect(localStorage.getItem('ctid')).toBeNull()
    })

    it('builds nothing when the widget was destroyed while recovering', async () => {
      let answer: (token: string) => void = () => {}
      ;(window as any).chattermateConfig = { tokenProvider: () => new Promise((resolve) => { answer = resolve }) }
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      handshake()
      fromFrame({ type: 'WIDGET_ERROR', code: 'identity_expired' })
      await flush()

      api().destroy()
      answer(tokenFor('cust-1', 'recovered'))
      await flush()

      expect(frames()).toHaveLength(0)
    })

    it('ignores the outgoing frame asking for a new identity while it closes up', async () => {
      const provider = vi.fn().mockResolvedValue(tokenFor('cust-1', 'again'))
      ;(window as any).chattermateConfig = { tokenProvider: provider }
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      bringUp()
      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-9', authenticated: true, created: true })
      api().logout()
      await flush()

      fromFrame({ type: 'IDENTITY_EXPIRED' })
      await flush()

      expect(provider).not.toHaveBeenCalled()
      expect(localStorage.getItem('ctid')).toBeNull()
    })

    it('restarts with a fresher token when a token-only agent refused the old one', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1', 'a')
      await loadLoader()
      handshake()
      const fresher = tokenFor('cust-1', 'b')
      api().identify(fresher)

      fromFrame({ type: 'WIDGET_ERROR', code: 'token_required' })
      await flush()

      expect(document.querySelector('.chattermate-error-ui')).toBeNull()
      expect(handshake()?.message.token).toBe(fresher)
    })

    it('does not send END_CHAT to a frame that reloaded itself and has not mounted again', async () => {
      ;(window as any).chattermateToken = tokenFor('cust-1')
      await loadLoader()
      bringUp()
      fromFrame({ type: 'CHAT_SESSION', sessionId: 's-9', authenticated: true, created: true })
      handshake() // reloaded itself
      const post = spyOnFrame()
      const before = frame()

      api().logout()
      await flush()

      expect(post.mock.calls.some(([m]) => (m as any).type === 'END_CHAT')).toBe(false)
      expect(frame()).not.toBe(before)
    })
  })
})
